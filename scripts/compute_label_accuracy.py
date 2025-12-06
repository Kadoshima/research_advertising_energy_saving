"""Compute label accuracy and transition delay per interval bucket using time windows.

Approach:
- Use trial_session_mapping_txsd.csv for trial order and ms_total/interval/subject.
- Use RX raw log (rx_trial_*.csv) with ms, seq, label.
- For each trial, define a time window [t0, t1) on RX ms based on cumulative ms_total.
  Assign RX rows falling in that window to the trial.
- Compare RX label vs TX label (labels_all.h) by seq modulo label length.
- Compute accuracy and transition delay per interval bucket.

Outputs CSV to stdout:
interval_bucket_ms,trials,acc_mean,acc_std,delay_mean_ms,delay_p95_ms
"""

import argparse
import csv
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


def load_mapping(path: Path) -> List[dict]:
    rows = list(csv.DictReader(path.open()))
    # add cumulative start/end ms from ms_total
    t0 = 0.0
    for r in rows:
        ms_total = float(r["ms_total"])
        r["start_ms"] = t0
        r["end_ms"] = t0 + ms_total
        t0 = r["end_ms"]
    return rows


def load_labels(labels_all: Path) -> Dict[str, List[int]]:
    text = labels_all.read_text(errors="ignore")
    arrays = {}
    for m in re.finditer(
        # Match definitions like `static const uint8_t subject01[] = {...};`
        r"static const uint8_t\s+(subject\d+)\s*\[\]\s*=\s*\{([^}]*)\};",
        text,
        re.DOTALL,
    ):
        name = m.group(1)
        vals = [
            int(x)
            for x in m.group(2).replace("\n", "").split(",")
            if x.strip().isdigit()
        ]
        arrays[name] = vals
    return arrays


def load_rx_raw(rx_path: Path) -> List[dict]:
    rows = []
    with rx_path.open() as fh:
        for r in csv.DictReader(fh):
            if r.get("ms") and r.get("seq") and r.get("label"):
                rows.append(r)
    rows.sort(key=lambda r: float(r["ms"]))
    return rows


def segment_rx_by_seq(rx_rows: List[dict]) -> List[List[dict]]:
    segments: List[List[dict]] = []
    current: List[dict] = []
    prev_seq: Optional[int] = None
    for r in rx_rows:
        seq = int(r["seq"])
        if prev_seq is not None and seq < prev_seq:
            if current:
                segments.append(current)
            current = []
        current.append(r)
        prev_seq = seq
    if current:
        segments.append(current)
    return segments


def analyze_trial(rows: List[dict], interval_ms: float, labels: List[int]) -> Tuple[float, List[float]]:
    if not rows:
        return math.nan, []
    rows_sorted = sorted(rows, key=lambda r: int(r["seq"]))
    base_ms = float(rows_sorted[0]["ms"])
    base_seq = int(rows_sorted[0]["seq"])
    correct = 0
    total = 0
    delays: List[float] = []

    for r in rows_sorted:
        seq = int(r["seq"])
        lbl_rx = int(r["label"])
        tx_lbl = labels[seq % len(labels)]
        total += 1
        if lbl_rx == tx_lbl:
            correct += 1

    prev_lbl = labels[0]
    for seq in range(1, len(labels)):
        tx_lbl = labels[seq]
        if tx_lbl != prev_lbl:
            cand = [
                float(r["ms"]) - base_ms
                for r in rows_sorted
                if int(r["seq"]) >= seq and int(r["label"]) == tx_lbl
            ]
            if cand:
                rx_first = min(cand)
                tx_time_rel = (seq - base_seq) * interval_ms
                delays.append(rx_first - tx_time_rel)
            prev_lbl = tx_lbl

    acc = correct / total if total else math.nan
    return acc, delays


def main():
    ap = argparse.ArgumentParser(description="Compute label accuracy/delay per interval using time windows.")
    ap.add_argument("--root", required=True, type=Path, help="Root dir containing mapping and RX/TX files.")
    ap.add_argument("--rx-file", type=Path, help="RX raw file (rx_trial_*.csv). If omitted, pick first in root/RX.")
    ap.add_argument(
        "--labels-all",
        default=Path("esp32_firmware/1202/modeC2prime_tx/labels_all.h"),
        type=Path,
    )
    args = ap.parse_args()

    mapping_rows = load_mapping(args.root / "trial_session_mapping_txsd.csv")
    labels_dict = load_labels(args.labels_all)

    rx_file = args.rx_file
    if rx_file is None:
        rx_candidates = sorted((args.root / "RX").glob("rx_trial_*.csv"))
        if not rx_candidates:
            raise SystemExit("No RX files found.")
        rx_file = rx_candidates[0]
    rx_rows = load_rx_raw(rx_file)
    rx_segments = segment_rx_by_seq(rx_rows)

    bucket_stats: Dict[int, Dict[str, List[float]]] = {}

    for i, m in enumerate(mapping_rows):
        if i >= len(rx_segments):
            break
        rows_trial = rx_segments[i]
        trial = m["trial"]
        b = int(m["interval_bucket_ms"]) if m["interval_bucket_ms"] else 0
        if b == 0:
            continue
        subj = m["subject"]
        lbl_arr = labels_dict.get(subj)
        if not lbl_arr:
            continue
        acc, delays = analyze_trial(rows_trial, float(m["interval_ms_est"]), lbl_arr)
        bucket_stats.setdefault(b, {"acc": [], "delays": []})
        if not math.isnan(acc):
            bucket_stats[b]["acc"].append(acc)
        bucket_stats[b]["delays"].extend(delays)

    print("interval_bucket_ms,trials,acc_mean,acc_std,delay_mean_ms,delay_p95_ms")
    for b in sorted(bucket_stats):
        accs = bucket_stats[b]["acc"]
        ds = bucket_stats[b]["delays"]
        acc_mean = sum(accs) / len(accs) if accs else math.nan
        acc_std = (
            (sum((a - acc_mean) ** 2 for a in accs) / len(accs)) ** 0.5
            if accs
            else math.nan
        )
        d_mean = sum(ds) / len(ds) if ds else math.nan
        d_p95 = float(np.percentile(ds, 95)) if ds else math.nan
        print(
            f"{b},{len(accs)},{acc_mean:.4f},{acc_std:.4f},{d_mean:.2f},{d_p95:.2f}"
        )


if __name__ == "__main__":
    main()
