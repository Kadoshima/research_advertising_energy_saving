#!/usr/bin/env python3
"""
Conditional timing analysis for D4B (run01):
  "average over all transitions" can hide differences, because pout_1s is driven by a few failures.

This script re-computes a minimal timing view (P(interval=100) around transitions) on a *subset* of transitions.

Inputs:
  - RX dir (D4B run01): `.../RX` containing rx_trial_*.csv
  - truth CSV (100ms grid): stress_causal_S4.csv
  - outage_ranking.csv (from outage_story_trace.py) to choose subset transitions

Outputs (out_dir):
  - selected_transitions.csv
  - fig_event_triggered_p100_conditional.svg

No external dependencies.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DT_MS = 100


def _svg_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _read_truth_labels(path: Path, n_steps: int) -> List[int]:
    labels: List[int] = []
    with path.open(newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            labels.append(int(row["label"]))
            if len(labels) >= n_steps:
                break
    if len(labels) < n_steps:
        raise SystemExit(f"truth too short: {path} rows={len(labels)} < {n_steps}")
    return labels


def _extract_transitions(labels: List[int]) -> List[int]:
    out: List[int] = []
    prev = labels[0]
    for i in range(1, len(labels)):
        cur = labels[i]
        if cur != prev:
            out.append(i)
        prev = cur
    return out


def _parse_step_idx_from_mfd(mfd: str) -> Optional[int]:
    mfd = (mfd or "").strip()
    if not mfd:
        return None
    us = mfd.find("_")
    if us <= 0:
        return None
    try:
        return int(mfd[:us])
    except Exception:
        return None


def _parse_tag(tag: str) -> Optional[Tuple[str, int, int]]:
    # ex: P4-03-100, U4-01-500
    tag = (tag or "").strip()
    if not tag:
        return None
    mode = tag[0]
    if mode not in ("P", "U"):
        return None
    parts = tag.split("-")
    if len(parts) < 3:
        return None
    try:
        itv = int(parts[2])
    except Exception:
        return None
    if itv not in (100, 500):
        return None
    return mode, itv


@dataclass(frozen=True)
class RxEvent:
    step_idx: int
    rx_ms: float
    itv_ms: int


def _read_rx_events_by_mode(path: Path, n_steps: int) -> Dict[str, List[RxEvent]]:
    out: Dict[str, List[RxEvent]] = {"P": [], "U": []}
    with path.open(newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            parsed = _parse_tag(row.get("label") or "")
            if parsed is None:
                continue
            mode, itv = parsed
            step = _parse_step_idx_from_mfd(row.get("mfd") or "")
            if step is None or not (0 <= step < n_steps):
                continue
            try:
                rx_ms = float(row.get("ms") or "")
            except Exception:
                continue
            out[mode].append(RxEvent(step_idx=step, rx_ms=rx_ms, itv_ms=itv))
    return out


def _dominant_mode(events_by_mode: Dict[str, List[RxEvent]]) -> Optional[str]:
    p = len(events_by_mode.get("P") or [])
    u = len(events_by_mode.get("U") or [])
    if p == 0 and u == 0:
        return None
    return "P" if p >= u else "U"


def _ffill_itv(n_steps: int, itv_by_step: Dict[int, int]) -> List[int]:
    if not itv_by_step:
        return [500] * n_steps
    first = min(itv_by_step.keys())
    cur = itv_by_step[first]
    out = [cur] * n_steps
    for t in range(n_steps):
        if t in itv_by_step:
            cur = itv_by_step[t]
        out[t] = cur
    return out


def _select_transition_subset(
    ranking_csv: Path,
    subset: str,
    top_k: int,
) -> List[int]:
    rows: List[Dict[str, str]] = []
    with ranking_csv.open(newline="") as f:
        rows = list(csv.DictReader(f))
    items: List[Tuple[int, float, float, float]] = []
    for r in rows:
        try:
            step = int(float(r["transition_step"]))
            du = float(r["u_minus_p_out_rate"])
            ur = float(r["u_only_out_rate"])
            pr = float(r["policy_out_rate"])
        except Exception:
            continue
        if math.isnan(du) or math.isinf(du):
            continue
        items.append((step, du, ur, pr))

    if subset == "u_only_worse":
        # where U-only is worse in outage-rate than policy
        items = [x for x in items if x[1] > 0]
        items.sort(key=lambda x: x[1], reverse=True)
    elif subset == "u_only_outage":
        # where U-only has any outage-rate
        items = [x for x in items if x[2] > 0]
        items.sort(key=lambda x: (x[2], x[1]), reverse=True)
    else:
        raise SystemExit(f"unknown subset: {subset}")

    return [step for step, _du, _ur, _pr in items[:top_k]]


def _plot_event_triggered_svg(
    out_svg: Path,
    title: str,
    window_steps: int,
    p100_policy: List[float],
    p100_uonly: List[float],
) -> None:
    width, height = 920, 520
    ml, mr, mt, mb = 70, 30, 70, 60
    pw = width - ml - mr
    ph = height - mt - mb
    axis = "#111827"
    grid = "#e5e7eb"
    col_p = "#2563eb"
    col_u = "#ef4444"

    xs = list(range(-window_steps, window_steps + 1))
    xmin, xmax = xs[0], xs[-1]

    def xpx(x: float) -> float:
        if xmax == xmin:
            return ml + pw / 2
        return ml + (x - xmin) * pw / (xmax - xmin)

    def ypx(y: float) -> float:
        return mt + (1 - max(0.0, min(1.0, y))) * ph

    svg: List[str] = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>')
    svg.append(f'<text x="{width/2:.1f}" y="38" font-size="20" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{title}</text>')
    svg.append(f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" fill="none" stroke="{axis}" stroke-width="1.2"/>')

    # grid
    for i in range(6):
        y = i / 5
        py = ypx(y)
        svg.append(f'<line x1="{ml}" y1="{py:.2f}" x2="{ml+pw}" y2="{py:.2f}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{ml-8}" y="{py+4:.2f}" font-size="12" text-anchor="end" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{y:.1f}</text>')
    # x ticks
    for i in range(7):
        x = xmin + (xmax - xmin) * i / 6
        px = xpx(x)
        svg.append(f'<line x1="{px:.2f}" y1="{mt}" x2="{px:.2f}" y2="{mt+ph}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{px:.2f}" y="{mt+ph+26}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{(x*DT_MS)/1000:.1f}</text>')

    # vertical line at 0
    px0 = xpx(0)
    svg.append(f'<line x1="{px0:.2f}" y1="{mt}" x2="{px0:.2f}" y2="{mt+ph}" stroke="#6b7280" stroke-width="2" stroke-dasharray="6 4"/>')

    def path(vals: List[float], col: str) -> None:
        d = [f"M {xpx(xs[0]):.2f} {ypx(vals[0]):.2f}"]
        for x, y in zip(xs[1:], vals[1:]):
            d.append(f"L {xpx(x):.2f} {ypx(y):.2f}")
        d_str = " ".join(d)
        svg.append(f'<path d="{d_str}" fill="none" stroke="{col}" stroke-width="2.5"/>')

    path(p100_policy, col_p)
    path(p100_uonly, col_u)

    # legend
    lx, ly = ml + pw - 240, mt + 10
    svg.append(f'<rect x="{lx}" y="{ly}" width="230" height="54" fill="#ffffff" stroke="{grid}" stroke-width="1"/>')
    svg.append(f'<line x1="{lx+14}" y1="{ly+20}" x2="{lx+34}" y2="{ly+20}" stroke="{col_p}" stroke-width="3"/>')
    svg.append(f'<text x="{lx+42}" y="{ly+24}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">Policy (U+CCS)</text>')
    svg.append(f'<line x1="{lx+14}" y1="{ly+40}" x2="{lx+34}" y2="{ly+40}" stroke="{col_u}" stroke-width="3"/>')
    svg.append(f'<text x="{lx+42}" y="{ly+44}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">U-only (CCS-off)</text>')

    svg.append(f'<text x="{ml+pw/2:.1f}" y="{height-20}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">relative time to truth transition [s]</text>')
    svg.append(f'<text x="18" y="{mt+ph/2:.1f}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system" transform="rotate(-90 18 {mt+ph/2:.1f})">P(interval=100ms)</text>')
    svg.append("</svg>")

    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(svg), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx-dir", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--outage-ranking-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--n-steps", type=int, default=1800)
    ap.add_argument("--window-s", type=float, default=2.0)
    ap.add_argument("--subset", choices=("u_only_worse", "u_only_outage"), default="u_only_worse")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    window_steps = int(round(args.window_s * 1000 / DT_MS))
    truth = _read_truth_labels(args.truth, n_steps=args.n_steps)
    all_trans = _extract_transitions(truth)

    subset_steps = _select_transition_subset(args.outage_ranking_csv, subset=args.subset, top_k=args.top_k)
    subset_steps = [s for s in subset_steps if s in set(all_trans)]
    if not subset_steps:
        raise SystemExit("empty transition subset")

    # Build action series per trial, per mode
    series: Dict[str, List[List[int]]] = {"P": [], "U": []}  # mode -> list of itv series (len=n_steps)
    for p in sorted(args.rx_dir.glob("rx_trial_*.csv")):
        ev_by_mode = _read_rx_events_by_mode(p, n_steps=args.n_steps)
        mode = _dominant_mode(ev_by_mode)
        if mode is None or mode not in ("P", "U"):
            continue
        evs = ev_by_mode[mode]
        if len(evs) < 80:
            continue
        itv_by_step: Dict[int, int] = {}
        for e in evs:
            if e.step_idx not in itv_by_step:
                itv_by_step[e.step_idx] = e.itv_ms
        series[mode].append(_ffill_itv(args.n_steps, itv_by_step))

    if not series["P"] or not series["U"]:
        raise SystemExit("missing P or U trials in RX dir")

    # event-triggered P(100ms) around selected transitions
    def compute_p100(mode: str) -> List[float]:
        acc = [0.0] * (2 * window_steps + 1)
        denom = 0
        for itv in series[mode]:
            for t0 in subset_steps:
                if t0 - window_steps < 0 or t0 + window_steps >= args.n_steps:
                    continue
                denom += 1
                for i, dt in enumerate(range(-window_steps, window_steps + 1)):
                    acc[i] += 1.0 if itv[t0 + dt] == 100 else 0.0
        if denom == 0:
            return [0.0] * len(acc)
        return [v / denom for v in acc]

    p100_p = compute_p100("P")
    p100_u = compute_p100("U")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    # write selected transitions list
    with (args.out_dir / "selected_transitions.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["transition_step"])
        for s in subset_steps:
            w.writerow([s])

    _plot_event_triggered_svg(
        args.out_dir / "fig_event_triggered_p100_conditional.svg",
        title=_svg_escape(f"D4B conditional timing: P(100ms) around transitions ({args.subset}, topK={args.top_k})"),
        window_steps=window_steps,
        p100_policy=p100_p,
        p100_uonly=p100_u,
    )


if __name__ == "__main__":
    main()
