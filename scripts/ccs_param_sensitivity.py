#!/usr/bin/env python3
"""
CCS parameter sensitivity (alpha, W) using existing CCS sequences.

Inputs:
  - data/ccs_sequences/subject*_ccs.csv
    Columns: timestamp_ms,u,s,ccs,interval_ms,pred_label,true_label_4

Outputs:
  - summary_by_subject.csv
  - summary_overall.csv
  - summary_delta_vs_base.csv
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np


@dataclass
class SeriesData:
    subject_id: str
    ts_ms: np.ndarray
    u: np.ndarray
    pred_label: np.ndarray


def load_series(path: Path) -> SeriesData:
    ts_ms: List[int] = []
    u_vals: List[float] = []
    pred: List[int] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_ms.append(int(row["timestamp_ms"]))
            u_vals.append(float(row["u"]))
            pred.append(int(row["pred_label"]))
    subject_id = path.stem.replace("subject", "")
    return SeriesData(
        subject_id=subject_id,
        ts_ms=np.asarray(ts_ms, dtype=np.int64),
        u=np.asarray(u_vals, dtype=np.float64),
        pred_label=np.asarray(pred, dtype=np.int64),
    )


def compute_stability(pred_labels: np.ndarray, W: int) -> np.ndarray:
    n = len(pred_labels)
    s = np.zeros(n, dtype=np.float64)
    for i in range(n):
        start = max(0, i - W + 1)
        window_labels = pred_labels[start : i + 1]
        n_trans = int(np.sum(window_labels[1:] != window_labels[:-1]))
        s[i] = 1.0 - min(1.0, n_trans / float(W))
    return s


def ccs_to_interval(
    ccs_series: np.ndarray,
    ts_ms: np.ndarray,
    theta_high: float,
    theta_low: float,
    hysteresis: float,
    min_stay_s: float,
) -> np.ndarray:
    n = len(ccs_series)
    intervals = np.zeros(n, dtype=np.int32)

    if ccs_series[0] >= theta_high:
        intervals[0] = 2000
    elif ccs_series[0] >= theta_low:
        intervals[0] = 500
    else:
        intervals[0] = 100

    last_change_s = ts_ms[0] / 1000.0

    theta_high_up = theta_high
    theta_high_down = theta_high - hysteresis
    theta_low_up = theta_low
    theta_low_down = theta_low - hysteresis

    for i in range(1, n):
        t_s = ts_ms[i] / 1000.0
        prev_interval = intervals[i - 1]
        if t_s - last_change_s < min_stay_s:
            intervals[i] = prev_interval
            continue

        ccs = ccs_series[i]
        new_interval = prev_interval

        if prev_interval == 2000:
            if ccs < theta_low_down:
                new_interval = 100
            elif ccs < theta_high_down:
                new_interval = 500
        elif prev_interval == 500:
            if ccs >= theta_high_up:
                new_interval = 2000
            elif ccs < theta_low_down:
                new_interval = 100
        else:
            if ccs >= theta_high_up:
                new_interval = 2000
            elif ccs >= theta_low_up:
                new_interval = 500

        if new_interval != prev_interval:
            last_change_s = t_s
        intervals[i] = new_interval

    return intervals


def summarize_series(
    series: SeriesData,
    alpha: float,
    W: int,
    theta_low: float,
    theta_high: float,
    hysteresis: float,
    min_stay_s: float,
) -> Dict[str, float]:
    s = compute_stability(series.pred_label, W)
    ccs = alpha * (1.0 - series.u) + (1.0 - alpha) * s
    intervals = ccs_to_interval(
        ccs,
        series.ts_ms,
        theta_high=theta_high,
        theta_low=theta_low,
        hysteresis=hysteresis,
        min_stay_s=min_stay_s,
    )

    n = len(ccs)
    counts_100 = int(np.sum(intervals == 100))
    counts_500 = int(np.sum(intervals == 500))
    counts_2000 = int(np.sum(intervals == 2000))
    switches = int(np.sum(intervals[1:] != intervals[:-1]))

    ccs_mean = float(np.mean(ccs))
    ccs_std = float(np.std(ccs))
    s_mean = float(np.mean(s))
    s_std = float(np.std(s))

    return {
        "n_windows": n,
        "ccs_mean": ccs_mean,
        "ccs_std": ccs_std,
        "s_mean": s_mean,
        "s_std": s_std,
        "switches": switches,
        "switch_rate": switches / n if n else 0.0,
        "share_100": counts_100 / n if n else 0.0,
        "share_500": counts_500 / n if n else 0.0,
        "share_2000": counts_2000 / n if n else 0.0,
    }


def weighted_mean(vals: Iterable[float], weights: Iterable[int]) -> float:
    total_w = float(sum(weights))
    if total_w == 0.0:
        return 0.0
    return float(sum(v * w for v, w in zip(vals, weights))) / total_w


def write_csv(path: Path, rows: List[Dict[str, object]], headers: List[str]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="CCS alpha/W sensitivity using existing CCS sequences")
    parser.add_argument("--input-dir", type=Path, default=Path("data/ccs_sequences"))
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--alphas", type=str, default="0.6,0.7,0.8")
    parser.add_argument("--ws", type=str, default="3,5,7")
    parser.add_argument("--theta-low", type=float, default=0.80)
    parser.add_argument("--theta-high", type=float, default=0.90)
    parser.add_argument("--hysteresis", type=float, default=0.05)
    parser.add_argument("--min-stay-s", type=float, default=2.0)
    args = parser.parse_args()

    alphas = [float(x) for x in args.alphas.split(",") if x.strip()]
    ws = [int(x) for x in args.ws.split(",") if x.strip()]

    series_paths = sorted(args.input_dir.glob("subject*_ccs.csv"))
    if not series_paths:
        raise SystemExit(f"No subject*_ccs.csv found in {args.input_dir}")

    if args.out_dir is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        args.out_dir = Path("results") / f"ccs_param_sensitivity_{date_str}_v01"
    args.out_dir.mkdir(parents=True, exist_ok=True)

    series_list = [load_series(p) for p in series_paths]

    rows_by_subject: List[Dict[str, object]] = []
    rows_overall: List[Dict[str, object]] = []

    for alpha in alphas:
        for W in ws:
            # Per-subject rows
            for s in series_list:
                stats = summarize_series(
                    s,
                    alpha=alpha,
                    W=W,
                    theta_low=args.theta_low,
                    theta_high=args.theta_high,
                    hysteresis=args.hysteresis,
                    min_stay_s=args.min_stay_s,
                )
                rows_by_subject.append(
                    {
                        "subject_id": s.subject_id,
                        "alpha": alpha,
                        "W": W,
                        **stats,
                    }
                )

            # Aggregate over all subjects
            stats_list = [r for r in rows_by_subject if r["alpha"] == alpha and r["W"] == W]
            weights = [int(r["n_windows"]) for r in stats_list]
            total_windows = sum(weights)

            def wmean(key: str) -> float:
                return weighted_mean([float(r[key]) for r in stats_list], weights)

            rows_overall.append(
                {
                    "alpha": alpha,
                    "W": W,
                    "n_windows": total_windows,
                    "ccs_mean": wmean("ccs_mean"),
                    "ccs_std": wmean("ccs_std"),
                    "s_mean": wmean("s_mean"),
                    "s_std": wmean("s_std"),
                    "switch_rate": wmean("switch_rate"),
                    "share_100": wmean("share_100"),
                    "share_500": wmean("share_500"),
                    "share_2000": wmean("share_2000"),
                }
            )

    headers_subject = [
        "subject_id",
        "alpha",
        "W",
        "n_windows",
        "ccs_mean",
        "ccs_std",
        "s_mean",
        "s_std",
        "switches",
        "switch_rate",
        "share_100",
        "share_500",
        "share_2000",
    ]
    headers_overall = [
        "alpha",
        "W",
        "n_windows",
        "ccs_mean",
        "ccs_std",
        "s_mean",
        "s_std",
        "switch_rate",
        "share_100",
        "share_500",
        "share_2000",
    ]

    write_csv(args.out_dir / "summary_by_subject.csv", rows_by_subject, headers_subject)
    write_csv(args.out_dir / "summary_overall.csv", rows_overall, headers_overall)

    # Delta vs baseline (alpha=0.7, W=5)
    baseline = next((r for r in rows_overall if r["alpha"] == 0.7 and r["W"] == 5), None)
    delta_rows: List[Dict[str, object]] = []
    if baseline:
        for r in rows_overall:
            delta_rows.append(
                {
                    "alpha": r["alpha"],
                    "W": r["W"],
                    "delta_ccs_mean": r["ccs_mean"] - baseline["ccs_mean"],
                    "delta_ccs_std": r["ccs_std"] - baseline["ccs_std"],
                    "delta_s_mean": r["s_mean"] - baseline["s_mean"],
                    "delta_s_std": r["s_std"] - baseline["s_std"],
                    "delta_switch_rate": r["switch_rate"] - baseline["switch_rate"],
                    "delta_share_100": r["share_100"] - baseline["share_100"],
                    "delta_share_500": r["share_500"] - baseline["share_500"],
                    "delta_share_2000": r["share_2000"] - baseline["share_2000"],
                }
            )
        delta_headers = list(delta_rows[0].keys())
        write_csv(args.out_dir / "summary_delta_vs_base.csv", delta_rows, delta_headers)

    print(f"[OK] Wrote: {args.out_dir}")


if __name__ == "__main__":
    main()
