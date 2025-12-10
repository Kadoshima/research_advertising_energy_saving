#!/usr/bin/env python3
"""
Analyze stress-case real logs (RX + TXSD) and emit per-trial QoS/energy metrics.

Key outputs per trial (CSV):
  - pdr
  - pout_1s / pout_2s / pout_3s
  - tl_mean_s / tl_p95_s
  - E_total_mJ / E_per_adv_uJ / avg_power_mW / duration_ms

Usage example:
  python scripts/analyze_stress_causal_real.py \
    --rx-dir data/.../RX \
    --txsd-dir data/.../TXSD \
    --truth-dir Mode_C_2_シミュレート_causal/ccs \
    --truth-map maps/trial_truth_map.csv \
    --out results/stress_causal_real_summary.csv

Notes:
  - truth_map is optional; if provided, it should be CSV with columns:
      trial_id,truth_file[,mode]
    truth_file can be relative to --truth-dir.
  - If no truth is available, TL/Pout are left empty.
  - Trial id is inferred from rx filename `rx_trial_XXX*.csv`; txsd is matched to
    `trial_XXX_on.csv` in --txsd-dir.
"""
from __future__ import annotations

import argparse
import csv
import re
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple


TAU_VALUES = (1.0, 2.0, 3.0)  # seconds
STEP_MS = 100  # label timeline resolution for truth files


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def read_truth_labels(path: Path) -> List[int]:
    labels: List[int] = []
    with path.open() as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            labels.append(int(row["label"]))
    return labels


def read_txsd_summary(path: Path) -> Tuple[Optional[float], Optional[float], Optional[int], Optional[float]]:
    """
    Returns (E_total_mJ, E_per_adv_uJ, adv_count, duration_ms)
    Falls back to None if summary not found.
    """
    summary_line = None
    duration_ms = None
    with path.open() as f:
        for line in f:
            if line.startswith("# summary"):
                summary_line = line
            if line.startswith("# diag") and "ms_total=" in line:
                # diag, ms_total=..., rate_hz=...
                try:
                    for part in line.strip().split(","):
                        if part.strip().startswith("ms_total="):
                            duration_ms = float(part.split("=")[1])
                except Exception:
                    pass
    if summary_line:
        parts = summary_line.strip().split(",")
        vals = {}
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                vals[k.strip("# ").strip()] = v
        try:
            e_total = float(vals.get("E_total_mJ")) if "E_total_mJ" in vals else None
        except Exception:
            e_total = None
        try:
            e_per = float(vals.get("E_per_adv_uJ")) if "E_per_adv_uJ" in vals else None
        except Exception:
            e_per = None
        try:
            adv_count = int(vals.get("adv_count")) if "adv_count" in vals else None
        except Exception:
            adv_count = None
    else:
        e_total = e_per = adv_count = None
    # duration fallback: last ms if not in diag
    if duration_ms is None and summary_line:
        if "ms_total" in summary_line:
            try:
                for part in summary_line.strip().split(","):
                    if part.strip().startswith("ms_total="):
                        duration_ms = float(part.split("=")[1])
            except Exception:
                pass
    return e_total, e_per, adv_count, duration_ms


def parse_rx(path: Path) -> Tuple[List[Tuple[float, int, int]], int, int]:
    """
    Returns (events, rx_count, rx_unique)
    events: list of (ms, seq, label)
    """
    events: List[Tuple[float, int, int]] = []
    seq_set = set()
    with path.open() as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            try:
                ms = float(row.get("ms") or row.get("timestamp_ms") or 0.0)
            except Exception:
                continue
            # sequence
            seq = None
            if "seq" in row and row["seq"]:
                try:
                    seq = int(row["seq"])
                except Exception:
                    seq = None
            if seq is None and "mfd" in row and row["mfd"]:
                m = re.match(r"(\\d+)", row["mfd"])
                if m:
                    try:
                        seq = int(m.group(1))
                    except Exception:
                        seq = None
            if seq is None:
                seq = len(events)  # fallback monotonic
            # label
            label = None
            if "label" in row and row["label"]:
                try:
                    label = int(row["label"])
                except Exception:
                    label = None
            if label is None and "mfd" in row and row["mfd"]:
                m = re.match(r"\\d+_(\\d+)", row["mfd"])
                if m:
                    try:
                        label = int(m.group(1))
                    except Exception:
                        label = None
            if label is None:
                label = -1
            events.append((ms, seq, label))
            seq_set.add(seq)
    return events, len(events), len(seq_set)


