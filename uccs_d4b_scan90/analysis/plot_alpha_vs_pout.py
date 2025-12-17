#!/usr/bin/env python3
"""
Plot normalized power allocation α vs QoS (pout_1s) with per-run normalization.

α = (P - P500) / (P100 - P500)
  - P100: fixed100 avg_power_mW_mean within the same run
  - P500: fixed500 avg_power_mW_mean within the same run

This removes day-to-day drift and makes the "same energy allocation, better QoS"
story for CCS (D4B: U-only vs U+CCS) visually crisp.

Inputs: one or more summary_by_condition.csv files (no external deps).
Output: dependency-free SVG.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Row:
    cond: str
    pout_mean: float
    pout_std: float
    p_mean: float
    p_std: float


def f_or(v: Optional[str], default: float = 0.0) -> float:
    s = (v or "").strip()
    if not s:
        return default
    try:
        x = float(s)
    except Exception:
        return default
    if math.isnan(x) or math.isinf(x):
        return default
    return x


def read_summary(path: Path) -> Dict[str, Row]:
    out: Dict[str, Row] = {}
    with path.open(newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            cond = (row.get("condition") or "").strip()
            if not cond:
                continue
            out[cond] = Row(
                cond=cond,
                pout_mean=f_or(row.get("pout_1s_mean"), default=float("nan")),
                pout_std=f_or(row.get("pout_1s_std"), default=0.0),
                p_mean=f_or(row.get("avg_power_mW_mean"), default=float("nan")),
                p_std=f_or(row.get("avg_power_mW_std"), default=0.0),
            )
    return out


def compute_alpha(
    p: float,
    p_std: float,
    p100: float,
    p100_std: float,
    p500: float,
    p500_std: float,
) -> Tuple[float, float]:
    denom = (p100 - p500)
    if denom == 0 or math.isnan(denom) or math.isinf(denom):
        return float("nan"), float("nan")
    alpha = (p - p500) / denom
    # Simple error propagation (assume independence).
    # alpha = (p - p500)/d, d=(p100-p500)
    # dalpha/dp = 1/d
    # dalpha/dp500 = (-1)/d + (p-p500)/d^2
    # dalpha/dp100 = -(p-p500)/d^2
    d = denom
    a = (p - p500)
    da_dp = 1.0 / d
    da_dp500 = (-1.0 / d) + (a / (d * d))
    da_dp100 = -(a / (d * d))
    var = (da_dp * p_std) ** 2 + (da_dp500 * p500_std) ** 2 + (da_dp100 * p100_std) ** 2
    return alpha, math.sqrt(max(0.0, var))


def _svg_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _fmt(v: float, digits: int = 3) -> str:
    if math.isnan(v) or math.isinf(v):
        return "NA"
    return f"{v:.{digits}f}"


def _marker(shape: str, cx: float, cy: float, color: str) -> str:
    if shape == "diamond":
        return f'<polygon points="{cx:.2f},{cy-7:.2f} {cx-7:.2f},{cy:.2f} {cx:.2f},{cy+7:.2f} {cx+7:.2f},{cy:.2f}" fill="{color}" opacity="0.95"/>'
    if shape == "square":
        return f'<rect x="{cx-6:.2f}" y="{cy-6:.2f}" width="12" height="12" fill="{color}" opacity="0.95"/>'
    if shape == "triangle":
        return f'<polygon points="{cx:.2f},{cy-7:.2f} {cx-6.5:.2f},{cy+6:.2f} {cx+6.5:.2f},{cy+6:.2f}" fill="{color}" opacity="0.95"/>'
    return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="6" fill="{color}" opacity="0.95"/>'


@dataclass(frozen=True)
class Pt:
    key: str
    label: str
    alpha: float
    alpha_std: float
    pout: float
    pout_std: float
    color: str
    shape: str


def write_svg(out_svg: Path, title: str, pts: List[Pt]) -> None:
    width, height = 980, 620
    ml, mr, mt, mb = 90, 30, 70, 80
    pw, ph = width - ml - mr, height - mt - mb
    axis = "#111827"
    grid = "#e5e7eb"
    bg = "#ffffff"

    xs = [p.alpha for p in pts if not math.isnan(p.alpha)]
    ys = [p.pout for p in pts if not math.isnan(p.pout)]
    xerrs = [p.alpha_std for p in pts if not math.isnan(p.alpha)]
    yerrs = [p.pout_std for p in pts if not math.isnan(p.pout)]
    xmin = min(x - xe for x, xe in zip(xs, xerrs))
    xmax = max(x + xe for x, xe in zip(xs, xerrs))
    ymin = min(y - ye for y, ye in zip(ys, yerrs))
    ymax = max(y + ye for y, ye in zip(ys, yerrs))

    # α is conceptually [0,1], but allow a small margin.
    xmin = min(-0.05, xmin - 0.05)
    xmax = max(1.05, xmax + 0.05)
    ymin = max(0.0, ymin - 0.03)
    ymax += 0.03

    def xpx(x: float) -> float:
        return ml + (x - xmin) * pw / (xmax - xmin) if xmax > xmin else ml + pw / 2

    def ypx(y: float) -> float:
        return mt + (ymax - y) * ph / (ymax - ymin) if ymax > ymin else mt + ph / 2

    svg: List[str] = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>')
    svg.append(f'<text x="{width/2:.1f}" y="38" font-size="20" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(title)}</text>')
    svg.append(f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" fill="none" stroke="{axis}" stroke-width="1.2"/>')

    for i in range(6):
        tx = xmin + (xmax - xmin) * i / 5.0
        px = xpx(tx)
        svg.append(f'<line x1="{px:.2f}" y1="{mt}" x2="{px:.2f}" y2="{mt+ph}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{px:.2f}" y="{mt+ph+28}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(tx, 2)}</text>')
    for i in range(6):
        ty = ymin + (ymax - ymin) * i / 5.0
        py = ypx(ty)
        svg.append(f'<line x1="{ml}" y1="{py:.2f}" x2="{ml+pw}" y2="{py:.2f}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{ml-10}" y="{py+4:.2f}" font-size="12" text-anchor="end" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(ty, 3)}</text>')

    svg.append(f'<text x="{ml+pw/2:.1f}" y="{height-26}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">α=(P−P500)/(P100−P500)  (normalized power allocation)</text>')
    svg.append(f'<text x="22" y="{mt+ph/2:.1f}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system" transform="rotate(-90 22 {mt+ph/2:.1f})">pout_1s (lower=better)</text>')

    # δ=0.1 guideline (for D3 scan70 story)
    y_delta = 0.1
    if y_delta >= ymin and y_delta <= ymax:
        py = ypx(y_delta)
        svg.append(f'<line x1="{ml}" y1="{py:.2f}" x2="{ml+pw}" y2="{py:.2f}" stroke="#9ca3af" stroke-width="2" stroke-dasharray="6 4"/>')
        svg.append(f'<text x="{ml+pw-10}" y="{py-8:.2f}" font-size="12" text-anchor="end" fill="#6b7280" font-family="ui-sans-serif, system-ui, -apple-system">δ=0.1</text>')

    # points + error bars
    for p in pts:
        px, py = xpx(p.alpha), ypx(p.pout)
        svg.append(f'<line x1="{xpx(p.alpha-p.alpha_std):.2f}" y1="{py:.2f}" x2="{xpx(p.alpha+p.alpha_std):.2f}" y2="{py:.2f}" stroke="{p.color}" stroke-width="2" opacity="0.9"/>')
        svg.append(f'<line x1="{px:.2f}" y1="{ypx(p.pout-p.pout_std):.2f}" x2="{px:.2f}" y2="{ypx(p.pout+p.pout_std):.2f}" stroke="{p.color}" stroke-width="2" opacity="0.9"/>')
        svg.append(_marker(p.shape, px, py, p.color))
        svg.append(f'<text x="{px+10:.2f}" y="{py-10:.2f}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(p.label)}</text>')

    # legend
    lx, ly = ml + 10, mt + 10
    svg.append(f'<rect x="{lx-6}" y="{ly-6}" width="360" height="138" fill="#ffffff" stroke="{grid}" stroke-width="1"/>')
    legend = [
        ("fixed100/fixed500 (each run)", "#3b82f6", "square"),
        ("policy (U+CCS)", "#10b981", "circle"),
        ("ablation (U-shuf / CCS-off)", "#f59e0b", "triangle"),
        ("scan70 points", "#111827", "diamond"),
    ]
    for i, (name, color, shape) in enumerate(legend):
        cy = ly + 18 + i * 30
        svg.append(_marker(shape, lx + 12, cy, color))
        svg.append(f'<text x="{lx+28}" y="{cy+5}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(name)}</text>')

    svg.append("</svg>\n")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(svg), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--d4b", type=Path, default=Path("uccs_d4b_scan90/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--d4", type=Path, default=Path("uccs_d4_scan90/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--d3", type=Path, default=Path("uccs_d3_scan70/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", type=str, default="Normalized power allocation α vs QoS (S4)")
    args = ap.parse_args()

    d4b = read_summary(args.d4b)
    d4 = read_summary(args.d4)
    d3 = read_summary(args.d3)

    pts: List[Pt] = []

    # D4B scan90 normalization
    p100, p100s = d4b["S4_fixed100"].p_mean, d4b["S4_fixed100"].p_std
    p500, p500s = d4b["S4_fixed500"].p_mean, d4b["S4_fixed500"].p_std
    for cond, label, color, shape in [
        ("S4_fixed100", "scan90 fixed100", "#3b82f6", "square"),
        ("S4_fixed500", "scan90 fixed500", "#3b82f6", "square"),
        ("S4_policy", "scan90 policy (U+CCS)", "#10b981", "circle"),
        ("S4_ablation_ccs_off", "scan90 CCS-off (U-only)", "#f59e0b", "triangle"),
    ]:
        r = d4b[cond]
        a, astd = compute_alpha(r.p_mean, r.p_std, p100, p100s, p500, p500s)
        if cond == "S4_fixed100":
            a, astd = 1.0, 0.0
        if cond == "S4_fixed500":
            a, astd = 0.0, 0.0
        pts.append(Pt(f"d4b_{cond}", label, a, astd, r.pout_mean, r.pout_std, color, shape))

    # D4 scan90 (U-shuffle) normalization (use D4 fixed points)
    p100_d4, p100s_d4 = d4["S4_fixed100"].p_mean, d4["S4_fixed100"].p_std
    p500_d4, p500s_d4 = d4["S4_fixed500"].p_mean, d4["S4_fixed500"].p_std
    for cond, label, color in [
        ("S4_policy", "scan90 policy (D4)", "#10b981"),
        ("S4_ablation_u_shuf", "scan90 U-shuf", "#f59e0b"),
    ]:
        r = d4[cond]
        a, astd = compute_alpha(r.p_mean, r.p_std, p100_d4, p100s_d4, p500_d4, p500s_d4)
        pts.append(Pt(f"d4_{cond}", label, a, astd, r.pout_mean, r.pout_std, color, "triangle"))

    # D3 scan70 normalization (use D3 fixed points)
    p100_d3, p100s_d3 = d3["S4_fixed100"].p_mean, d3["S4_fixed100"].p_std
    p500_d3, p500s_d3 = d3["S4_fixed500"].p_mean, d3["S4_fixed500"].p_std
    for cond, label in [
        ("S4_fixed100", "scan70 fixed100",),
        ("S4_fixed500", "scan70 fixed500",),
        ("S4_policy", "scan70 policy",),
    ]:
        r = d3[cond]
        a, astd = compute_alpha(r.p_mean, r.p_std, p100_d3, p100s_d3, p500_d3, p500s_d3)
        if cond == "S4_fixed100":
            a, astd = 1.0, 0.0
        if cond == "S4_fixed500":
            a, astd = 0.0, 0.0
        pts.append(Pt(f"d3_{cond}", label, a, astd, r.pout_mean, r.pout_std, "#111827", "diamond"))

    write_svg(args.out, args.title, pts)


if __name__ == "__main__":
    main()

