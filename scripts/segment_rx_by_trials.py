"""Segment a single RX log into trials using TX trial durations.

Usage:
  python scripts/segment_rx_by_trials.py \
      --tx-dir data/1202配線変更後/Mode_C_2_02/TX \
      --rx-file data/1202配線変更後/Mode_C_2_02/RX/rx_trial_002.csv \
      --output segmented_pdr.csv

Assumptions:
- TX trials are recorded as trial_XXX_on.csv with 300 adv each.
- The RX log is one continuous file with the ms column relative to RX start.
- Trials run back-to-back; gaps are small. You can shift the RX timeline with
  --rx-offset-ms if the RX started before/after TX.
"""

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Trial:
    name: str
    idx: int
    duration_ms: float
    start_ms: float = 0.0
    end_ms: float = 0.0


def parse_summary_line(line: str) -> dict:
    kv = {}
    parts = line.split(",")
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            kv[k.strip()] = v.strip()
    return kv


def load_tx_trials(tx_dir: Path) -> List[Trial]:
    trials: List[Trial] = []
    for f in sorted(tx_dir.glob("trial_*_on.csv")):
        text = f.read_text(errors="ignore").splitlines()
        summary = next((l for l in text if l.startswith("# summary")), None)
        if not summary:
            continue
        kv = parse_summary_line(summary)
        try:
            ms_total = float(kv["ms_total"])
        except KeyError:
            continue
        try:
            idx = int(f.stem.split("_")[1])
        except Exception:
            idx = -1
        trials.append(Trial(name=f.name, idx=idx, duration_ms=ms_total))
    trials.sort(key=lambda t: t.idx)
    # assign cumulative windows
    t0 = 0.0
    for t in trials:
        t.start_ms = t0
        t.end_ms = t0 + t.duration_ms
        t0 = t.end_ms
    return trials


def segment_rx(rx_file: Path, trials: List[Trial], rx_offset_ms: float):
    per_trial = [
        {"rx_raw": 0, "rx_unique": set()} for _ in range(len(trials))
    ]
    unassigned = 0
    current = 0
    with rx_file.open() as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row or row[0].startswith("#") or row[0] == "ms":
                continue
            try:
                ms = float(row[0]) - rx_offset_ms
                seq = int(row[3])
            except Exception:
                continue
            while current < len(trials) and ms >= trials[current].end_ms:
                current += 1
            if current >= len(trials):
                unassigned += 1
                continue
            if ms < trials[current].start_ms:
                unassigned += 1
                continue
            per_trial[current]["rx_raw"] += 1
            per_trial[current]["rx_unique"].add(seq)
    return per_trial, unassigned


def main():
    ap = argparse.ArgumentParser(description="Segment RX log by TX trials.")
    ap.add_argument("--tx-dir", required=True, type=Path)
    ap.add_argument("--rx-file", required=True, type=Path)
    ap.add_argument("--rx-offset-ms", type=float, default=0.0,
                    help="Shift RX ms by this amount (RX_ms - offset).")
    ap.add_argument("--output", type=Path, default=None,
                    help="CSV output path (stdout if omitted).")
    args = ap.parse_args()

    trials = load_tx_trials(args.tx_dir)
    if not trials:
        raise SystemExit("No TX trials found.")

    per_trial, unassigned = segment_rx(args.rx_file, trials, args.rx_offset_ms)

    out_rows = []
    for t, stats in zip(trials, per_trial):
        rx_raw = stats["rx_raw"]
        rx_unique = len(stats["rx_unique"])
        pdr_raw = rx_raw / 300.0 if 300 else 0.0
        pdr_unique = rx_unique / 300.0 if 300 else 0.0
        out_rows.append({
            "trial": t.name,
            "trial_idx": t.idx,
            "interval_ms_est": round(t.duration_ms / 300.0, 2),
            "start_ms": round(t.start_ms, 2),
            "end_ms": round(t.end_ms, 2),
            "duration_ms": round(t.duration_ms, 2),
            "rx_raw": rx_raw,
            "rx_unique": rx_unique,
            "pdr_raw": round(pdr_raw, 4),
            "pdr_unique": round(pdr_unique, 4),
        })

    out_fields = list(out_rows[0].keys())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=out_fields)
            writer.writeheader()
            writer.writerows(out_rows)
        print(f"wrote {len(out_rows)} rows to {args.output} (unassigned={unassigned})")
    else:
        writer = csv.DictWriter(
            open(1, "w", newline=""), fieldnames=out_fields  # stdout fd=1
        )
        writer.writeheader()
        writer.writerows(out_rows)
        print(f"# unassigned={unassigned}")


if __name__ == "__main__":
    main()
