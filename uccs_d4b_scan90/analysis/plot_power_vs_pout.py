#!/usr/bin/env python3
"""
Plot Step D4B tradeoff: avg_power_mW vs pout_1s with share100 annotation (S4 only).

This script prefers matplotlib, but falls back to a dependency-free SVG output when
matplotlib is not available in the current Python environment.
"""

from __future__ import annotations

import argparse
import csv
import math
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


def get_point(
    rows: Dict[str, Dict[str, Optional[float]]],
    key: str,
) -> Tuple[float, float, float, float, Optional[float], Optional[float], Optional[float]]:
    r = rows.get(key, {})
    x = r.get("avg_power_mW_mean")
    y = r.get("pout_1s_mean")
    if x is None or y is None:
        raise SystemExit(f"missing required metrics for {key} in summary csv")
    xerr = r.get("avg_power_mW_std") or 0.0
    yerr = r.get("pout_1s_std") or 0.0
    adv = r.get("adv_count_mean")
    rx_share = r.get("rx_share100_mean")
    mix_share = r.get("share100_power_mix_mean")
    return float(x), float(y), float(xerr), float(yerr), adv, rx_share, mix_share


def _svg_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _fmt(v: Optional[float], digits: int = 3) -> str:
    if v is None:
        return "NA"
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return "NA"
    return f"{v:.{digits}f}"


