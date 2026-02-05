#!/usr/bin/env python3
"""
Single-figure overview to fix the narrative in one plot:

  - Role of U: U-shuffle collapses toward 100ms behavior (power-heavy)
  - Role of CCS: CCS-off (U-only) degrades QoS at ~same power vs U+CCS
  - Robustness: scan70 degrades Fixed500 strongly, while Policy remains feasible

Inputs are per-experiment summary_by_condition.csv files (no external deps).
Output is dependency-free SVG/PNG.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
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


@dataclass(frozen=True)
class LabelPlacement:
    dx: float
    dy: float
    anchor: str  # "start" | "end" | "middle"
    box: Tuple[float, float, float, float]  # x0, y0, x1, y1 in px
    leader: bool


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
            pout = f_or_none(row.get("pout_1s_mean") or "")
            power = f_or_none(row.get("avg_power_mW_mean") or "")
            if pout is None or power is None:
                continue
            out[cond] = {
                "pout": float(pout),
                "power": float(power),
                "pout_err": float(f_or_none(row.get("pout_1s_std") or "") or 0.0),
                "power_err": float(f_or_none(row.get("avg_power_mW_std") or "") or 0.0),
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


def _estimate_text_box(text: str, font_size: float = 12.0, pad: float = 2.0) -> Tuple[float, float]:
    # Rough width estimate for short ASCII labels.
    width = max(1.0, 0.6 * font_size * len(text)) + pad * 2
    height = font_size + pad * 2
    return width, height


def _rect_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    x0 = max(ax0, bx0)
    y0 = max(ay0, by0)
    x1 = min(ax1, bx1)
    y1 = min(ay1, by1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


def _closest_point_on_rect(px: float, py: float, rect: Tuple[float, float, float, float]) -> Tuple[float, float]:
    x0, y0, x1, y1 = rect
    cx = min(max(px, x0), x1)
    cy = min(max(py, y0), y1)
    return cx, cy


def _auto_place_labels(
    points: List[Point],
    label_keys: List[str],
    xpx,
    ypx,
    bounds: Tuple[float, float, float, float],
    font_size: float = 12.0,
) -> Dict[str, LabelPlacement]:
    # Greedy collision avoidance in pixel space.
    ml, mt, mr, mb = bounds
    placements: Dict[str, LabelPlacement] = {}
    obstacles: List[Tuple[float, float, float, float]] = []

    # Avoid placing labels on top of point markers.
    for p in points:
        px, py = xpx(p.x), ypx(p.y)
        obstacles.append((px - 8, py - 8, px + 8, py + 8))

    label_points = [p for p in points if p.key in label_keys]
    label_points.sort(key=lambda p: (ypx(p.y), xpx(p.x)))

    offsets = [
        (12, -12, "start"),
        (12, 12, "start"),
        (12, -28, "start"),
        (12, 28, "start"),
        (-12, -12, "end"),
        (-12, 12, "end"),
        (-12, -28, "end"),
        (-12, 28, "end"),
        (0, -18, "middle"),
        (0, 22, "middle"),
        (24, 0, "start"),
        (-24, 0, "end"),
        (36, -8, "start"),
        (-36, -8, "end"),
    ]

    def make_box(px: float, py: float, dx: float, dy: float, anchor: str, text: str) -> Tuple[float, float, float, float]:
        w, h = _estimate_text_box(text, font_size=font_size)
        tx = px + dx
        ty = py + dy
        if anchor == "start":
            x0, x1 = tx, tx + w
        elif anchor == "end":
            x0, x1 = tx - w, tx
        else:
            x0, x1 = tx - w / 2, tx + w / 2
        y0, y1 = ty - h, ty
        return x0, y0, x1, y1

    for p in label_points:
        px, py = xpx(p.x), ypx(p.y)
        best = None
        best_score = float("inf")
        for dx, dy, anchor in offsets:
            box = make_box(px, py, dx, dy, anchor, p.label)
            x0, y0, x1, y1 = box
            # Out-of-bounds area penalty
            out_x0 = max(0.0, ml - x0)
            out_y0 = max(0.0, mt - y0)
            out_x1 = max(0.0, x1 - mr)
            out_y1 = max(0.0, y1 - mb)
            out_area = (out_x0 + out_x1) * (y1 - y0) + (out_y0 + out_y1) * (x1 - x0)

            overlap = 0.0
            for ob in obstacles:
                overlap += _rect_overlap(box, ob)

            dist = abs(dx) + abs(dy)
            score = overlap * 10.0 + out_area * 50.0 + dist * 0.2
            if score < best_score:
                best_score = score
                best = (dx, dy, anchor, box)
            if overlap == 0.0 and out_area == 0.0:
                best = (dx, dy, anchor, box)
                break

        if best is None:
            continue
        dx, dy, anchor, box = best
        obstacles.append(box)
        # Leader if moved far from point
        bx0, by0, bx1, by1 = box
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        leader = math.hypot(cx - px, cy - py) > 18.0
        placements[p.key] = LabelPlacement(dx=dx, dy=dy, anchor=anchor, box=box, leader=leader)

    return placements


def write_svg(out_svg: Path, title: str, points: List[Point], arrows: List[Tuple[str, str, str]]) -> None:
    width, height = 980, 640
    ml, mr, mt, mb = 80, 20, 60, 65
    pw, ph = width - ml - mr, height - mt - mb
    axis = "#111827"
    grid = "#e5e7eb"
    bg = "#ffffff"

    # Axis bounds + ticks (X=avg_power, Y=P_out).
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    xerrs = [p.xerr for p in points]
    yerrs = [p.yerr for p in points]

    # X (avg_power) range is auto-scaled.
    x_min = min(x - xe for x, xe in zip(xs, xerrs))
    x_max = max(x + xe for x, xe in zip(xs, xerrs))
    x_pad = max(5.0, (x_max - x_min) * 0.1)
    xmin = math.floor((x_min - x_pad) / 5.0) * 5.0
    xmax = math.ceil((x_max + x_pad) / 5.0) * 5.0
    xmin = min(xmin, 185.0)

    x_span = xmax - xmin
    if x_span <= 40:
        x_step = 5.0
    elif x_span <= 80:
        x_step = 10.0
    else:
        x_step = 20.0
    x_ticks = [xmin + i * x_step for i in range(int(round((xmax - xmin) / x_step)) + 1)]

    # Y (P_out) stays fixed for consistent eps=0.1 placement.
    ymin, ymax = 0.0, 0.35
    y_ticks = [i * 0.05 for i in range(int(round(ymax / 0.05)) + 1)]

    def xpx(x: float) -> float:
        return ml + (x - xmin) * pw / (xmax - xmin) if xmax > xmin else ml + pw / 2

    def ypx(y: float) -> float:
        return mt + (ymax - y) * ph / (ymax - ymin) if ymax > ymin else mt + ph / 2

    svg: List[str] = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append(f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{axis}"/></marker></defs>')
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>')
    if title:
        svg.append(f'<text x="{width/2:.1f}" y="38" font-size="20" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(title)}</text>')
    svg.append(f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" fill="none" stroke="{axis}" stroke-width="1.2"/>')

    for tx in x_ticks:
        px = xpx(tx)
        svg.append(f'<line x1="{px:.2f}" y1="{mt}" x2="{px:.2f}" y2="{mt+ph}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{px:.2f}" y="{mt+ph+26}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt_tick(float(tx), 2)}</text>')
    for ty in y_ticks:
        py = ypx(ty)
        svg.append(f'<line x1="{ml}" y1="{py:.2f}" x2="{ml+pw}" y2="{py:.2f}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{ml-10}" y="{py+4:.2f}" font-size="12" text-anchor="end" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt_tick(ty, 2)}</text>')

    svg.append(f'<text x="{ml+pw/2:.1f}" y="{height-26}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">avg_power_mW (lower=better)</text>')
    svg.append(f'<text x="22" y="{mt+ph/2:.1f}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system" transform="rotate(-90 22 {mt+ph/2:.1f})">pout_1s (lower=better)</text>')

    # eps=0.1 guideline (Pout constraint)
    y_eps = 0.1
    if y_eps >= ymin and y_eps <= ymax:
        py = ypx(y_eps)
        svg.append(f'<line x1="{ml}" y1="{py:.2f}" x2="{ml+pw}" y2="{py:.2f}" stroke="#9ca3af" stroke-width="2" stroke-dasharray="6 4"/>')
        svg.append(f'<text x="{ml+pw-6:.2f}" y="{py-6:.2f}" font-size="12" text-anchor="end" fill="#6b7280" font-family="ui-sans-serif, system-ui, -apple-system">eps=0.1</text>')

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
        svg.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{axis}" stroke-width="2" marker-end="url(#arrow)" opacity="0.35"/>')
        if text:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            svg.append(f'<text x="{mx+6:.2f}" y="{my-6:.2f}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(text)}</text>')

    label_keys = [
        "scan70_fixed500",
        "scan90_fixed500",
        "scan70_policy",
        "scan90_policy",
        "scan90_ccs_off",
        "scan90_fixed100",
        "scan70_fixed100",
        "scan90_u_shuf",
    ]
    placements = _auto_place_labels(points, label_keys, xpx, ypx, (ml, mt, ml + pw, mt + ph), font_size=12.0)
    label_style = 'style="paint-order: stroke; stroke: #ffffff; stroke-width: 4px; stroke-linejoin: round;"'

    # Points + error bars
    for p in points:
        px, py = xpx(p.x), ypx(p.y)
        # error bars (vertical only; omit horizontal to keep the overview uncluttered)
        svg.append(f'<line x1="{px:.2f}" y1="{ypx(p.y-p.yerr):.2f}" x2="{px:.2f}" y2="{ypx(p.y+p.yerr):.2f}" stroke="{p.color}" stroke-width="2" opacity="0.9"/>')
        svg.append(_draw_marker(p.shape, px, py, p.color))
        placement = placements.get(p.key)
        if placement:
            tx = px + placement.dx
            ty = py + placement.dy
            if placement.leader:
                cx, cy = _closest_point_on_rect(px, py, placement.box)
                svg.append(
                    f'<line x1="{px:.2f}" y1="{py:.2f}" x2="{cx:.2f}" y2="{cy:.2f}" stroke="{axis}" stroke-width="1.4" opacity="0.35"/>'
                )
            svg.append(
                f'<text x="{tx:.2f}" y="{ty:.2f}" font-size="12" text-anchor="{placement.anchor}" fill="{axis}" {label_style} font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(p.label)}</text>'
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


def write_matplotlib(out_path: Path, title: str, points: List[Point], arrows: List[Tuple[str, str, str]]) -> None:
    repo_root = Path.cwd()
    xdg_cache = repo_root / ".cache"
    xdg_cache.mkdir(exist_ok=True)
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache))
    mpl_dir = repo_root / ".mplconfig"
    mpl_dir.mkdir(exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir))

    import matplotlib  # type: ignore

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore
    from matplotlib.lines import Line2D  # type: ignore

    fig, ax = plt.subplots(figsize=(9.8, 6.4), dpi=120)

    # Axis bounds (match SVG layout, expanded for scan70 n=10).
    # X=avg_power (auto), Y=P_out (fixed).
    xs = [p.x for p in points]
    xerrs = [p.xerr for p in points]
    x_min = min(x - xe for x, xe in zip(xs, xerrs))
    x_max = max(x + xe for x, xe in zip(xs, xerrs))
    x_pad = max(5.0, (x_max - x_min) * 0.1)
    xmin = math.floor((x_min - x_pad) / 5.0) * 5.0
    xmax = math.ceil((x_max + x_pad) / 5.0) * 5.0
    xmin = min(xmin, 185.0)

    x_span = xmax - xmin
    if x_span <= 40:
        x_step = 5.0
    elif x_span <= 80:
        x_step = 10.0
    else:
        x_step = 20.0
    ax.set_xlim(xmin, xmax)
    ax.set_xticks([xmin + i * x_step for i in range(int(round((xmax - xmin) / x_step)) + 1)])

    ax.set_ylim(0.0, 0.35)
    ax.set_yticks([i * 0.05 for i in range(8)])
    ax.grid(True, color="#e5e7eb", linewidth=1.0)

    ax.set_xlabel("avg_power_mW (lower=better)")
    ax.set_ylabel("pout_1s (lower=better)")
    if title:
        ax.set_title(title)

    # eps=0.1 guideline
    ax.axhline(0.1, color="#9ca3af", linestyle=(0, (6, 4)), linewidth=1.8)
    ax.text(xmax - (xmax - xmin) * 0.02, 0.102, "eps=0.1", ha="right", va="bottom", color="#6b7280", fontsize=10)

    marker_map = {
        "square": "s",
        "triangle": "^",
        "diamond": "D",
        "circle": "o",
    }

    # Error bars + points
    for p in points:
        marker = marker_map.get(p.shape, "o")
        ax.errorbar(
            p.x,
            p.y,
            yerr=p.yerr,
            fmt=marker,
            ms=7,
            color=p.color,
            capsize=3,
            linestyle="none",
            alpha=0.95,
        )

    # Arrows
    by_key: Dict[str, Point] = {p.key: p for p in points}
    for src, dst, text in arrows:
        ps = by_key.get(src)
        pd = by_key.get(dst)
        if ps is None or pd is None:
            continue
        ax.annotate(
            "",
            xy=(pd.x, pd.y),
            xytext=(ps.x, ps.y),
            arrowprops=dict(arrowstyle="->", color="#111827", lw=2.0, alpha=0.35),
        )
        if text:
            mx, my = (ps.x + pd.x) / 2, (ps.y + pd.y) / 2
            ax.text(mx + 0.005, my + 0.5, text, fontsize=10, color="#111827")

    label_keys = [
        "scan70_fixed500",
        "scan90_fixed500",
        "scan70_policy",
        "scan90_policy",
        "scan90_ccs_off",
        "scan90_fixed100",
        "scan70_fixed100",
        "scan90_u_shuf",
    ]
    # Reuse the SVG placement in pixel space to avoid overlaps.
    fig_dpi = fig.get_dpi()

    def xpx(x: float) -> float:
        return ax.transData.transform((x, 0))[0]

    def ypx(y: float) -> float:
        return ax.transData.transform((0, y))[1]

    placements = _auto_place_labels(points, label_keys, xpx, ypx, ax.bbox.bounds, font_size=10.0)
    for p in points:
        placement = placements.get(p.key)
        if not placement:
            continue
        dx_pt = placement.dx * 72.0 / fig_dpi
        dy_pt = placement.dy * 72.0 / fig_dpi
        align = "center"
        if placement.anchor == "start":
            align = "left"
        elif placement.anchor == "end":
            align = "right"
        arrowprops = None
        if placement.leader:
            arrowprops = dict(arrowstyle="-", color="#111827", lw=1.2, alpha=0.35)
        ax.annotate(
            p.label,
            (p.x, p.y),
            textcoords="offset points",
            xytext=(dx_pt, dy_pt),
            ha=align,
            fontsize=10,
            color="#111827",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9),
            arrowprops=arrowprops,
        )

    legend = [
        Line2D([0], [0], marker="s", color="none", markerfacecolor="#3b82f6", markeredgecolor="#3b82f6", label="scan90 fixed"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#10b981", markeredgecolor="#10b981", label="scan90 policy"),
        Line2D([0], [0], marker="^", color="none", markerfacecolor="#f59e0b", markeredgecolor="#f59e0b", label="scan90 ablation"),
        Line2D([0], [0], marker="D", color="none", markerfacecolor="#111827", markeredgecolor="#111827", label="scan70 (worse RX)"),
    ]
    ax.legend(handles=legend, loc="upper right", frameon=True, fontsize=9)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--d4-csv", type=Path, default=Path("uccs_d4_scan90/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--d4b-csv", type=Path, default=Path("uccs_d4b_scan90/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--d3-csv", type=Path, default=Path("uccs_d3_scan70/metrics/01/summary_by_condition.csv"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", type=str, default="")
    args = ap.parse_args()

    d4 = read_summary(args.d4_csv)
    d4b = read_summary(args.d4b_csv)
    d3 = read_summary(args.d3_csv)

    pts: List[Point] = []
    # scan90 fixed points (use D4B fixed values for consistency with CCS-off run)
    pts.append(Point("scan90_fixed100", "fixed100 (90)", d4b["S4_fixed100"]["power"], d4b["S4_fixed100"]["pout"], d4b["S4_fixed100"]["power_err"], d4b["S4_fixed100"]["pout_err"], "#3b82f6", "square"))
    pts.append(Point("scan90_fixed500", "fixed500 (90)", d4b["S4_fixed500"]["power"], d4b["S4_fixed500"]["pout"], d4b["S4_fixed500"]["power_err"], d4b["S4_fixed500"]["pout_err"], "#3b82f6", "square"))

    # scan90 policy (U+CCS): use D4B policy point (same definition)
    pts.append(Point("scan90_policy", "policy (90)", d4b["S4_policy"]["power"], d4b["S4_policy"]["pout"], d4b["S4_policy"]["power_err"], d4b["S4_policy"]["pout_err"], "#10b981", "circle"))

    # scan90 ablations
    pts.append(Point("scan90_u_shuf", "U-shuf", d4["S4_ablation_u_shuf"]["power"], d4["S4_ablation_u_shuf"]["pout"], d4["S4_ablation_u_shuf"]["power_err"], d4["S4_ablation_u_shuf"]["pout_err"], "#f59e0b", "triangle"))
    pts.append(Point("scan90_ccs_off", "CCS-off", d4b["S4_ablation_ccs_off"]["power"], d4b["S4_ablation_ccs_off"]["pout"], d4b["S4_ablation_ccs_off"]["power_err"], d4b["S4_ablation_ccs_off"]["pout_err"], "#f59e0b", "triangle"))

    # scan70 robustness (D3): fixed100/fixed500/policy
    pts.append(Point("scan70_fixed100", "fixed100 (70)", d3["S4_fixed100"]["power"], d3["S4_fixed100"]["pout"], d3["S4_fixed100"]["power_err"], d3["S4_fixed100"]["pout_err"], "#111827", "diamond"))
    pts.append(Point("scan70_fixed500", "fixed500 (70)", d3["S4_fixed500"]["power"], d3["S4_fixed500"]["pout"], d3["S4_fixed500"]["power_err"], d3["S4_fixed500"]["pout_err"], "#111827", "diamond"))
    pts.append(Point("scan70_policy", "policy (70)", d3["S4_policy"]["power"], d3["S4_policy"]["pout"], d3["S4_policy"]["power_err"], d3["S4_policy"]["pout_err"], "#111827", "diamond"))

    arrows = [
        ("scan90_u_shuf", "scan90_policy", ""),
        ("scan90_ccs_off", "scan90_policy", ""),
        ("scan90_fixed500", "scan70_fixed500", ""),
        ("scan90_policy", "scan70_policy", ""),
    ]

    if args.out.suffix.lower() == ".svg":
        write_svg(args.out, title=args.title, points=pts, arrows=arrows)
    else:
        write_matplotlib(args.out, title=args.title, points=pts, arrows=arrows)


if __name__ == "__main__":
    main()