def compute_tl_and_pout(truth_labels: List[int], rx_events: List[Tuple[float, int, int]]) -> Tuple[float, float, Dict[float, float]]:
    # Transitions from truth timeline
    transitions_ms: List[int] = []
    prev = truth_labels[0]
    for idx, lab in enumerate(truth_labels[1:], start=1):
        if lab != prev:
            transitions_ms.append(idx * STEP_MS)
            prev = lab
    if not transitions_ms:
        return 0.0, 0.0, {tau: 0.0 for tau in TAU_VALUES}

    # For each transition, find first RX event after transition whose label matches truth at that time (last-value-hold of truth)
    tl_list_s: List[float] = []
    rx_events_sorted = sorted(rx_events, key=lambda x: x[0])
    for t_ms in transitions_ms:
        true_label = truth_labels[min(len(truth_labels) - 1, t_ms // STEP_MS)]
        arrival = None
        for ms, _, lbl in rx_events_sorted:
            if ms > t_ms and lbl == true_label:
                arrival = ms
                break
        if arrival is None:
            # no reception after transition; treat as full duration miss
            tl_list_s.append((len(truth_labels) * STEP_MS - t_ms) / 1000.0)
        else:
            tl_list_s.append((arrival - t_ms) / 1000.0)

    tl_mean = statistics.mean(tl_list_s) if tl_list_s else 0.0
    tl_p95 = statistics.quantiles(tl_list_s, n=100)[94] if len(tl_list_s) >= 2 else (tl_list_s[0] if tl_list_s else 0.0)
    pout = {}
    for tau in TAU_VALUES:
        pout[tau] = sum(1 for tl in tl_list_s if tl > tau) / len(tl_list_s)
    return tl_mean, tl_p95, pout


def infer_mode(trial_id: str, filename: str, override: Optional[str]) -> Optional[str]:
    if override:
        return override
    m = re.search(r"(FIXED[_-]?1000?|FIXED[_-]?2000|FIXED[_-]?500|CCS[_-]?causal)", filename, re.IGNORECASE)
    if m:
        return m.group(1).upper().replace("-", "_")
    return None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze stress-case real RX/TXSD logs.")
    ap.add_argument("--rx-dir", required=True, type=Path)
    ap.add_argument("--txsd-dir", required=True, type=Path)
    ap.add_argument("--truth-dir", type=Path, help="Directory with truth timelines (idx,label,...) e.g., Mode_C_2_シミュレート_causal/ccs")
    ap.add_argument("--truth-map", type=Path, help="CSV mapping trial_id -> truth_file[,mode]")
    ap.add_argument("--mode", type=str, help="Force mode name for all trials (e.g., FIXED_100)")
    ap.add_argument("--out", required=True, type=Path, help="Output CSV summary path")
    args = ap.parse_args()

    truth_map: Dict[str, Dict[str, str]] = {}
    if args.truth_map and args.truth_map.exists():
        with args.truth_map.open() as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                tid = row["trial_id"]
                truth_map[tid] = {
                    "truth_file": row.get("truth_file", ""),
                    "mode": row.get("mode", "") or "",
                }

    rx_files = sorted(args.rx_dir.glob("rx_trial_*.csv"))
    if not rx_files:
        raise SystemExit(f"No rx_trial_*.csv found in {args.rx_dir}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f_out:
        fieldnames = [
            "trial_id",
            "mode",
            "adv_count",
            "rx_count",
            "rx_unique",
            "pdr",
            "tl_mean_s",
            "tl_p95_s",
            "pout_1s",
            "pout_2s",
            "pout_3s",
            "E_total_mJ",
            "E_per_adv_uJ",
            "avg_power_mW",
            "duration_ms",
            "rx_path",
            "txsd_path",
            "truth_path",
        ]
        w = csv.DictWriter(f_out, fieldnames=fieldnames)
        w.writeheader()

        for rx_path in rx_files:
            m = re.search(r"rx_trial_(\\d+)", rx_path.name)
            trial_id = m.group(1) if m else rx_path.stem
            txsd_path = args.txsd_dir / f"trial_{trial_id}_on.csv"
            if not txsd_path.exists():
                txsd_path = args.txsd_dir / f"trial_{trial_id}.csv"
            if not txsd_path.exists():
                print(f"[WARN] TXSD missing for trial {trial_id}, skip")
                continue

            # truth resolution
            truth_path = None
            mode_override = None
            if trial_id in truth_map:
                tfile = truth_map[trial_id].get("truth_file", "")
                if tfile:
                    truth_path = args.truth_dir / tfile if args.truth_dir else Path(tfile)
                mode_override = truth_map[trial_id].get("mode") or None
            if truth_path is None and args.truth_dir:
                candidate = args.truth_dir / f"{trial_id}.csv"
                if candidate.exists():
                    truth_path = candidate

            truth_labels = read_truth_labels(truth_path) if truth_path and truth_path.exists() else None

            rx_events, rx_count, rx_unique = parse_rx(rx_path)
            e_total_mj, e_per_adv_uj, adv_count, duration_ms = read_txsd_summary(txsd_path)

            if adv_count is None:
                adv_count = max((seq for _, seq, _ in rx_events), default=0) + 1
            pdr = (rx_unique / adv_count) if adv_count else 0.0

            tl_mean_s = tl_p95_s = 0.0
            pout = {tau: 0.0 for tau in TAU_VALUES}
            if truth_labels:
                tl_mean_s, tl_p95_s, pout = compute_tl_and_pout(truth_labels, rx_events)

            if duration_ms is None and rx_events:
                duration_ms = rx_events[-1][0] - rx_events[0][0]
            if e_total_mj is None:
                # rough integrate assuming uniform 10ms sampling
                e_total_mj = 0.0

            if e_per_adv_uj is None and e_total_mj is not None and adv_count:
                e_per_adv_uj = (e_total_mj * 1000.0) / adv_count
            avg_power_mw = None
            if e_total_mj is not None and duration_ms:
                avg_power_mw = e_total_mj / (duration_ms / 1000.0)

            mode = infer_mode(trial_id, rx_path.name, args.mode or mode_override)

            row = {
                "trial_id": trial_id,
                "mode": mode or "",
                "adv_count": adv_count,
                "rx_count": rx_count,
                "rx_unique": rx_unique,
                "pdr": round(pdr, 6),
                "tl_mean_s": round(tl_mean_s, 6),
                "tl_p95_s": round(tl_p95_s, 6),
                "pout_1s": round(pout[1.0], 6),
                "pout_2s": round(pout[2.0], 6),
                "pout_3s": round(pout[3.0], 6),
                "E_total_mJ": e_total_mj,
                "E_per_adv_uJ": e_per_adv_uj,
                "avg_power_mW": avg_power_mw,
                "duration_ms": duration_ms,
                "rx_path": str(rx_path),
                "txsd_path": str(txsd_path),
                "truth_path": str(truth_path) if truth_path else "",
            }
            w.writerow(row)
    print(f"[INFO] wrote summary to {args.out}")


if __name__ == "__main__":
    main()
