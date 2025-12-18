#!/usr/bin/env python3
"""
Single-figure overview to fix the narrative in one plot:

  - Role of U: U-shuffle collapses toward 100ms behavior (power↑)
  - Role of CCS: CCS-off (U-only) degrades QoS at ~same power vs U+CCS
  - Robustness: scan70 degrades Fixed500 strongly, while Policy remains feasible

Inputs are per-experiment summary_by_condition.csv files (no external deps).
Output is dependency-free SVG.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Point:
    key: str
    label: str
    x: float
    y: float
    xerr: float
    yerr: float
    color: str
    shape: str  # "circle" | "square" | "triangle" | "diamond"


def f_or_none(v: str) -> Optional[float]:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except Exception:
        return None


def read_summary(path: Path) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    with path.open(newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            cond = (row.get("condition") or "").strip()
            if not cond:
                continue
            x = f_or_none(row.get("avg_power_mW_mean") or "")
            y = f_or_none(row.get("pout_1s_mean") or "")
            if x is None or y is None:
                continue
            out[cond] = {
                "x": float(x),
                "y": float(y),
                "xerr": float(f_or_none(row.get("avg_power_mW_std") or "") or 0.0),
                "yerr": float(f_or_none(row.get("pout_1s_std") or "") or 0.0),
            }
    return out


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


def _fmt_tick(v: float, digits: int = 2) -> str:
    if math.isnan(v) or math.isinf(v):
        return "NA"
    if digits <= 0:
        return f"{v:.0f}"
    s = f"{v:.{digits}f}"
    return s.rstrip("0").rstrip(".")


def _draw_marker(shape: str, cx: float, cy: float, color: str) -> str:
    if shape == "square":
        return f'<rect x="{cx-6:.2f}" y="{cy-6:.2f}" width="12" height="12" fill="{color}" opacity="0.95"/>'
    if shape == "triangle":
        return f'<polygon points="{cx:.2f},{cy-7:.2f} {cx-6.5:.2f},{cy+6:.2f} {cx+6.5:.2f},{cy+6:.2f}" fill="{color}" opacity="0.95"/>'
    if shape == "diamond":
        return f'<polygon points="{cx:.2f},{cy-7:.2f} {cx-7:.2f},{cy:.2f} {cx:.2f},{cy+7:.2f} {cx+7:.2f},{cy:.2f}" fill="{color}" opacity="0.95"/>'
    return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="6" fill="{color}" opacity="0.95"/>'


def write_svg(out_svg: Path, title: str, points: List[Point], arrows: List[Tuple[str, str, str]]) -> None:
    width, height = 980, 640
    ml, mr, mt, mb = 80, 20, 60, 65
    pw, ph = width - ml - mr, height - mt - mb
    axis = "#111827"
    grid = "#e5e7eb"
    bg = "#ffffff"

    # Axis bounds + ticks (fixed & "nice" to avoid awkward steps).
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    xerrs = [p.xerr for p in points]
    yerrs = [p.yerr for p in points]
    # Use round axis bounds so tick marks align with plot edges.
    # NOTE: x error bars are omitted in this overview to keep the frame clean.
    xmin, xmax = 185.0, 210.0
    ymin, ymax = 0.0, 0.35
    x_ticks = [185, 190, 195, 200, 205, 210]
    y_ticks = [i * 0.05 for i in range(int(round(ymax / 0.05)) + 1)]

    def xpx(x: float) -> float:
        return ml + (x - xmin) * pw / (xmax - xmin) if xmax > xmin else ml + pw / 2

    def ypx(y: float) -> float:
        return mt + (ymax - y) * ph / (ymax - ymin) if ymax > ymin else mt + ph / 2

    svg: List[str] = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append(f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{axis}"/></marker></defs>')
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>')
    svg.append(f'<text x="{width/2:.1f}" y="38" font-size="20" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(title)}</text>')
    svg.append(f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" fill="none" stroke="{axis}" stroke-width="1.2"/>')

    for tx in x_ticks:
        px = xpx(tx)
        svg.append(f'<line x1="{px:.2f}" y1="{mt}" x2="{px:.2f}" y2="{mt+ph}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{px:.2f}" y="{mt+ph+26}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt_tick(float(tx), 0)}</text>')
    for ty in y_ticks:
        py = ypx(ty)
        svg.append(f'<line x1="{ml}" y1="{py:.2f}" x2="{ml+pw}" y2="{py:.2f}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{ml-10}" y="{py+4:.2f}" font-size="12" text-anchor="end" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt_tick(ty, 2)}</text>')

    svg.append(f'<text x="{ml+pw/2:.1f}" y="{height-26}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">avg_power_mW (lower=better)</text>')
    svg.append(f'<text x="22" y="{mt+ph/2:.1f}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system" transform="rotate(-90 22 {mt+ph/2:.1f})">pout_1s (lower=better)</text>')

    # ε=0.1 guideline
    y_eps = 0.1
    if y_eps >= ymin and y_eps <= ymax:
        py = ypx(y_eps)
        svg.append(f'<line x1="{ml}" y1="{py:.2f}" x2="{ml+pw}" y2="{py:.2f}" stroke="#9ca3af" stroke-width="2" stroke-dasharray="6 4"/>')
        svg.append(f'<text x="{ml+pw-10}" y="{py-8:.2f}" font-size="12" text-anchor="end" fill="#6b7280" font-family="ui-sans-serif, system-ui, -apple-system">ε=0.1</text>')

    # Index points by key for arrows.
    by_key: Dict[str, Point] = {p.key: p for p in points}

    # Arrows (behind points)
    for src, dst, text in arrows:
        ps = by_key.get(src)
        pd = by_key.get(dst)
        if ps is None or pd is None:
            continue
        x1, y1 = xpx(ps.x), ypx(ps.y)
        x2, y2 = xpx(pd.x), ypx(pd.y)
        svg.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{axis}" stroke-width="2" marker-end="url(#arrow)" opacity="0.85"/>')
        if text:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            svg.append(f'<text x="{mx+6:.2f}" y="{my-6:.2f}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(text)}</text>')

    label_cfg = {
        # dx, dy, anchor
        "scan70_fixed500": (10, -10, "start"),
        "scan90_fixed500": (10, -10, "start"),
        "scan70_policy": (12, -8, "start"),
        "scan90_policy": (12, 22, "start"),
        "scan90_ccs_off": (12, -8, "start"),
        "scan90_fixed100": (-12, -10, "end"),
        "scan70_fixed100": (-12, 18, "end"),
        "scan90_u_shuf": (-12, 18, "end"),
    }
    label_style = 'style="paint-order: stroke; stroke: #ffffff; stroke-width: 4px; stroke-linejoin: round;"'

    # Points + error bars
    for p in points:
        px, py = xpx(p.x), ypx(p.y)
        # error bars (vertical only; omit horizontal to keep the overview uncluttered)
        svg.append(f'<line x1="{px:.2f}" y1="{ypx(p.y-p.yerr):.2f}" x2="{px:.2f}" y2="{ypx(p.y+p.yerr):.2f}" stroke="{p.color}" stroke-width="2" opacity="0.9"/>')
        svg.append(_draw_marker(p.shape, px, py, p.color))
        if p.key in label_cfg:
            dx, dy, anchor = label_cfg[p.key]
            svg.append(
                f'<text x="{px+dx:.2f}" y="{py+dy:.2f}" font-size="12" text-anchor="{anchor}" fill="{axis}" {label_style} font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(p.label)}</text>'
            )

    # Legend
    lx, ly = ml + pw - 250, mt + 10
    svg.append(f'<rect x="{lx-6}" y="{ly-6}" width="240" height="128" fill="#ffffff" stroke="{grid}" stroke-width="1"/>')
    legend = [
        ("scan90 fixed", "#3b82f6", "square"),
        ("scan90 policy", "#10b981", "circle"),
        ("scan90 ablation", "#f59e0b", "triangle"),
        ("scan70 (worse RX)", "#111827", "diamond"),
    ]
    for i, (name, color, shape) in enumerate(legend):
        cy = ly + 18 + i * 28
        svg.append(_draw_marker(shape, lx + 12, cy, color))
        svg.append(f'<text x="{lx+28}" y="{cy+5}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(name)}</text>')

    svg.append("</svg>\n")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(svg), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--d4-csv", type=Path, default=Path("uccs_d4_scan90/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--d4b-csv", type=Path, default=Path("uccs_d4b_scan90/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--d3-csv", type=Path, default=Path("uccs_d3_scan70/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", type=str, default="Role separation overview (scan90/scan70, S4)")
    args = ap.parse_args()

    d4 = read_summary(args.d4_csv)
    d4b = read_summary(args.d4b_csv)
    d3 = read_summary(args.d3_csv)

    pts: List[Point] = []
    # scan90 fixed points (use D4B fixed values for consistency with CCS-off run)
    pts.append(Point("scan90_fixed100", "fixed100 (90)", d4b["S4_fixed100"]["x"], d4b["S4_fixed100"]["y"], d4b["S4_fixed100"]["xerr"], d4b["S4_fixed100"]["yerr"], "#3b82f6", "square"))
    pts.append(Point("scan90_fixed500", "fixed500 (90)", d4b["S4_fixed500"]["x"], d4b["S4_fixed500"]["y"], d4b["S4_fixed500"]["xerr"], d4b["S4_fixed500"]["yerr"], "#3b82f6", "square"))

    # scan90 policy (U+CCS): use D4B policy point (same definition)
    pts.append(Point("scan90_policy", "policy (90)", d4b["S4_policy"]["x"], d4b["S4_policy"]["y"], d4b["S4_policy"]["xerr"], d4b["S4_policy"]["yerr"], "#10b981", "circle"))

    # scan90 ablations
    pts.append(Point("scan90_u_shuf", "U-shuf", d4["S4_ablation_u_shuf"]["x"], d4["S4_ablation_u_shuf"]["y"], d4["S4_ablation_u_shuf"]["xerr"], d4["S4_ablation_u_shuf"]["yerr"], "#f59e0b", "triangle"))
    pts.append(Point("scan90_ccs_off", "CCS-off", d4b["S4_ablation_ccs_off"]["x"], d4b["S4_ablation_ccs_off"]["y"], d4b["S4_ablation_ccs_off"]["xerr"], d4b["S4_ablation_ccs_off"]["yerr"], "#f59e0b", "triangle"))

    # scan70 robustness (D3): fixed100/fixed500/policy
    pts.append(Point("scan70_fixed100", "fixed100 (70)", d3["S4_fixed100"]["x"], d3["S4_fixed100"]["y"], d3["S4_fixed100"]["xerr"], d3["S4_fixed100"]["yerr"], "#111827", "diamond"))
    pts.append(Point("scan70_fixed500", "fixed500 (70)", d3["S4_fixed500"]["x"], d3["S4_fixed500"]["y"], d3["S4_fixed500"]["xerr"], d3["S4_fixed500"]["yerr"], "#111827", "diamond"))
    pts.append(Point("scan70_policy", "policy (70)", d3["S4_policy"]["x"], d3["S4_policy"]["y"], d3["S4_policy"]["xerr"], d3["S4_policy"]["yerr"], "#111827", "diamond"))

    arrows = [
        ("scan90_u_shuf", "scan90_policy", ""),
        ("scan90_ccs_off", "scan90_policy", ""),
        ("scan90_fixed500", "scan70_fixed500", ""),
        ("scan90_policy", "scan70_policy", ""),
    ]

    write_svg(args.out, title=args.title, points=pts, arrows=arrows)


if __name__ == "__main__":
    main()
