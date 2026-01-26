#!/usr/bin/env python3
"""
Generate paper-ready figures for stress_fixed (scan50/scan90, v4/v5 metrics).

Figures:
  - fig1_scan90_metrics_v4_v5.png:
      interval vs {pdr_unique, pout_1s, tl_p95_s, avg_power_mW} for S1/S4 (scan90), v4 vs v5 overlay.
  - fig3_scan50_vs_scan90_metrics.png:
      scan50 points + scan90 lines for {pdr_unique, pout_1s, tl_p95_s}.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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


def base_session(session: str) -> Optional[str]:
    m = re.search(r"(S\d+)", session)
    return m.group(1) if m else None


def load_agg(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            rows.append(row)
    return rows


def filter_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for r in rows:
        sess = (r.get("session") or "").strip()
        interval = to_int(r.get("interval_ms", "0"))
        if not sess or interval <= 0:
            continue
        out.append(r)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Plot stress_fixed figures (v4/v5).")
    ap.add_argument(
        "--scan90-v4",
        type=Path,
        default=Path("results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv"),
    )
    ap.add_argument(
        "--scan90",
        type=Path,
        default=Path("results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v5.csv"),
    )
    ap.add_argument(
        "--scan50",
        type=Path,
        default=Path("results/stress_fixed/scan50/stress_causal_real_summary_1211_stress_agg_enriched_scan50_v5.csv"),
    )
    ap.add_argument("--out-dir", type=Path, default=Path("results/stress_fixed/figures_v5"))
    args = ap.parse_args()

    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as e:
        raise SystemExit(f"matplotlib is required: {e}")

    rows90_v5 = filter_rows(load_agg(args.scan90))
    rows90_v4 = filter_rows(load_agg(args.scan90_v4))
    rows50 = filter_rows(load_agg(args.scan50))

    # ------------------------------ #
    # Fig 1: scan90 metrics (v4 vs v5)
    # ------------------------------ #
    metrics = [
        ("pdr_unique_mean", "PDR (unique)"),
        ("pout_1s_mean", r"$P_{\mathrm{out}}(1\,\mathrm{s})$"),
        ("tl_p95_s_mean", "TL p95 (s)"),
        ("avg_power_mW_mean", "Average power (mW)"),
    ]

    intervals = sorted({to_int(r["interval_ms"]) for r in rows90_v5})
    sessions = sorted({(r.get("session") or "").strip() for r in rows90_v5})

    by_sess_int_v5: Dict[Tuple[str, int], Dict[str, str]] = {
        (r["session"], to_int(r["interval_ms"])): r for r in rows90_v5
    }
    by_sess_int_v4: Dict[Tuple[str, int], Dict[str, str]] = {
        (r["session"], to_int(r["interval_ms"])): r for r in rows90_v4
    }

    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    axes_list = [axes[0][0], axes[0][1], axes[1][0], axes[1][1]]

    colors = {"S1": "#1f77b4", "S4": "#ff7f0e"}
    for ax, (key, title) in zip(axes_list, metrics):
        for sess in sessions:
            xs = intervals
            ys_v4 = []
            ys_v5 = []
            for itv in xs:
                row4 = by_sess_int_v4.get((sess, itv))
                row5 = by_sess_int_v5.get((sess, itv))
                ys_v4.append(to_float(row4.get(key, "nan")) if row4 else float("nan"))
                ys_v5.append(to_float(row5.get(key, "nan")) if row5 else float("nan"))
            ax.plot(xs, ys_v4, linestyle="--", color=colors.get(sess, None), alpha=0.8)
            ax.plot(xs, ys_v5, linestyle="-", marker="o", color=colors.get(sess, None))
        ax.set_ylabel(title)
        ax.set_xticks(intervals)
        ax.set_xlabel("interval (ms)")
        if key == "tl_p95_s_mean":
            ax.set_yscale("log")
    axes[0][0].set_ylim(0, 1.05)
    axes[0][1].set_ylim(0, 1.05)

    from matplotlib.lines import Line2D

    session_handles = [
        Line2D([0], [0], color=colors.get("S1"), label="S1"),
        Line2D([0], [0], color=colors.get("S4"), label="S4"),
    ]
    version_handles = [
        Line2D([0], [0], color="#111827", linestyle="--", label="v4"),
        Line2D([0], [0], color="#111827", linestyle="-", label="v5"),
    ]
    axes[0][0].legend(handles=session_handles + version_handles, loc="lower right", fontsize=8)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out1 = args.out_dir / "fig1_scan90_metrics_v4_v5.png"
    fig.tight_layout()
    fig.savefig(out1, dpi=200)

    # ------------------------------ #
    # Fig 3: scan50 vs scan90 (pdr_unique / pout_1s / tl_p95)
    # ------------------------------ #
    fig2, axes2 = plt.subplots(3, 1, figsize=(7, 9), sharex=True)
    compare_metrics = [
        ("pdr_unique_mean", "PDR (unique)"),
        ("pout_1s_mean", r"$P_{\mathrm{out}}(1\,\mathrm{s})$"),
        ("tl_p95_s_mean", "TL p95 (s)"),
    ]

    for ax, (key, ylabel) in zip(axes2, compare_metrics):
        # scan90 lines (base sessions only)
        for sess in sessions:
            xs = intervals
            ys = [to_float(by_sess_int_v5.get((sess, itv), {}).get(key, "0")) for itv in xs]
            ax.plot(xs, ys, marker="o", linewidth=2, label=f"scan90 {sess}", color=colors.get(sess, None))

        # scan50 points (include variants; colored by base session)
        for r in rows50:
            sess50 = (r.get("session") or "").strip()
            b = base_session(sess50) or sess50
            itv = to_int(r.get("interval_ms", "0"))
            y = to_float(r.get(key, "0"))
            ax.scatter([itv], [y], marker="x", s=60, color=colors.get(b, "#666666"), alpha=0.7)

        ax.set_ylabel(ylabel)
        if key in ("pdr_unique_mean", "pout_1s_mean"):
            ax.set_ylim(0, 1.05)
        if key == "tl_p95_s_mean":
            ax.set_yscale("log")
        ax.set_xticks(intervals)
        ax.grid(True, alpha=0.3)

    axes2[-1].set_xlabel("interval (ms)")
    axes2[0].legend(loc="lower right", fontsize=8)

    out3 = args.out_dir / "fig3_scan50_vs_scan90_metrics.png"
    fig2.tight_layout()
    fig2.savefig(out3, dpi=200)

    print(f"[INFO] wrote {out1}")
    print(f"[INFO] wrote {out3}")


if __name__ == "__main__":
    main()