def _write_svg(
    out_path: Path,
    title: str,
    points: Dict[str, Dict[str, float]],
    x_label: str,
    y_label: str,
) -> None:
    width = 900
    height = 600
    margin_l = 90
    margin_r = 30
    margin_t = 60
    margin_b = 70
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    xs = [v["x"] for v in points.values()]
    ys = [v["y"] for v in points.values()]
    xerrs = [v["xerr"] for v in points.values()]
    yerrs = [v["yerr"] for v in points.values()]

    xmin = min(x - xe for x, xe in zip(xs, xerrs))
    xmax = max(x + xe for x, xe in zip(xs, xerrs))
    ymin = min(y - ye for y, ye in zip(ys, yerrs))
    ymax = max(y + ye for y, ye in zip(ys, yerrs))

    xpad = max(0.5, (xmax - xmin) * 0.08)
    ypad = max(0.002, (ymax - ymin) * 0.12)
    xmin -= xpad
    xmax += xpad
    ymin = max(0.0, ymin - ypad)
    ymax += ypad

    def x_to_px(x: float) -> float:
        if xmax <= xmin:
            return float(margin_l + plot_w / 2)
        return margin_l + (x - xmin) * plot_w / (xmax - xmin)

    def y_to_px(y: float) -> float:
        if ymax <= ymin:
            return float(margin_t + plot_h / 2)
        return margin_t + (ymax - y) * plot_h / (ymax - ymin)

    bg = "#ffffff"
    axis = "#111827"
    grid = "#e5e7eb"
    colors = {
        "S4_fixed100": "#ef4444",
        "S4_fixed500": "#3b82f6",
        "S4_policy": "#10b981",
        "S4_ablation_ccs_off": "#f59e0b",
    }

    svg_lines = []
    svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg_lines.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>')
    svg_lines.append(f'<text x="{width/2:.1f}" y="34" font-size="20" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(title)}</text>')
    svg_lines.append(f'<rect x="{margin_l}" y="{margin_t}" width="{plot_w}" height="{plot_h}" fill="none" stroke="{axis}" stroke-width="1.2"/>')

    for i in range(6):
        tx = xmin + (xmax - xmin) * i / 5.0
        px = x_to_px(tx)
        svg_lines.append(f'<line x1="{px:.2f}" y1="{margin_t}" x2="{px:.2f}" y2="{margin_t+plot_h}" stroke="{grid}" stroke-width="1"/>')
        svg_lines.append(f'<text x="{px:.2f}" y="{margin_t+plot_h+24}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(tx, 1)}</text>')
    for i in range(6):
        ty = ymin + (ymax - ymin) * i / 5.0
        py = y_to_px(ty)
        svg_lines.append(f'<line x1="{margin_l}" y1="{py:.2f}" x2="{margin_l+plot_w}" y2="{py:.2f}" stroke="{grid}" stroke-width="1"/>')
        svg_lines.append(f'<text x="{margin_l-10}" y="{py+4:.2f}" font-size="12" text-anchor="end" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(ty, 3)}</text>')

    svg_lines.append(f'<text x="{margin_l+plot_w/2:.1f}" y="{height-24}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(x_label)}</text>')
    svg_lines.append(f'<text x="22" y="{margin_t+plot_h/2:.1f}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system" transform="rotate(-90 22 {margin_t+plot_h/2:.1f})">{_svg_escape(y_label)}</text>')

    for key, v in points.items():
        x = v["x"]
        y = v["y"]
        xerr = v["xerr"]
        yerr = v["yerr"]
        px = x_to_px(x)
        py = y_to_px(y)
        color = colors.get(key, "#111827")
        px_l = x_to_px(x - xerr)
        px_r = x_to_px(x + xerr)
        py_u = y_to_px(y + yerr)
        py_d = y_to_px(y - yerr)
        svg_lines.append(f'<line x1="{px_l:.2f}" y1="{py:.2f}" x2="{px_r:.2f}" y2="{py:.2f}" stroke="{color}" stroke-width="2" opacity="0.9"/>')
        svg_lines.append(f'<line x1="{px:.2f}" y1="{py_u:.2f}" x2="{px:.2f}" y2="{py_d:.2f}" stroke="{color}" stroke-width="2" opacity="0.9"/>')
        svg_lines.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="6" fill="{color}" opacity="0.95"/>')
        label = key.replace("S4_", "")
        note = f"{label} (adv={int(v['adv']) if v.get('adv') is not None else 'NA'}, share100_rx={_fmt(v.get('rx_share'), 3)}, share100_mix={_fmt(v.get('mix_share'), 3)})"
        svg_lines.append(f'<text x="{px+10:.2f}" y="{py-10:.2f}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(note)}</text>')

    svg_lines.append("</svg>\n")
    out_path.write_text("\n".join(svg_lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-csv", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", type=str, default="")
    args = ap.parse_args()

    rows = read_summary_by_condition(args.summary_csv)

    k100 = "S4_fixed100"
    k500 = "S4_fixed500"
    kpol = "S4_policy"
    kubona = "S4_ablation_ccs_off"

    x100, y100, x100e, y100e, adv100, rx100, mix100 = get_point(rows, k100)
    x500, y500, x500e, y500e, adv500, rx500, mix500 = get_point(rows, k500)
    xpol, ypol, xpole, ypole, advpol, rxpol, mixpol = get_point(rows, kpol)
    xub, yub, xube, yube, advub, rxub, mixub = get_point(rows, kubona)

    # Try matplotlib first.
    repo_root = Path.cwd()
    try:
        xdg_cache = repo_root / ".cache"
        xdg_cache.mkdir(exist_ok=True)
        os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache))
        mpl_dir = repo_root / ".mplconfig"
        mpl_dir.mkdir(exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir))

        import matplotlib  # type: ignore

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        # Dependency-free fallback.
        args.out.parent.mkdir(parents=True, exist_ok=True)
        _write_svg(
            args.out.with_suffix(".svg"),
            title=args.title or "D4B scan90 (S4): CCS-off ablation",
            points={
                "S4_fixed100": {"x": x100, "y": y100, "xerr": x100e, "yerr": y100e, "adv": adv100 or 0.0, "rx_share": rx100 or float("nan"), "mix_share": mix100 or float("nan")},
                "S4_fixed500": {"x": x500, "y": y500, "xerr": x500e, "yerr": y500e, "adv": adv500 or 0.0, "rx_share": rx500 or float("nan"), "mix_share": mix500 or float("nan")},
                "S4_policy": {"x": xpol, "y": ypol, "xerr": xpole, "yerr": ypole, "adv": advpol or 0.0, "rx_share": rxpol or float("nan"), "mix_share": mixpol or float("nan")},
                "S4_ablation_ccs_off": {"x": xub, "y": yub, "xerr": xube, "yerr": yube, "adv": advub or 0.0, "rx_share": rxub or float("nan"), "mix_share": mixub or float("nan")},
            },
            x_label="avg_power_mW (mean±std)",
            y_label="pout_1s (mean±std)",
        )
        return

    fig, ax = plt.subplots(figsize=(7.6, 5.0), dpi=160)
    ax.errorbar([x100], [y100], xerr=[x100e], yerr=[y100e], fmt="s", ms=7, color="#ef4444", capsize=3, linestyle="none", label="fixed100")
    ax.errorbar([x500], [y500], xerr=[x500e], yerr=[y500e], fmt="s", ms=7, color="#3b82f6", capsize=3, linestyle="none", label="fixed500")
    ax.errorbar([xpol], [ypol], xerr=[xpole], yerr=[ypole], fmt="o", ms=8, color="#10b981", capsize=3, linestyle="none", label="policy (U+CCS)")
    ax.errorbar([xub], [yub], xerr=[xube], yerr=[yube], fmt="^", ms=8, color="#f59e0b", capsize=3, linestyle="none", label="ablation (U-only / CCS-off)")

    def annotate(x: float, y: float, name: str, adv: Optional[float], rx_share: Optional[float], mix_share: Optional[float]) -> None:
        adv_s = f"adv={int(adv)}" if adv is not None else "adv=NA"
        rx_s = f"share100_rx={rx_share:.2f}" if rx_share is not None else "share100_rx=NA"
        mix_s = f"share100_mix={mix_share:.2f}" if mix_share is not None else "share100_mix=NA"
        ax.annotate(f"{name}\n{adv_s}, {rx_s}, {mix_s}", (x, y), textcoords="offset points", xytext=(8, 8), ha="left", fontsize=8)

    annotate(x100, y100, "fixed100", adv100, rx100, mix100)
    annotate(x500, y500, "fixed500", adv500, rx500, mix500)
    annotate(xpol, ypol, "policy", advpol, rxpol, mixpol)
    annotate(xub, yub, "ccs_off", advub, rxub, mixub)

    ax.set_xlabel("avg_power_mW (TXSD)")
    ax.set_ylabel("pout_1s")
    ax.grid(True, alpha=0.25)
    if args.title:
        ax.set_title(args.title)
    ax.legend(loc="best", fontsize=9, frameon=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    if args.out.suffix.lower() == ".png":
        fig.savefig(args.out.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
