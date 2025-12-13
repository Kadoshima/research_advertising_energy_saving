#!/usr/bin/env python3
"""
Generate paper-ready figures for stress_fixed (scan50/scan90, v5 metrics).

Figures:
  - fig1_scan90_metrics.png:
      interval vs {pdr_unique, pout_1s, tl_mean_s, E_per_adv_uJ, avg_power_mW} for S1/S4 (scan90).
  - fig3_scan50_vs_scan90_pdr_unique.png:
      pdr_unique points (scan50) + lines (scan90) to highlight scan duty effect (esp. 100ms).
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
    with path.open() as f:
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
    ap = argparse.ArgumentParser(description="Plot stress_fixed figures (v5).")
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

    rows90 = filter_rows(load_agg(args.scan90))
    rows50 = filter_rows(load_agg(args.scan50))

    # ------------------------------ #
    # Fig 1: scan90 metrics
    # ------------------------------ #
    metrics = [
        ("pdr_unique_mean", "PDR (unique)"),
        ("pout_1s_mean", "Pout(1s)"),
        ("tl_mean_s_mean", "TL mean (s)"),
        ("E_per_adv_uJ_mean", "E/adv (uJ)"),
        ("avg_power_mW_mean", "avg power (mW)"),
    ]

    intervals = sorted({to_int(r["interval_ms"]) for r in rows90})
    sessions = sorted({(r.get("session") or "").strip() for r in rows90})

    # session -> interval -> row
    by_sess_int: Dict[Tuple[str, int], Dict[str, str]] = {(r["session"], to_int(r["interval_ms"])): r for r in rows90}

    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    axes_list = [axes[0][0], axes[0][1], axes[0][2], axes[1][0], axes[1][1]]
    fig.delaxes(axes[1][2])

    colors = {"S1": "#1f77b4", "S4": "#ff7f0e"}
    for ax, (key, title) in zip(axes_list, metrics):
        for sess in sessions:
            xs = intervals
            ys = []
            for itv in xs:
                row = by_sess_int.get((sess, itv))
                ys.append(to_float(row.get(key, "0")) if row else 0.0)
            ax.plot(xs, ys, marker="o", label=sess, color=colors.get(sess, None))
        ax.set_title(title)
        ax.set_xticks(intervals)
        ax.set_xlabel("interval_ms")
        if key in ("E_per_adv_uJ_mean", "tl_mean_s_mean"):
            ax.set_yscale("log")
    axes[0][0].set_ylim(0, 1.05)
    axes[0][1].set_ylim(0, 1.05)
    axes[0][0].legend(loc="lower right")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out1 = args.out_dir / "fig1_scan90_metrics.png"
    fig.tight_layout()
    fig.savefig(out1, dpi=200)

    # ------------------------------ #
    # Fig 3: scan50 vs scan90 (pdr_unique)
    # ------------------------------ #
    fig2, ax = plt.subplots(figsize=(8, 4.5))

    # scan90 lines (base sessions only)
    for sess in sessions:
        xs = intervals
        ys = [to_float(by_sess_int.get((sess, itv), {}).get("pdr_unique_mean", "0")) for itv in xs]
        ax.plot(xs, ys, marker="o", linewidth=2, label=f"scan90 {sess}", color=colors.get(sess, None))

    # scan50 points (include variants; colored by base session)
    for r in rows50:
        sess50 = (r.get("session") or "").strip()
        b = base_session(sess50) or sess50
        itv = to_int(r.get("interval_ms", "0"))
        y = to_float(r.get("pdr_unique_mean", "0"))
        ax.scatter([itv], [y], marker="x", s=60, color=colors.get(b, "#666666"), alpha=0.7)
        if itv == 100 and b in ("S1", "S4"):
            ax.annotate(sess50, (itv, y), xytext=(5, 5), textcoords="offset points", fontsize=8)

    ax.set_title("scan50 vs scan90: pdr_unique (stress_fixed)")
    ax.set_xlabel("interval_ms")
    ax.set_ylabel("pdr_unique")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(intervals)
    ax.legend(loc="lower right")

    out3 = args.out_dir / "fig3_scan50_vs_scan90_pdr_unique.png"
    fig2.tight_layout()
    fig2.savefig(out3, dpi=200)

    print(f"[INFO] wrote {out1}")
    print(f"[INFO] wrote {out3}")


if __name__ == "__main__":
    main()
