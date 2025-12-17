#!/usr/bin/env python3
"""
D4B (CCS ablation) additional analysis: tail-risk decomposition of Pout(1s).

Motivation:
  - pout_1s is often driven by a small number of transition events (TL > 1s).
  - This script quantifies "how concentrated" the delta-pout is across transitions
    and generates a few letter-friendly, no-deps SVG plots.

Inputs:
  - per_transition.csv from outage_story_trace.py (trial × transition TL/outage)
  - outage_ranking.csv from outage_story_trace.py (transition-wise outage-rate diff)

Outputs (out_dir):
  - outage_counts_by_trial.csv
  - delta_pout_contrib.csv
  - fig_delta_pout_cum.svg
  - fig_outage_count_hist.svg
  - pout_tail_decomposition.md

No external dependencies.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class TrialOutage:
    rx_file: str
    mode: str  # "P" or "U"
    n_transitions: int
    n_outages: int


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, header: List[str], rows: List[List[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


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


def _plot_cumulative_svg(
    out_svg: Path,
    title: str,
    xs: List[int],
    ys: List[float],
    y_label: str,
) -> None:
    width, height = 920, 520
    ml, mr, mt, mb = 70, 30, 70, 60
    pw = width - ml - mr
    ph = height - mt - mb
    axis = "#111827"
    grid = "#e5e7eb"
    line = "#2563eb"

    def xpx(x: float) -> float:
        if not xs:
            return ml
        xmin, xmax = min(xs), max(xs)
        if xmax == xmin:
            return ml + pw / 2
        return ml + (x - xmin) * pw / (xmax - xmin)

    def ypx(y: float) -> float:
        # y in [0,1]
        return mt + (1.0 - max(0.0, min(1.0, y))) * ph

    svg: List[str] = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>')
    svg.append(f'<text x="{width/2:.1f}" y="38" font-size="20" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(title)}</text>')
    svg.append(f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" fill="none" stroke="{axis}" stroke-width="1.2"/>')

    # grid + y ticks
    for i in range(6):
        y = i / 5
        py = ypx(y)
        svg.append(f'<line x1="{ml}" y1="{py:.2f}" x2="{ml+pw}" y2="{py:.2f}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{ml-8}" y="{py+4:.2f}" font-size="12" text-anchor="end" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(y,2)}</text>')

    # x ticks
    for i in range(6):
        if not xs:
            break
        x = min(xs) + (max(xs) - min(xs)) * i / 5
        px = xpx(x)
        svg.append(f'<line x1="{px:.2f}" y1="{mt}" x2="{px:.2f}" y2="{mt+ph}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{px:.2f}" y="{mt+ph+26}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{int(round(x))}</text>')

    # path
    if xs:
        d = [f"M {xpx(xs[0]):.2f} {ypx(ys[0]):.2f}"]
        for x, y in zip(xs[1:], ys[1:]):
            d.append(f"L {xpx(x):.2f} {ypx(y):.2f}")
        svg.append(f'<path d="{" ".join(d)}" fill="none" stroke="{line}" stroke-width="2.5"/>')

    svg.append(f'<text x="{ml+pw/2:.1f}" y="{height-20}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">top-K transitions (sorted by ΔPout contribution)</text>')
    svg.append(f'<text x="18" y="{mt+ph/2:.1f}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system" transform="rotate(-90 18 {mt+ph/2:.1f})">{_svg_escape(y_label)}</text>')
    svg.append("</svg>")

    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(svg), encoding="utf-8")


def _plot_hist_svg(
    out_svg: Path,
    title: str,
    bins: List[int],
    counts_p: List[int],
    counts_u: List[int],
) -> None:
    width, height = 920, 520
    ml, mr, mt, mb = 70, 30, 70, 60
    pw = width - ml - mr
    ph = height - mt - mb
    axis = "#111827"
    grid = "#e5e7eb"
    col_p = "#2563eb"
    col_u = "#ef4444"

    max_count = max(counts_p + counts_u + [1])

    svg: List[str] = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>')
    svg.append(f'<text x="{width/2:.1f}" y="38" font-size="20" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(title)}</text>')
    svg.append(f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" fill="none" stroke="{axis}" stroke-width="1.2"/>')

    for i in range(6):
        y = i / 5 * max_count
        py = mt + (1 - i / 5) * ph
        svg.append(f'<line x1="{ml}" y1="{py:.2f}" x2="{ml+pw}" y2="{py:.2f}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{ml-8}" y="{py+4:.2f}" font-size="12" text-anchor="end" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{int(round(y))}</text>')

    n = max(1, len(bins))
    group_w = pw / n
    bar_w = group_w * 0.35

    def ypx(count: int) -> float:
        return mt + (1 - (count / max_count)) * ph

    for i, b in enumerate(bins):
        x0 = ml + i * group_w + group_w / 2
        # policy bar
        hp = ph - (ypx(counts_p[i]) - mt)
        svg.append(f'<rect x="{x0-bar_w-2:.2f}" y="{ypx(counts_p[i]):.2f}" width="{bar_w:.2f}" height="{hp:.2f}" fill="{col_p}" opacity="0.75"/>')
        # u-only bar
        hu = ph - (ypx(counts_u[i]) - mt)
        svg.append(f'<rect x="{x0+2:.2f}" y="{ypx(counts_u[i]):.2f}" width="{bar_w:.2f}" height="{hu:.2f}" fill="{col_u}" opacity="0.75"/>')
        svg.append(f'<text x="{x0:.2f}" y="{mt+ph+26}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{b}</text>')

    # legend
    lx, ly = ml + pw - 220, mt + 10
    svg.append(f'<rect x="{lx}" y="{ly}" width="210" height="54" fill="#ffffff" stroke="{grid}" stroke-width="1"/>')
    svg.append(f'<rect x="{lx+12}" y="{ly+14}" width="14" height="14" fill="{col_p}" opacity="0.75"/>')
    svg.append(f'<text x="{lx+34}" y="{ly+26}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">Policy (U+CCS)</text>')
    svg.append(f'<rect x="{lx+12}" y="{ly+34}" width="14" height="14" fill="{col_u}" opacity="0.75"/>')
    svg.append(f'<text x="{lx+34}" y="{ly+46}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">U-only (CCS-off)</text>')

    svg.append(f'<text x="{ml+pw/2:.1f}" y="{height-20}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">outage count per trial (TL&gt;1s), binned</text>')
    svg.append(f'<text x="18" y="{mt+ph/2:.1f}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system" transform="rotate(-90 18 {mt+ph/2:.1f})"># trials</text>')
    svg.append("</svg>")

    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(svg), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-transition-csv", type=Path, required=True)
    ap.add_argument("--outage-ranking-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--tau-s", type=float, default=1.0)
    ap.add_argument("--top-k-max", type=int, default=20)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Per-trial outage counts
    per_rows = _read_csv(args.per_transition_csv)
    by_trial: Dict[Tuple[str, str], List[int]] = {}
    for r in per_rows:
        mode = r["mode"]
        if mode not in ("P", "U"):
            continue
        key = (r["rx_file"], mode)
        by_trial.setdefault(key, []).append(int(r["outage_gt_tau"]))

    trials: List[TrialOutage] = []
    for (rx_file, mode), outs in sorted(by_trial.items()):
        trials.append(TrialOutage(rx_file=rx_file, mode=mode, n_transitions=len(outs), n_outages=sum(outs)))

    _write_csv(
        args.out_dir / "outage_counts_by_trial.csv",
        ["rx_file", "mode", "n_transitions", "n_outages", "pout_est"],
        [[t.rx_file, t.mode, t.n_transitions, t.n_outages, (t.n_outages / t.n_transitions if t.n_transitions else float("nan"))] for t in trials],
    )

    # Histogram bins (0..max_outages observed)
    max_out = max((t.n_outages for t in trials), default=0)
    bins = list(range(0, max_out + 1))
    c_p = [0] * len(bins)
    c_u = [0] * len(bins)
    for t in trials:
        if t.n_outages not in bins:
            continue
        idx = bins.index(t.n_outages)
        if t.mode == "P":
            c_p[idx] += 1
        else:
            c_u[idx] += 1

    _plot_hist_svg(
        args.out_dir / "fig_outage_count_hist.svg",
        title=f"D4B: outage-count distribution per trial (TL>{args.tau_s:.1f}s)",
        bins=bins,
        counts_p=c_p,
        counts_u=c_u,
    )

    # Delta-Pout contribution across transitions (from outage_ranking.csv)
    rank_rows = _read_csv(args.outage_ranking_csv)
    # Keep only finite deltas
    deltas: List[Tuple[int, float]] = []
    for r in rank_rows:
        try:
            step = int(float(r["transition_step"]))
            du = float(r["u_minus_p_out_rate"])
        except Exception:
            continue
        if math.isnan(du) or math.isinf(du):
            continue
        deltas.append((step, du))

    # Contributions: overall Δpout = mean_j du_j (j over transitions)
    # We focus on positive du (U-only worse) because it explains the improvement.
    pos = [(step, du) for step, du in deltas if du > 0]
    pos.sort(key=lambda x: x[1], reverse=True)
    total_pos = sum(du for _step, du in pos) or 1.0

    contrib_rows: List[List[object]] = []
    cum = 0.0
    xs: List[int] = []
    ys: List[float] = []
    for k in range(1, min(args.top_k_max, len(pos)) + 1):
        step, du = pos[k - 1]
        cum += du
        frac = cum / total_pos
        xs.append(k)
        ys.append(frac)
        contrib_rows.append([k, step, du, frac])

    _write_csv(
        args.out_dir / "delta_pout_contrib.csv",
        ["k", "transition_step", "delta_out_rate", "cum_frac_of_positive_delta"],
        contrib_rows,
    )
    if xs:
        _plot_cumulative_svg(
            args.out_dir / "fig_delta_pout_cum.svg",
            title="D4B: cumulative share of positive ΔPout explained by top-K transitions",
            xs=xs,
            ys=ys,
            y_label="cumulative fraction of positive ΔPout",
        )

    # Write a short markdown summary (letter-friendly notes)
    p_pouts = [t.n_outages / t.n_transitions for t in trials if t.mode == "P" and t.n_transitions]
    u_pouts = [t.n_outages / t.n_transitions for t in trials if t.mode == "U" and t.n_transitions]
    md: List[str] = []
    md.append("# D4B Pout tail decomposition (TL>%.1fs)" % args.tau_s)
    md.append("")
    md.append(f"- input: `{args.per_transition_csv}` / `{args.outage_ranking_csv}`")
    md.append(f"- output dir: `{args.out_dir}`")
    md.append("")
    md.append("## Trial-level outage counts")
    md.append("")
    if p_pouts and u_pouts:
        md.append(f"- Policy (U+CCS): mean pout_est={_fmt(statistics.mean(p_pouts),4)} (n_trials={len(p_pouts)})")
        md.append(f"- U-only (CCS-off): mean pout_est={_fmt(statistics.mean(u_pouts),4)} (n_trials={len(u_pouts)})")
    md.append("")
    md.append("## Concentration across transitions")
    md.append("")
    if xs:
        md.append(f"- #transitions with positive ΔPout (U-only worse): {len(pos)} / {len(deltas)} total transitions")
        md.append(f"- top-1 explains {ys[0]*100:.1f}% of positive ΔPout; top-{xs[min(4,len(xs))-1]} explains {ys[min(4,len(xs))-1]*100:.1f}%")
        md.append(f"- see `fig_delta_pout_cum.svg` + `delta_pout_contrib.csv`")
    md.append("")
    md.append("## Figures")
    md.append("")
    md.append(f"- `fig_outage_count_hist.svg`: outage-count distribution per trial")
    md.append(f"- `fig_delta_pout_cum.svg`: cumulative ΔPout concentration curve (top-K transitions)")
    md.append("")
    (args.out_dir / "pout_tail_decomposition.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

