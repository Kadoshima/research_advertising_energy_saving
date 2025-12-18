#!/usr/bin/env python3
"""
Merge key experiment summary tables into one CSV for `results/final/tab/`.

Dependency-free (csv + stdlib only).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    preferred = [
        "dataset",
        "run",
        "condition",
        "avg_power_mW_mean",
        "avg_power_mW_std",
        "pout_1s_mean",
        "pout_1s_std",
        "tl_mean_s_mean",
        "tl_mean_s_std",
        "pdr_unique_mean",
        "pdr_unique_std",
        "adv_count_mean",
        "adv_count_std",
        "share100_power_mix_mean",
        "share100_power_mix_std",
        "rx_tag_share100_time_est_mean",
        "rx_tag_share100_time_est_std",
    ]
    keys = set()
    for r in rows:
        keys.update(r.keys())
    rest = [k for k in sorted(keys) if k not in preferred]
    fieldnames = [k for k in preferred if k in keys] + rest
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def tag_rows(rows: Iterable[Dict[str, str]], dataset: str, run: str) -> List[Dict[str, str]]:
    out = []
    for r in rows:
        rr = dict(r)
        rr["dataset"] = dataset
        rr["run"] = run
        out.append(rr)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--d3", type=Path, default=Path("uccs_d3_scan70/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--d4", type=Path, default=Path("uccs_d4_scan90/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--d4b90", type=Path, default=Path("uccs_d4b_scan90/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--d4b70", type=Path, default=Path("uccs_d4b_scan70/metrics/01_fixed/summary_by_condition.csv"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    merged: List[Dict[str, str]] = []
    if args.d3.exists():
        merged += tag_rows(read_csv(args.d3), dataset="uccs_d3_scan70", run=args.d3.parent.name)
    if args.d4.exists():
        merged += tag_rows(read_csv(args.d4), dataset="uccs_d4_scan90", run=args.d4.parent.name)
    if args.d4b90.exists():
        merged += tag_rows(read_csv(args.d4b90), dataset="uccs_d4b_scan90", run=args.d4b90.parent.name)
    if args.d4b70.exists():
        merged += tag_rows(read_csv(args.d4b70), dataset="uccs_d4b_scan70", run=args.d4b70.parent.name)

    write_csv(args.out, merged)


if __name__ == "__main__":
    main()

