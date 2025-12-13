#!/usr/bin/env python3
"""
Summarize TXSD power logs for sleep_eval_scan90.

Input layout (current):
  sleep_eval_scan90/data/<interval_ms>/{TX,RX}/trial_*.csv

This script focuses on TXSD logs (power) and outputs:
  - sleep_eval_scan90/metrics/txsd_power_trials.csv
  - sleep_eval_scan90/metrics/txsd_power_summary.csv
  - sleep_eval_scan90/plots/txsd_power_summary.png

If a TXSD file lacks '# diag'/'# summary' footer, it is treated as incomplete and
excluded from aggregate summaries (still listed in trials CSV with status).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class Trial:
    interval_ms: Optional[int]
    condition: str
    path: str
    ms_total: Optional[int]
    mean_p_mw: Optional[float]
    mean_v: Optional[float]
    mean_i: Optional[float]
    samples: Optional[int]
    ok: bool


def infer_interval_ms(fp: Path) -> Optional[int]:
    for part in fp.parts:
        if part.isdigit():
            return int(part)
    return None


def infer_condition(fp: Path) -> str:
    parts = set(fp.parts)
    if "sleep_on" in parts:
        return "sleep_on"
    if "sleep_off" in parts:
        return "sleep_off"
    return "unknown"


def parse_footer(fp: Path) -> Trial:
    lines = fp.read_text(errors="ignore").splitlines()
    summary = next((l for l in reversed(lines) if l.startswith("# summary,")), None)
    diag = next((l for l in reversed(lines) if l.startswith("# diag,")), None)

    ms_total = None
    mean_p = None
    mean_v = None
    mean_i = None
    samples = None

    if summary:
        m = re.search(r"ms_total=(\d+)", summary)
        if m:
            ms_total = int(m.group(1))

    if diag:
        m = re.search(r"samples=(\d+)", diag)
        if m:
            samples = int(m.group(1))
        m = re.search(r"mean_v=([0-9.]+)", diag)
        if m:
            mean_v = float(m.group(1))
        m = re.search(r"mean_i=([0-9.]+)", diag)
        if m:
            mean_i = float(m.group(1))
        m = re.search(r"mean_p_mW=([0-9.]+)", diag)
        if m:
            mean_p = float(m.group(1))

    ok = bool(summary and diag and ms_total is not None and mean_p is not None)
    return Trial(
        interval_ms=infer_interval_ms(fp),
        condition=infer_condition(fp),
        path=str(fp),
        ms_total=ms_total,
        mean_p_mw=mean_p,
        mean_v=mean_v,
        mean_i=mean_i,
        samples=samples,
        ok=ok,
    )


def save_plot(summary_csv: Path, out_png: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pd.read_csv(summary_csv)
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=160)
    for cond, sub in df.groupby("condition"):
        sub = sub.sort_values("interval_ms")
        x = sub["interval_ms"].astype(int).to_list()
        y = sub["mean_mean_p_mw"].to_list()
        yerr = sub["std_mean_p_mw"].to_list()
        ax.errorbar(x, y, yerr=yerr, fmt="o-", capsize=4, label=cond)
    ax.set_xlabel("ADV interval (ms)")
    ax.set_ylabel("TX power mean_p (mW)")
    ax.set_title("sleep_eval_scan90: TXSD mean power (per trial)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png)
    plt.close(fig)


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    base = repo / "sleep_eval_scan90"
    data_dir = base / "data"
    metrics_dir = base / "metrics"
    plots_dir = base / "plots"

    txsd_files = sorted(data_dir.glob("**/TX/trial_*.csv"))
    trials = [parse_footer(fp) for fp in txsd_files]

    metrics_dir.mkdir(parents=True, exist_ok=True)

    trials_csv = metrics_dir / "txsd_power_trials.csv"
    with trials_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "condition",
                "interval_ms",
                "path",
                "ok",
                "ms_total",
                "samples",
                "mean_p_mw",
                "mean_v",
                "mean_i",
            ]
        )
        for t in trials:
            w.writerow(
                [
                    t.condition,
                    t.interval_ms,
                    t.path,
                    int(t.ok),
                    t.ms_total,
                    t.samples,
                    t.mean_p_mw,
                    t.mean_v,
                    t.mean_i,
                ]
            )

    df = pd.DataFrame([t.__dict__ for t in trials])
    ok_df = df[df["ok"] == True].copy()
    if ok_df.empty:
        raise SystemExit("No complete TXSD trials found (missing '# summary'/'# diag').")

    summary = (
        ok_df.groupby(["condition", "interval_ms"])
        .agg(
            n_trials=("mean_p_mw", "count"),
            mean_ms_total=("ms_total", "mean"),
            mean_mean_p_mw=("mean_p_mw", "mean"),
            std_mean_p_mw=("mean_p_mw", "std"),
        )
        .reset_index()
    )
    summary["std_mean_p_mw"] = summary["std_mean_p_mw"].fillna(0.0)

    summary_csv = metrics_dir / "txsd_power_summary.csv"
    summary.to_csv(summary_csv, index=False)

    save_plot(summary_csv, plots_dir / "txsd_power_summary.png")

    print(f"wrote {trials_csv}")
    print(f"wrote {summary_csv}")
    print(f"wrote {plots_dir / 'txsd_power_summary.png'}")


if __name__ == "__main__":
    main()
