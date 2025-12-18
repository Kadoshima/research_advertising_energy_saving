#!/usr/bin/env python3
"""
Main figure: scan70 vs scan90 on the same axes (power vs P_out(1s)).

Requirements
------------
- Dependency-free (no pandas/matplotlib). Outputs SVG.

Input
-----
- per_trial.csv (n=3 each) for scan90 and scan70.
  Expected columns (same as summarize_* outputs):
    - condition: S4_fixed100 / S4_fixed500 / S4_policy / S4_ablation_ccs_off
    - avg_power_mW
    - pout_1s

Output
------
- SVG scatter with bootstrap CI error bars (mean of n=3; 95% bootstrap CI).

Notes (intended narrative)
-------------------------
- scan70: Fixed500 breaks (high P_out), but policy group remains feasible as a mid-solution.
- scan90: At similar mix, CCS can improve QoS at (almost) the same power (shown in scan90 D4B).
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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


def bootstrap_ci_mean(xs: List[float], n_boot: int = 20000, seed: int = 0) -> Tuple[float, float]:
    """
    95% bootstrap CI for mean. For n=3 this is necessarily coarse, but it is
    preferable to mean±std for "reproducibility-like" visualization.
    """
    if not xs:
        return (float("nan"), float("nan"))
    if len(xs) == 1:
        return (xs[0], xs[0])
    rng = random.Random(seed)
    n = len(xs)
    means = []
    for _ in range(n_boot):
        s = [xs[rng.randrange(n)] for __ in range(n)]
        means.append(statistics.mean(s))
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot)]
    return float(lo), float(hi)


@dataclass
class PointCI:
    x_mean: float
    x_lo: float
    x_hi: float
    y_mean: float
    y_lo: float
    y_hi: float
    n: int


def read_per_trial(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def f_or_none(v: str) -> Optional[float]:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except Exception:
        return None


def summarize_with_bootstrap(per_trial_csv: Path, seed: int) -> Dict[str, PointCI]:
    rows = read_per_trial(per_trial_csv)
    by: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        cond = (r.get("condition") or "").strip()
        if not cond:
            continue
        by.setdefault(cond, []).append(r)

    out: Dict[str, PointCI] = {}
    for cond, rs in by.items():
        xs = [f_or_none(r.get("avg_power_mW") or "") for r in rs]
        ys = [f_or_none(r.get("pout_1s") or "") for r in rs]
        xs_f = [x for x in xs if x is not None]
        ys_f = [y for y in ys if y is not None]
        if len(xs_f) < 1 or len(ys_f) < 1:
            continue
        x_mean = statistics.mean(xs_f)
        y_mean = statistics.mean(ys_f)
        x_lo, x_hi = bootstrap_ci_mean(xs_f, seed=seed)
        y_lo, y_hi = bootstrap_ci_mean(ys_f, seed=seed + 13)
        out[cond] = PointCI(
            x_mean=float(x_mean),
            x_lo=float(x_lo),
            x_hi=float(x_hi),
            y_mean=float(y_mean),
            y_lo=float(y_lo),
            y_hi=float(y_hi),
            n=len(rs),
        )
    return out


def write_svg(
    out_path: Path,
    title: str,
    scan90: Dict[str, PointCI],
    scan70: Dict[str, PointCI],
    y_label: str = "P_out(1s)",
    x_label: str = "avg_power [mW]",
) -> None:
    width = 980
    height = 640
    margin_l = 90
    margin_r = 40
    margin_t = 70
    margin_b = 80
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    # Axis ranges from all CI bounds.
    xs = []
    ys = []
    for d in (scan90, scan70):
        for p in d.values():
            xs += [p.x_lo, p.x_hi]
            ys += [p.y_lo, p.y_hi]
    xmin = min(xs) if xs else 0.0
    xmax = max(xs) if xs else 1.0
    ymin = 0.0
    ymax = max(ys) if ys else 1.0

    xpad = max(0.5, (xmax - xmin) * 0.08)
    ypad = max(0.01, (ymax - ymin) * 0.15)
    xmin -= xpad
    xmax += xpad
    ymax += ypad

    def x_to_px(x: float) -> float:
        return margin_l + (x - xmin) * plot_w / (xmax - xmin) if xmax > xmin else (margin_l + plot_w / 2)

    def y_to_px(y: float) -> float:
        return margin_t + (ymax - y) * plot_h / (ymax - ymin) if ymax > ymin else (margin_t + plot_h / 2)

    bg = "#ffffff"
    axis = "#111827"
    grid = "#e5e7eb"
    scan_colors = {"scan90": "#111827", "scan70": "#7c3aed"}  # black / purple
    cond_mark = {
        "S4_fixed100": "triangle",
        "S4_fixed500": "square",
        "S4_policy": "circle",
        "S4_ablation_ccs_off": "diamond",
    }
    cond_label = {
        "S4_fixed100": "Fixed100",
        "S4_fixed500": "Fixed500",
        "S4_policy": "Policy (U+CCS)",
        "S4_ablation_ccs_off": "U-only (CCS-off)",
    }

    def draw_marker(kind: str, cx: float, cy: float, r: float, fill: str) -> str:
        if kind == "circle":
            return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" opacity="0.95"/>'
        if kind == "square":
            s = r * 1.8
            return f'<rect x="{(cx - s/2):.2f}" y="{(cy - s/2):.2f}" width="{s:.2f}" height="{s:.2f}" fill="{fill}" opacity="0.95"/>'
        if kind == "diamond":
            s = r * 2.0
            pts = [(cx, cy - s/2), (cx + s/2, cy), (cx, cy + s/2), (cx - s/2, cy)]
            ps = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
            return f'<polygon points="{ps}" fill="{fill}" opacity="0.95"/>'
        # triangle
        s = r * 2.1
        pts = [(cx, cy - s/2), (cx + s/2, cy + s/2), (cx - s/2, cy + s/2)]
        ps = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        return f'<polygon points="{ps}" fill="{fill}" opacity="0.95"/>'

    def draw_errorbars(p: PointCI, color: str) -> List[str]:
        px = x_to_px(p.x_mean)
        py = y_to_px(p.y_mean)
        px_l = x_to_px(p.x_lo)
        px_r = x_to_px(p.x_hi)
        py_u = y_to_px(p.y_hi)
        py_d = y_to_px(p.y_lo)
        lines = []
        lines.append(f'<line x1="{px_l:.2f}" y1="{py:.2f}" x2="{px_r:.2f}" y2="{py:.2f}" stroke="{color}" stroke-width="2" opacity="0.9"/>')
        lines.append(f'<line x1="{px:.2f}" y1="{py_u:.2f}" x2="{px:.2f}" y2="{py_d:.2f}" stroke="{color}" stroke-width="2" opacity="0.9"/>')
        return lines

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>')
    svg.append(
        f'<text x="{width/2:.1f}" y="40" font-size="20" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">'
        f"{_svg_escape(title)}</text>"
    )
    svg.append(f'<rect x="{margin_l}" y="{margin_t}" width="{plot_w}" height="{plot_h}" fill="none" stroke="{axis}" stroke-width="1.2"/>')

    # grid + ticks
    for i in range(6):
        tx = xmin + (xmax - xmin) * i / 5.0
        px = x_to_px(tx)
        svg.append(f'<line x1="{px:.2f}" y1="{margin_t}" x2="{px:.2f}" y2="{margin_t+plot_h}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{px:.2f}" y="{margin_t+plot_h+24}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(tx,1)}</text>')
    for i in range(6):
        ty = ymin + (ymax - ymin) * i / 5.0
        py = y_to_px(ty)
        svg.append(f'<line x1="{margin_l}" y1="{py:.2f}" x2="{margin_l+plot_w}" y2="{py:.2f}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{margin_l-10}" y="{py+4:.2f}" font-size="12" text-anchor="end" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(ty,3)}</text>')

    svg.append(f'<text x="{margin_l+plot_w/2:.1f}" y="{height-24}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(x_label)}</text>')
    svg.append(f'<text x="22" y="{margin_t+plot_h/2:.1f}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system" transform="rotate(-90 22 {margin_t+plot_h/2:.1f})">{_svg_escape(y_label)}</text>')

    # plot scan70 + scan90 (order: fixed500 behind)
    def plot_env(env_name: str, data: Dict[str, PointCI]) -> None:
        color = scan_colors[env_name]
        # consistent order
        order = ["S4_fixed500", "S4_fixed100", "S4_policy", "S4_ablation_ccs_off"]
        for cond in order:
            p = data.get(cond)
            if not p:
                continue
            svg.extend(draw_errorbars(p, color))
            px = x_to_px(p.x_mean)
            py = y_to_px(p.y_mean)
            svg.append(draw_marker(cond_mark.get(cond, "circle"), px, py, 6.0, color))
            txt = f"{cond_label.get(cond, cond)} ({env_name}, n={p.n})"
            svg.append(
                f'<text x="{px+10:.2f}" y="{py-10:.2f}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">'
                f"{_svg_escape(txt)}</text>"
            )

    plot_env("scan70", scan70)
    plot_env("scan90", scan90)

    # Legend (env colors)
    lx = margin_l + 10
    ly = margin_t - 24
    svg.append(f'<rect x="{lx}" y="{ly}" width="340" height="40" fill="#ffffff" stroke="{grid}"/>')
    svg.append(draw_marker("circle", lx + 20, ly + 20, 6, scan_colors["scan90"]))
    svg.append(f'<text x="{lx+34}" y="{ly+24}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">scan90</text>')
    svg.append(draw_marker("circle", lx + 110, ly + 20, 6, scan_colors["scan70"]))
    svg.append(f'<text x="{lx+124}" y="{ly+24}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">scan70</text>')
    svg.append(f'<text x="{lx+200}" y="{ly+24}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">error bars: 95% bootstrap CI (mean)</text>')

    svg.append("</svg>\n")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(svg), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan90", type=Path, required=True, help="per_trial.csv for scan90 run")
    ap.add_argument("--scan70", type=Path, required=True, help="per_trial.csv for scan70 run")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", type=str, default="Main figure: scan70 vs scan90 (S4, D4B)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    scan90_sum = summarize_with_bootstrap(args.scan90, seed=args.seed)
    scan70_sum = summarize_with_bootstrap(args.scan70, seed=args.seed + 1000)

    write_svg(args.out, args.title, scan90=scan90_sum, scan70=scan70_sum)


if __name__ == "__main__":
    main()

