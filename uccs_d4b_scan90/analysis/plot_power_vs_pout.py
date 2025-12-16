#!/usr/bin/env python3
"""
Plot Step D4B tradeoff: avg_power_mW vs pout_1s with share100 annotation (S4 only).
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Dict, Optional, Tuple


def f_or_none(v: str) -> Optional[float]:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except Exception:
        return None


def read_summary_by_condition(path: Path) -> Dict[str, Dict[str, Optional[float]]]:
    out: Dict[str, Dict[str, Optional[float]]] = {}
    with path.open(newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            cond = (row.get("condition") or "").strip()
            if not cond:
                continue
            out[cond] = {
                "pout_1s_mean": f_or_none(row.get("pout_1s_mean") or ""),
                "pout_1s_std": f_or_none(row.get("pout_1s_std") or ""),
                "avg_power_mW_mean": f_or_none(row.get("avg_power_mW_mean") or ""),
                "avg_power_mW_std": f_or_none(row.get("avg_power_mW_std") or ""),
                "adv_count_mean": f_or_none(row.get("adv_count_mean") or ""),
                "rx_share100_mean": f_or_none(row.get("rx_tag_share100_time_est_mean") or ""),
            }
    return out


def get_point(
    rows: Dict[str, Dict[str, Optional[float]]],
    key: str,
) -> Tuple[float, float, float, float, Optional[float], Optional[float]]:
    r = rows.get(key, {})
    x = r.get("avg_power_mW_mean")
    y = r.get("pout_1s_mean")
    if x is None or y is None:
        raise SystemExit(f"missing required metrics for {key} in summary csv")
    xerr = r.get("avg_power_mW_std") or 0.0
    yerr = r.get("pout_1s_std") or 0.0
    adv = r.get("adv_count_mean")
    rx_share = r.get("rx_share100_mean")
    return float(x), float(y), float(xerr), float(yerr), adv, rx_share


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-csv", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", type=str, default="")
    args = ap.parse_args()

    repo_root = Path.cwd()
    xdg_cache = repo_root / ".cache"
    xdg_cache.mkdir(exist_ok=True)
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache))
    mpl_dir = repo_root / ".mplconfig"
    mpl_dir.mkdir(exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore

    rows = read_summary_by_condition(args.summary_csv)

    k100 = "S4_fixed100"
    k500 = "S4_fixed500"
    kpol = "S4_policy"
    kubona = "S4_ablation_ccs_off"

    x100, y100, x100e, y100e, _, _ = get_point(rows, k100)
    x500, y500, x500e, y500e, _, _ = get_point(rows, k500)
    xpol, ypol, xpole, ypole, _, sh_pol = get_point(rows, kpol)
    xub, yub, xube, yube, _, sh_ub = get_point(rows, kubona)

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.errorbar([x100, x500], [y100, y500], xerr=[x100e, x500e], yerr=[y100e, y500e],
                fmt="s", ms=7, color="#1f77b4", capsize=3, linestyle="none", label="fixed")
    ax.errorbar([xpol], [ypol], xerr=[xpole], yerr=[ypole],
                fmt="o", ms=8, color="#ff7f0e", capsize=3, linestyle="none", label="policy (U+CCS)")
    ax.errorbar([xub], [yub], xerr=[xube], yerr=[yube],
                fmt="^", ms=8, color="#2ca02c", capsize=3, linestyle="none", label="ablation (U-only / CCS-off)")

    if sh_pol is not None:
        ax.annotate(f"share100≈{sh_pol:.2f}", (xpol, ypol), textcoords="offset points", xytext=(8, 8), ha="left", fontsize=10, color="#ff7f0e")
    if sh_ub is not None:
        ax.annotate(f"share100≈{sh_ub:.2f}", (xub, yub), textcoords="offset points", xytext=(8, 8), ha="left", fontsize=10, color="#2ca02c")

    ax.annotate("100", (x100, y100), textcoords="offset points", xytext=(6, -12), fontsize=9, color="#1f77b4")
    ax.annotate("500", (x500, y500), textcoords="offset points", xytext=(6, -12), fontsize=9, color="#1f77b4")

    ax.set_xlabel("avg_power_mW (TXSD)")
    ax.set_ylabel("pout_1s")
    ax.grid(True, alpha=0.25)
    if args.title:
        ax.set_title(args.title)
    ax.legend(loc="upper right", frameon=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    if args.out.suffix.lower() == ".png":
        fig.savefig(args.out.with_suffix(".pdf"))


if __name__ == "__main__":
    main()

