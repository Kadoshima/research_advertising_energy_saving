#!/usr/bin/env python3
"""
Summarize RX logs for sleep_eval_scan90.

This script is a lightweight counterpart of summarize_txsd_power.py.

Inputs:
- sleep_eval_scan90/data/<run>/RX/rx_trial_*.csv

Outputs (default):
- sleep_eval_scan90/metrics/rx_trials.csv
- sleep_eval_scan90/metrics/rx_rate_summary.csv

If --run is provided, outputs go under:
- sleep_eval_scan90/metrics/<run>/...
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RxTrial:
    run: str
    rel_path: str
    path: str
    condition_label: Optional[str]
    ms_total: Optional[int]
    rx: int
    rate_hz: Optional[float]
    ok: bool


def infer_run(fp: Path) -> str:
    parts = list(fp.parts)
    if "data" in parts:
        i = parts.index("data")
        if i + 1 < len(parts):
            return parts[i + 1]
    return "unknown_run"


def infer_rel_path(fp: Path) -> str:
    """
    Returns a stable path under the run directory.
    Example:
      sleep_eval_scan90/data/<run>/RX/rx_trial_001.csv -> RX/rx_trial_001.csv
    """
    parts = list(fp.parts)
    if "data" in parts:
        i = parts.index("data")
        if i + 2 < len(parts):
            return str(Path(*parts[i + 2 :]))
    return fp.name


def parse_rx_csv(fp: Path) -> RxTrial:
    condition_label: Optional[str] = None
    ms_total: Optional[int] = None
    rx = 0

    try:
        with fp.open("r", newline="", errors="ignore") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                if row[0].startswith("#"):
                    if row[0].startswith("# condition_label="):
                        condition_label = row[0].split("=", 1)[1].strip()
                    continue
                if row[0] == "ms":
                    continue
                try:
                    ms = int(row[0])
                except ValueError:
                    continue
                if ms_total is None or ms > ms_total:
                    ms_total = ms
                if len(row) >= 2 and row[1] == "ADV":
                    rx += 1
    except OSError:
        return RxTrial(
            run=infer_run(fp),
            rel_path=infer_rel_path(fp),
            path=str(fp),
            condition_label=None,
            ms_total=None,
            rx=0,
            rate_hz=None,
            ok=False,
        )

    rate_hz = (rx * 1000.0 / ms_total) if (ms_total and ms_total > 0) else None
    ok = bool(condition_label and ms_total is not None and rate_hz is not None)
    return RxTrial(
        run=infer_run(fp),
        rel_path=infer_rel_path(fp),
        path=str(fp),
        condition_label=condition_label,
        ms_total=ms_total,
        rx=rx,
        rate_hz=rate_hz,
        ok=ok,
    )


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    base = repo / "sleep_eval_scan90"

    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=base / "data")
    ap.add_argument("--run", type=str, default=None, help="Optional run filter (e.g., on_off_test_100_2000)")
    ap.add_argument("--min-ms-total", type=int, default=50000, help="Filter out too-short trials (default 50s)")
    args = ap.parse_args()

    data_root = args.data_root
    metrics_dir = base / "metrics"
    if args.run:
        metrics_dir = metrics_dir / args.run
    metrics_dir.mkdir(parents=True, exist_ok=True)

    rx_files = sorted(data_root.glob("**/RX/rx_trial_*.csv"))
    trials = [parse_rx_csv(fp) for fp in rx_files]
    rows = [t.__dict__ for t in trials]
    if args.run:
        rows = [r for r in rows if r["run"] == args.run]

    trials_csv = metrics_dir / "rx_trials.csv"
    with trials_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run", "rel_path", "path", "condition_label", "ok", "ms_total", "rx", "rate_hz"])
        for r in rows:
            w.writerow(
                [
                    r.get("run"),
                    r.get("rel_path"),
                    r.get("path"),
                    r.get("condition_label"),
                    int(bool(r.get("ok"))),
                    r.get("ms_total"),
                    r.get("rx"),
                    r.get("rate_hz"),
                ]
            )

    ok_rows = [r for r in rows if r.get("ok") and (r.get("ms_total") or 0) >= args.min_ms_total]
    if not ok_rows:
        raise SystemExit("No complete RX trials found.")

    # Aggregate by condition_label.
    from collections import defaultdict
    from statistics import mean, pstdev

    groups = defaultdict(list)
    for r in ok_rows:
        groups[str(r.get("condition_label"))].append(r)

    summary_csv = metrics_dir / "rx_rate_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run", "condition_label", "n_trials", "mean_ms_total", "mean_rx", "mean_rate_hz", "std_rate_hz"])
        for cond in sorted(groups.keys()):
            arr = groups[cond]
            ms = [int(x["ms_total"]) for x in arr if x.get("ms_total") is not None]
            rx = [int(x["rx"]) for x in arr]
            rates = [float(x["rate_hz"]) for x in arr if x.get("rate_hz") is not None]
            w.writerow(
                [
                    args.run or "all",
                    cond,
                    len(arr),
                    mean(ms) if ms else "",
                    mean(rx) if rx else "",
                    mean(rates) if rates else "",
                    pstdev(rates) if len(rates) > 1 else 0.0,
                ]
            )

    print(f"wrote {trials_csv}")
    print(f"wrote {summary_csv}")


if __name__ == "__main__":
    main()

