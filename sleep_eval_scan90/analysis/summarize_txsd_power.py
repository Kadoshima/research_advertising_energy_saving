#!/usr/bin/env python3
"""
Summarize TXSD power logs for sleep_eval_scan90.

Supports:
- Per-run data folders under `sleep_eval_scan90/data/<run>/...`
- Condition inference from TXSD meta line:
    # meta, ..., cond_id=*, adv_interval_ms=*, sleep=on/off/unk, ...
  This is preferred over directory naming.

Outputs (default):
- sleep_eval_scan90/metrics/txsd_power_trials.csv
- sleep_eval_scan90/metrics/txsd_power_summary.csv
- sleep_eval_scan90/metrics/txsd_power_diff.md
- sleep_eval_scan90/plots/txsd_power_summary.png

If --run is provided, outputs go under:
- sleep_eval_scan90/metrics/<run>/...
- sleep_eval_scan90/plots/<run>/...
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class Trial:
    run: str
    condition: str  # sleep_on/sleep_off/unknown
    interval_ms: Optional[int]
    cond_id: Optional[int]
    path: str
    ms_total: Optional[int]
    mean_p_mw: Optional[float]
    mean_v: Optional[float]
    mean_i: Optional[float]
    samples: Optional[int]
    ok: bool


def infer_run(fp: Path) -> str:
    parts = list(fp.parts)
    if "data" in parts:
        i = parts.index("data")
        if i + 1 < len(parts):
            return parts[i + 1]
    return "unknown_run"


def infer_interval_ms_from_path(fp: Path) -> Optional[int]:
    for part in fp.parts:
        if part.isdigit():
            return int(part)
    return None


def infer_condition_from_path(fp: Path) -> str:
    parts = set(fp.parts)
    if "sleep_on" in parts:
        return "sleep_on"
    if "sleep_off" in parts:
        return "sleep_off"
    return "unknown"


def parse_meta(fp: Path) -> Tuple[Optional[int], Optional[int], str]:
    """
    Returns: (cond_id, adv_interval_ms, sleep_tag)
    sleep_tag is one of: on/off/unk
    """
    try:
        with fp.open("r", encoding="utf-8", errors="ignore") as f:
            for _ in range(12):
                line = f.readline()
                if not line:
                    break
                if line.startswith("# meta,"):
                    cond_id = None
                    adv_ms = None
                    sleep_tag = "unk"
                    m = re.search(r"cond_id=(\d+)", line)
                    if m:
                        cond_id = int(m.group(1))
                    m = re.search(r"adv_interval_ms=(\d+)", line)
                    if m:
                        adv_ms = int(m.group(1))
                    m = re.search(r"sleep=([^,\s]+)", line)
                    if m:
                        sleep_tag = m.group(1)
                    return cond_id, adv_ms, sleep_tag
    except OSError:
        pass
    return None, None, "unk"


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

    cond_id, adv_ms_meta, sleep_tag = parse_meta(fp)
    if sleep_tag == "on":
        condition = "sleep_on"
    elif sleep_tag == "off":
        condition = "sleep_off"
    else:
        condition = infer_condition_from_path(fp)

    interval_ms = adv_ms_meta if adv_ms_meta and adv_ms_meta > 0 else infer_interval_ms_from_path(fp)

    return Trial(
        run=infer_run(fp),
        condition=condition,
        interval_ms=interval_ms,
        cond_id=cond_id,
        path=str(fp),
        ms_total=ms_total,
        mean_p_mw=mean_p,
        mean_v=mean_v,
        mean_i=mean_i,
        samples=samples,
        ok=ok,
    )


def save_plot(summary_df: pd.DataFrame, out_png: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 4.0), dpi=160)
    for (run, cond), sub in summary_df.groupby(["run", "condition"]):
        sub = sub.sort_values("interval_ms")
        x = sub["interval_ms"].astype(int).to_list()
        y = sub["mean_mean_p_mw"].to_list()
        yerr = sub["std_mean_p_mw"].to_list()
        ax.errorbar(x, y, yerr=yerr, fmt="o-", capsize=4, label=f"{run}:{cond}")
    ax.set_xlabel("ADV interval (ms)")
    ax.set_ylabel("TX power mean_p (mW)")
    ax.set_title("sleep_eval_scan90: TXSD mean power (per trial)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png)
    plt.close(fig)


def write_dod(summary_df: pd.DataFrame, report_md: Path, data_root: Path, summary_csv: Path) -> None:
    lines = [
        "# sleep_eval_scan90: difference-of-differences",
        "",
        f"Source: `{data_root}`",
        f"Summary: `{summary_csv}`",
        "",
    ]
    for run in sorted(summary_df["run"].unique()):
        sub = summary_df[summary_df["run"] == run]
        lines.append(f"## run: {run}")
        pivot = sub.pivot(index="interval_ms", columns="condition", values="mean_mean_p_mw")
        if "sleep_on" in pivot.columns and "sleep_off" in pivot.columns:
            def get(i: int, c: str) -> Optional[float]:
                if i not in pivot.index or c not in pivot.columns:
                    return None
                v = pivot.loc[i, c]
                return None if pd.isna(v) else float(v)

            p100_off = get(100, "sleep_off")
            p100_on = get(100, "sleep_on")
            p2000_off = get(2000, "sleep_off")
            p2000_on = get(2000, "sleep_on")
            if None not in (p100_off, p100_on, p2000_off, p2000_on):
                eff_100 = p100_off - p100_on
                eff_2000 = p2000_off - p2000_on
                dod = eff_2000 - eff_100
                lines += [
                    f"- P(100,OFF)={p100_off:.2f}, P(100,ON)={p100_on:.2f}, sleep_effect@100={eff_100:.2f}",
                    f"- P(2000,OFF)={p2000_off:.2f}, P(2000,ON)={p2000_on:.2f}, sleep_effect@2000={eff_2000:.2f}",
                    f"- DoD = {dod:.2f}",
                    "",
                ]
            else:
                lines += ["- Missing interval rows (need 100/2000 for both conditions).", ""]
        else:
            lines += ["- Missing both sleep_on and sleep_off (need both for DoD).", ""]
    report_md.write_text("\n".join(lines), encoding="utf-8")


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
    plots_dir = base / "plots"
    if args.run:
        metrics_dir = metrics_dir / args.run
        plots_dir = plots_dir / args.run

    txsd_files = sorted(data_root.glob("**/TX/trial_*.csv"))
    trials = [parse_footer(fp) for fp in txsd_files]
    df = pd.DataFrame([t.__dict__ for t in trials])
    if args.run:
        df = df[df["run"] == args.run].copy()

    metrics_dir.mkdir(parents=True, exist_ok=True)

    trials_csv = metrics_dir / "txsd_power_trials.csv"
    with trials_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "run",
                "condition",
                "interval_ms",
                "cond_id",
                "path",
                "ok",
                "ms_total",
                "samples",
                "mean_p_mw",
                "mean_v",
                "mean_i",
            ]
        )
        for _, r in df.iterrows():
            w.writerow(
                [
                    r.get("run"),
                    r.get("condition"),
                    r.get("interval_ms"),
                    r.get("cond_id"),
                    r.get("path"),
                    int(r.get("ok")),
                    r.get("ms_total"),
                    r.get("samples"),
                    r.get("mean_p_mw"),
                    r.get("mean_v"),
                    r.get("mean_i"),
                ]
            )

    ok_df = df[df["ok"] == True].copy()
    ok_df = ok_df[ok_df["condition"].isin(["sleep_on", "sleep_off"])].copy()
    ok_df = ok_df[ok_df["ms_total"].fillna(0) >= args.min_ms_total].copy()
    if ok_df.empty:
        raise SystemExit("No complete TXSD trials found (missing '# summary'/'# diag').")

    summary = (
        ok_df.groupby(["run", "condition", "interval_ms"])
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

    plot_png = plots_dir / "txsd_power_summary.png"
    save_plot(summary, plot_png)

    report_md = metrics_dir / "txsd_power_diff.md"
    write_dod(summary, report_md, data_root, summary_csv)

    print(f"wrote {trials_csv}")
    print(f"wrote {summary_csv}")
    print(f"wrote {plot_png}")
    print(f"wrote {report_md}")


if __name__ == "__main__":
    main()
