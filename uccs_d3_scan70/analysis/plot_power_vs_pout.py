#!/usr/bin/env python3
"""
Plot Step D3 tradeoff: avg_power_mW vs pout_1s with share100 annotation (S4 only).
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
                "share100_power_mix_mean": f_or_none(row.get("share100_power_mix_mean") or ""),
            }
    return out


def compute_share100_from_adv(
    adv_count_policy: Optional[float],
    adv_count_fixed100: Optional[float],
    adv_count_fixed500: Optional[float],
) -> Optional[float]:
    if (
        adv_count_policy is None
        or adv_count_fixed100 is None
        or adv_count_fixed500 is None
        or adv_count_fixed100 <= adv_count_fixed500
    ):
        return None
    return (adv_count_policy - adv_count_fixed500) / (adv_count_fixed100 - adv_count_fixed500)


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

    x100, y100, x100e, y100e, adv100, _ = get_point(rows, k100)
    x500, y500, x500e, y500e, adv500, _ = get_point(rows, k500)
    xpol, ypol, xpole, ypole, advpol, rx_share_pol = get_point(rows, kpol)
    share_mix = rows.get(kpol, {}).get("share100_power_mix_mean")

    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    ax.errorbar([x100, x500], [y100, y500], xerr=[x100e, x500e], yerr=[y100e, y500e],
                fmt="s", ms=7, color="#1f77b4", capsize=3, linestyle="none", label="fixed")
    ax.errorbar([xpol], [ypol], xerr=[xpole], yerr=[ypole],
                fmt="o", ms=8, color="#ff7f0e", capsize=3, linestyle="none", label="policy (U+CCS)")

    share = share_mix if share_mix is not None else compute_share100_from_adv(advpol, adv100, adv500)
    if share is None:
        share = rx_share_pol
    if share is not None:
        ax.annotate(f"share100≈{share:.2f}", (xpol, ypol), textcoords="offset points", xytext=(8, 8), ha="left", fontsize=10, color="#ff7f0e")

    ax.annotate("100", (x100, y100), textcoords="offset points", xytext=(6, -12), fontsize=9, color="#1f77b4")
    ax.annotate("500", (x500, y500), textcoords="offset points", xytext=(6, -12), fontsize=9, color="#1f77b4")

    ax.set_xlabel("avg_power_mW (TXSD)")
    ax.set_ylabel("pout_1s")
    ax.grid(True, alpha=0.3)
    ax.set_title(args.title.strip() or f"{args.summary_csv.parent.name}: avg_power vs pout_1s (D3 scan70, S4)")
    ax.legend(loc="best", frameon=True, fontsize=9)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    if args.out.suffix.lower() == ".png":
        fig.savefig(args.out.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
