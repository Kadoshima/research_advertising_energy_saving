#!/usr/bin/env python3
"""
Aggregate per-trial summary CSV from analyze_stress_causal_real.py into:
  - modes (per-trial trimmed)
  - agg (session×interval summary stats)
  - agg_enriched (agg + derived columns)

Designed for stress_fixed/scan90 outputs under results/stress_fixed/scan90/.
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def to_float(x: str) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def to_int(x: str) -> int:
    try:
        return int(float(x))
    except Exception:
        return 0


def infer_session_from_truth_path(truth_path: str) -> str:
    name = Path(truth_path).name
    m = re.search(r"stress_causal_(S\d+)\.csv", name)
    if m:
        return m.group(1)
    m = re.search(r"(S\d+)", name)
    return m.group(1) if m else "UNKNOWN"


def mean_median_std(values: List[float]) -> Tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    mu = statistics.mean(values)
    med = statistics.median(values)
    if len(values) < 2:
        sd = 0.0
    else:
        sd = statistics.stdev(values)
    return mu, med, sd


def main() -> None:
    ap = argparse.ArgumentParser(description="Aggregate stress_causal_real per-trial CSV into modes/agg/enriched.")
    ap.add_argument("--in", dest="in_path", required=True, type=Path, help="Input per-trial CSV (full_*.csv)")
    ap.add_argument("--out-modes", required=True, type=Path)
    ap.add_argument("--out-agg", required=True, type=Path)
    ap.add_argument("--out-agg-enriched", required=True, type=Path)
    args = ap.parse_args()

    rows: List[Dict[str, str]] = []
    with args.in_path.open() as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            rows.append(row)

    modes_fieldnames = [
        "trial_id",
        "session",
        "interval_ms",
        "mode",
        "pdr_raw",
        "pdr_unique",
        "pout_1s",
        "pout_2s",
        "pout_3s",
        "tl_mean_s",
        "tl_p95_s",
        "tl_clamp_high_rate",
        "E_per_adv_uJ",
        "avg_power_mW",
        "rx_dup_factor",
        "tl_time_offset_ms",
        "tl_time_offset_n",
    ]

    args.out_modes.parent.mkdir(parents=True, exist_ok=True)
    with args.out_modes.open("w", newline="") as f_out:
        w = csv.DictWriter(f_out, fieldnames=modes_fieldnames)
        w.writeheader()
        for row in rows:
            interval_ms = to_int(row.get("interval_ms", "0"))
            if interval_ms <= 0:
                continue
            session = (row.get("session") or "").strip() or infer_session_from_truth_path(row.get("truth_path", ""))
            rx_count = to_float(row.get("rx_count", "0"))
            rx_unique = to_float(row.get("rx_unique", "0"))
            rx_dup_factor = (rx_count / rx_unique) if rx_unique else 0.0
            w.writerow(
                {
                    "trial_id": row.get("trial_id", ""),
                    "session": session,
                    "interval_ms": interval_ms,
                    "mode": row.get("mode", ""),
                    "pdr_raw": row.get("pdr_raw", ""),
                    "pdr_unique": row.get("pdr_unique", ""),
                    "pout_1s": row.get("pout_1s", ""),
                    "pout_2s": row.get("pout_2s", ""),
                    "pout_3s": row.get("pout_3s", ""),
                    "tl_mean_s": row.get("tl_mean_s", ""),
                    "tl_p95_s": row.get("tl_p95_s", ""),
                    "tl_clamp_high_rate": row.get("tl_clamp_high_rate", ""),
                    "E_per_adv_uJ": row.get("E_per_adv_uJ", ""),
                    "avg_power_mW": row.get("avg_power_mW", ""),
                    "rx_dup_factor": f"{rx_dup_factor:.6f}",
                    "tl_time_offset_ms": row.get("tl_time_offset_ms", ""),
                    "tl_time_offset_n": row.get("tl_time_offset_n", ""),
                }
            )

    # Aggregation
    metrics = [
        "pdr_raw",
        "pdr_unique",
        "pout_1s",
        "pout_2s",
        "pout_3s",
        "tl_mean_s",
        "tl_p95_s",
        "E_per_adv_uJ",
        "avg_power_mW",
        "tl_clamp_high_rate",
        "rx_dup_factor",
        "tl_time_offset_ms",
    ]

    grouped: Dict[Tuple[str, int], Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    counts: Dict[Tuple[str, int], int] = defaultdict(int)

    with args.out_modes.open() as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            session = row.get("session", "UNKNOWN")
            interval_ms = to_int(row.get("interval_ms", "0"))
            key = (session, interval_ms)
            counts[key] += 1
            for m in metrics:
                grouped[key][m].append(to_float(row.get(m, "0")))

    agg_fieldnames: List[str] = ["session", "interval_ms", "n"]
    for m in metrics:
        agg_fieldnames.extend([f"{m}_mean", f"{m}_median", f"{m}_std"])

    args.out_agg.parent.mkdir(parents=True, exist_ok=True)
    with args.out_agg.open("w", newline="") as f_out:
        w = csv.DictWriter(f_out, fieldnames=agg_fieldnames)
        w.writeheader()
        for (session, interval_ms) in sorted(grouped.keys(), key=lambda x: (x[0], x[1])):
            row_out: Dict[str, object] = {"session": session, "interval_ms": interval_ms, "n": counts[(session, interval_ms)]}
            for m in metrics:
                mu, med, sd = mean_median_std(grouped[(session, interval_ms)][m])
                row_out[f"{m}_mean"] = mu
                row_out[f"{m}_median"] = med
                row_out[f"{m}_std"] = sd
            w.writerow(row_out)

    # Enriched
    args.out_agg_enriched.parent.mkdir(parents=True, exist_ok=True)
    with args.out_agg.open() as f_in, args.out_agg_enriched.open("w", newline="") as f_out:
        rdr = csv.DictReader(f_in)
        fieldnames = list(rdr.fieldnames or [])
        # keep compatibility with existing enriched outputs
        for extra in ["pout1s_excess", "tl_mean_norm"]:
            if extra not in fieldnames:
                fieldnames.append(extra)
        w = csv.DictWriter(f_out, fieldnames=fieldnames)
        w.writeheader()

        for row in rdr:
            interval_ms = to_float(row.get("interval_ms", "0"))
            pout_1s_mean = to_float(row.get("pout_1s_mean", "0"))
            tl_mean_s_mean = to_float(row.get("tl_mean_s_mean", "0"))

            # v4 compatibility: treat "excess over 0.5" as a simple flag-like metric.
            row["pout1s_excess"] = max(pout_1s_mean - 0.5, 0.0)

            interval_s = interval_ms / 1000.0 if interval_ms else 0.0
            row["tl_mean_norm"] = (tl_mean_s_mean / interval_s) if interval_s else 0.0

            w.writerow(row)

    print(f"[INFO] wrote modes: {args.out_modes}")
    print(f"[INFO] wrote agg: {args.out_agg}")
    print(f"[INFO] wrote agg_enriched: {args.out_agg_enriched}")


if __name__ == "__main__":
    main()
