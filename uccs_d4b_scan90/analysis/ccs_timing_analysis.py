#!/usr/bin/env python3
"""
D4B (scan90, S4) analysis-only: visualize that CCS improves QoS by placing 100ms closer to transitions.

Inputs:
  - RX logs: rx_trial_*.csv (expects columns: ms, seq, label, mfd)
    - label example: "P4-03-100", "U4-03-500" (mode P=policy(U+CCS), U=U-only(CCS-off))
    - mfd example:   "<step_idx>_<tag>"
  - truth: stress_causal_S4.csv (expects columns: idx, label; dt=100ms)

Outputs (out_dir):
  - event_triggered_p100.csv : tau_s vs P(100ms) curves (policy vs u-only)
  - hit_cover_lag_summary.csv: per-condition summary of Hit/PreHit/Cover/Lag metrics
  - lag_cdf.csv              : CDF of lag-to-100 after transition
  - fig_event_triggered_p100.svg
  - fig_lag_cdf.svg
  - fig_hit_cover.svg

No external dependencies (no pandas/matplotlib).
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


DT_MS_DEFAULT = 100


@dataclass(frozen=True)
class RxObs:
    step_idx: int
    itv_ms: int
    mode: str  # "P" or "U"


def _read_truth_labels(truth_csv: Path, n_steps: int) -> List[int]:
    labels: List[int] = []
    with truth_csv.open(newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            labels.append(int(row["label"]))
            if len(labels) >= n_steps:
                break
    if len(labels) < n_steps:
        raise SystemExit(f"truth too short: {truth_csv} rows={len(labels)} < {n_steps}")
    return labels


def _read_truth_fields(truth_csv: Path, n_steps: int) -> Tuple[List[int], List[float], List[float]]:
    labels: List[int] = []
    us: List[float] = []
    ccss: List[float] = []
    with truth_csv.open(newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            labels.append(int(row["label"]))
            us.append(float(row.get("U") or "nan"))
            ccss.append(float(row.get("CCS") or "nan"))
            if len(labels) >= n_steps:
                break
    if len(labels) < n_steps:
        raise SystemExit(f"truth too short: {truth_csv} rows={len(labels)} < {n_steps}")
    return labels, us, ccss


def _extract_transitions(labels: List[int]) -> List[int]:
    out: List[int] = []
    for i in range(1, len(labels)):
        if labels[i] != labels[i - 1]:
            out.append(i)
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


def _parse_mode_and_itv(tag: str) -> Optional[Tuple[str, int]]:
    tag = (tag or "").strip()
    if not tag:
        return None
    # ex: P4-03-500 / U4-01-100
    if len(tag) < 2:
        return None
    mode = tag[0]
    if mode not in ("P", "U"):
        return None
    try:
        itv_ms = int(tag.split("-")[-1])
    except Exception:
        return None
    if itv_ms not in (100, 500):
        return None
    return mode, itv_ms


def _read_rx_trial(path: Path) -> List[RxObs]:
    obs: List[RxObs] = []
    with path.open(newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            tag = (row.get("label") or "").strip()
            parsed = _parse_mode_and_itv(tag)
            if parsed is None:
                continue
            mode, itv_ms = parsed
            step_idx = _parse_step_idx_from_mfd(row.get("mfd") or "")
            if step_idx is None:
                # fallback: seq
                try:
                    step_idx = int(row.get("seq") or "")
                except Exception:
                    continue
            obs.append(RxObs(step_idx=step_idx, itv_ms=itv_ms, mode=mode))
    return obs


def _build_itv_series(n_steps: int, obs: List[RxObs]) -> Optional[Tuple[str, List[int]]]:
    if not obs:
        return None
    # RXログはtrial境界で前後のパケットが少量混入し得るため、
    # そのtrialで支配的なmode（P/U）を採用し、他modeは捨てる。
    counts: Dict[str, int] = {"P": 0, "U": 0}
    for o in obs:
        if o.mode in counts:
            counts[o.mode] += 1
    mode = "P" if counts["P"] >= counts["U"] else "U"
    obs = [o for o in obs if o.mode == mode]
    if not obs:
        return None
    # Guard: a trial with only a handful of packets is likely contamination/noise.
    if len(obs) < 50:
        return None
    # step_idx -> itv, first-seen wins
    itv_by_step: Dict[int, int] = {}
    for o in obs:
        if 0 <= o.step_idx < n_steps and o.step_idx not in itv_by_step:
            itv_by_step[o.step_idx] = o.itv_ms
    if not itv_by_step:
        return None
    first_step = min(itv_by_step.keys())
    cur = itv_by_step[first_step]
    series: List[int] = [cur] * n_steps
    for t in range(n_steps):
        if t in itv_by_step:
            cur = itv_by_step[t]
        series[t] = cur
    return mode, series


def _mean(xs: Iterable[float]) -> float:
    xs = list(xs)
    if not xs:
        return float("nan")
    return sum(xs) / len(xs)


def _cdf(values_s: List[float], xs_s: List[float]) -> List[float]:
    if not values_s:
        return [float("nan")] * len(xs_s)
    vs = sorted(values_s)
    out: List[float] = []
    n = len(vs)
    j = 0
    for x in xs_s:
        while j < n and vs[j] <= x + 1e-12:
            j += 1
        out.append(j / n)
    return out


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


def _plot_lines_svg(
    out_svg: Path,
    title: str,
    x_label: str,
    y_label: str,
    xs: List[float],
    series: List[Tuple[str, List[float], str]],
    y_min: float = 0.0,
    y_max: float = 1.0,
) -> None:
    width, height = 920, 560
    ml, mr, mt, mb = 80, 30, 60, 70
    pw, ph = width - ml - mr, height - mt - mb
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = y_min, y_max

    def xpx(x: float) -> float:
        return ml + (x - xmin) * pw / (xmax - xmin) if xmax > xmin else ml + pw / 2

    def ypx(y: float) -> float:
        return mt + (ymax - y) * ph / (ymax - ymin) if ymax > ymin else mt + ph / 2

    axis = "#111827"
    grid = "#e5e7eb"
    bg = "#ffffff"

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    lines.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>')
    lines.append(f'<text x="{width/2:.1f}" y="34" font-size="20" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(title)}</text>')
    lines.append(f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" fill="none" stroke="{axis}" stroke-width="1.2"/>')

    # ticks
    for i in range(6):
        tx = xmin + (xmax - xmin) * i / 5.0
        px = xpx(tx)
        lines.append(f'<line x1="{px:.2f}" y1="{mt}" x2="{px:.2f}" y2="{mt+ph}" stroke="{grid}" stroke-width="1"/>')
        lines.append(f'<text x="{px:.2f}" y="{mt+ph+24}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(tx, 1)}</text>')
    for i in range(6):
        ty = ymin + (ymax - ymin) * i / 5.0
        py = ypx(ty)
        lines.append(f'<line x1="{ml}" y1="{py:.2f}" x2="{ml+pw}" y2="{py:.2f}" stroke="{grid}" stroke-width="1"/>')
        lines.append(f'<text x="{ml-10}" y="{py+4:.2f}" font-size="12" text-anchor="end" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(ty, 2)}</text>')

    # axis labels
    lines.append(f'<text x="{ml+pw/2:.1f}" y="{height-24}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(x_label)}</text>')
    lines.append(f'<text x="22" y="{mt+ph/2:.1f}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system" transform="rotate(-90 22 {mt+ph/2:.1f})">{_svg_escape(y_label)}</text>')

    # series
    for name, ys, color in series:
        pts = [f"{xpx(x):.2f},{ypx(y):.2f}" for x, y in zip(xs, ys)]
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{" ".join(pts)}"/>')
        # marker at tau=0
        if 0.0 >= xmin and 0.0 <= xmax:
            i0 = min(range(len(xs)), key=lambda i: abs(xs[i] - 0.0))
            lines.append(f'<circle cx="{xpx(xs[i0]):.2f}" cy="{ypx(ys[i0]):.2f}" r="4.5" fill="{color}"/>')

    # legend
    lx, ly = ml + 10, mt + 10
    lines.append(f'<rect x="{lx-6}" y="{ly-6}" width="260" height="{26*len(series)+12}" fill="#ffffff" stroke="{grid}" stroke-width="1"/>')
    for i, (name, _, color) in enumerate(series):
        cy = ly + 18 + i * 26
        lines.append(f'<line x1="{lx}" y1="{cy}" x2="{lx+28}" y2="{cy}" stroke="{color}" stroke-width="4"/>')
        lines.append(f'<text x="{lx+36}" y="{cy+5}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(name)}</text>')

    lines.append("</svg>\n")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(lines), encoding="utf-8")


def _plot_bars_svg(
    out_svg: Path,
    title: str,
    items: List[Tuple[str, float, str]],
    y_label: str,
    y_max: float,
) -> None:
    width, height = 920, 520
    ml, mr, mt, mb = 80, 30, 60, 70
    pw, ph = width - ml - mr, height - mt - mb
    axis = "#111827"
    grid = "#e5e7eb"
    bg = "#ffffff"

    def ypx(v: float) -> float:
        return mt + (y_max - v) * ph / y_max if y_max > 0 else mt + ph

    n = len(items)
    bar_w = pw / max(1, (n * 1.6))
    gap = bar_w * 0.6
    start = ml + (pw - (n * bar_w + (n - 1) * gap)) / 2

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    lines.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>')
    lines.append(f'<text x="{width/2:.1f}" y="34" font-size="20" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(title)}</text>')
    lines.append(f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" fill="none" stroke="{axis}" stroke-width="1.2"/>')
    for i in range(6):
        ty = y_max * i / 5.0
        py = ypx(ty)
        lines.append(f'<line x1="{ml}" y1="{py:.2f}" x2="{ml+pw}" y2="{py:.2f}" stroke="{grid}" stroke-width="1"/>')
        lines.append(f'<text x="{ml-10}" y="{py+4:.2f}" font-size="12" text-anchor="end" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(ty, 2)}</text>')

    lines.append(f'<text x="22" y="{mt+ph/2:.1f}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system" transform="rotate(-90 22 {mt+ph/2:.1f})">{_svg_escape(y_label)}</text>')

    for i, (name, val, color) in enumerate(items):
        x = start + i * (bar_w + gap)
        y = ypx(val)
        h = mt + ph - y
        lines.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{color}" opacity="0.9"/>')
        lines.append(f'<text x="{x+bar_w/2:.2f}" y="{mt+ph+24}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(name)}</text>')
        lines.append(f'<text x="{x+bar_w/2:.2f}" y="{y-6:.2f}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(val, 3)}</text>')

    lines.append("</svg>\n")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx-dir", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--n-steps", type=int, default=1800)
    ap.add_argument("--dt-ms", type=int, default=DT_MS_DEFAULT)
    ap.add_argument("--window-s", type=float, default=2.0)
    ap.add_argument("--hit-s", type=float, default=1.0)
    ap.add_argument("--prehit-s", type=float, default=0.5)
    ap.add_argument("--cover-s", type=float, default=1.0)
    args = ap.parse_args()

    n_steps = args.n_steps
    dt_ms = args.dt_ms
    w_steps = int(round(args.window_s * 1000 / dt_ms))
    hit_steps = int(round(args.hit_s * 1000 / dt_ms))
    pre_steps = int(round(args.prehit_s * 1000 / dt_ms))
    cover_steps = int(round(args.cover_s * 1000 / dt_ms))

    truth_labels, truth_u, truth_ccs = _read_truth_fields(args.truth, n_steps=n_steps)
    transitions = _extract_transitions(truth_labels)
    if not transitions:
        raise SystemExit("no transitions found in truth")

    # Build per-trial interval series for policy (P) and u-only (U)
    series_by_mode: Dict[str, List[List[int]]] = {"P": [], "U": []}
    for p in sorted(args.rx_dir.glob("rx_trial_*.csv")):
        obs = _read_rx_trial(p)
        built = _build_itv_series(n_steps=n_steps, obs=obs)
        if built is None:
            continue
        mode, series = built
        if mode in series_by_mode:
            series_by_mode[mode].append(series)

    if not series_by_mode["P"] or not series_by_mode["U"]:
        raise SystemExit(f"not enough trials: policy={len(series_by_mode['P'])}, u_only={len(series_by_mode['U'])}")

    taus = list(range(-w_steps, w_steps + 1))
    tau_s = [t * dt_ms / 1000.0 for t in taus]

    def event_triggered_p100(mode: str) -> List[float]:
        ys: List[float] = []
        trials = series_by_mode[mode]
        for tau in taus:
            vals: List[float] = []
            for k in transitions:
                t = k + tau
                if t < 0 or t >= n_steps:
                    continue
                for s in trials:
                    vals.append(1.0 if s[t] == 100 else 0.0)
            ys.append(_mean(vals))
        return ys

    p100_policy = event_triggered_p100("P")
    p100_uonly = event_triggered_p100("U")

    _write_csv(
        args.out_dir / "event_triggered_p100.csv",
        ["tau_s", "p100_policy", "p100_u_only"],
        [[tau_s[i], p100_policy[i], p100_uonly[i]] for i in range(len(tau_s))],
    )

    # Hit/PreHit/Cover/Lag metrics
    def compute_metrics(mode: str) -> Tuple[float, float, float, List[float]]:
        trials = series_by_mode[mode]
        hit_flags: List[float] = []
        pre_flags: List[float] = []
        covers: List[float] = []
        lags_s: List[float] = []
        for k in transitions:
            # aggregate over trials, then average over transitions
            for s in trials:
                w0 = max(0, k - cover_steps)
                w1 = min(n_steps - 1, k + cover_steps)
                window = s[w0 : w1 + 1]
                covers.append(sum(1 for v in window if v == 100) / len(window))

                hit_w = s[k : min(n_steps, k + hit_steps + 1)]
                hit_flags.append(1.0 if any(v == 100 for v in hit_w) else 0.0)

                pre_w = s[max(0, k - pre_steps) : k + 1]
                pre_flags.append(1.0 if any(v == 100 for v in pre_w) else 0.0)

                lag = None
                for t in range(k, n_steps):
                    if s[t] == 100:
                        lag = (t - k) * dt_ms / 1000.0
                        break
                if lag is not None:
                    lags_s.append(lag)
        return _mean(hit_flags), _mean(pre_flags), _mean(covers), lags_s

    hit_p, pre_p, cov_p, lags_p = compute_metrics("P")
    hit_u, pre_u, cov_u, lags_u = compute_metrics("U")

    _write_csv(
        args.out_dir / "hit_cover_lag_summary.csv",
        ["condition", "n_trials", "hit_rate", "pre_hit_rate", "cover_ratio", "lag_median_s", "lag_p90_s"],
        [
            ["policy(U+CCS)", len(series_by_mode["P"]), hit_p, pre_p, cov_p, float("nan") if not lags_p else sorted(lags_p)[len(lags_p)//2], float("nan") if not lags_p else sorted(lags_p)[int(0.9*(len(lags_p)-1))]],
            ["u_only(CCS-off)", len(series_by_mode["U"]), hit_u, pre_u, cov_u, float("nan") if not lags_u else sorted(lags_u)[len(lags_u)//2], float("nan") if not lags_u else sorted(lags_u)[int(0.9*(len(lags_u)-1))]],
        ],
    )

    # lag CDF
    xs = [i * 0.1 for i in range(0, int(round(args.window_s / 0.1)) + 1)]
    cdf_p = _cdf(lags_p, xs)
    cdf_u = _cdf(lags_u, xs)
    _write_csv(
        args.out_dir / "lag_cdf.csv",
        ["x_s", "cdf_policy", "cdf_u_only"],
        [[xs[i], cdf_p[i], cdf_u[i]] for i in range(len(xs))],
    )

    # Plots
    _plot_lines_svg(
        args.out_dir / "fig_event_triggered_p100.svg",
        title=f"D4B timing (S4, scan90): P(100ms) around truth transitions (±{args.window_s:.1f}s)",
        x_label="relative time from transition [s]",
        y_label="P(interval=100ms)",
        xs=tau_s,
        series=[
            ("policy (U+CCS)", p100_policy, "#10b981"),
            ("u-only (CCS-off)", p100_uonly, "#f59e0b"),
        ],
        y_min=0.0,
        y_max=1.0,
    )

    _plot_lines_svg(
        args.out_dir / "fig_lag_cdf.svg",
        title="D4B timing (S4, scan90): CDF of lag-to-100ms after transition",
        x_label="time since transition [s]",
        y_label="CDF",
        xs=xs,
        series=[
            ("policy (U+CCS)", cdf_p, "#10b981"),
            ("u-only (CCS-off)", cdf_u, "#f59e0b"),
        ],
        y_min=0.0,
        y_max=1.0,
    )

    _plot_bars_svg(
        args.out_dir / "fig_hit_cover.svg",
        title="D4B timing (S4, scan90): transition hit/prehit/cover (mean over transitions×trials)",
        items=[
            ("hit@1s P", hit_p, "#10b981"),
            ("hit@1s U", hit_u, "#f59e0b"),
            ("pre@0.5s P", pre_p, "#10b981"),
            ("pre@0.5s U", pre_u, "#f59e0b"),
            ("cover±1s P", cov_p, "#10b981"),
            ("cover±1s U", cov_u, "#f59e0b"),
        ],
        y_label="ratio",
        y_max=1.0,
    )

    # Allocation efficiency: does 100ms land on high-CCS steps?
    def topq_indices(values: List[float], q: float) -> List[int]:
        vv = [(i, v) for i, v in enumerate(values) if not (math.isnan(v) or math.isinf(v))]
        if not vv:
            return []
        vv.sort(key=lambda x: x[1], reverse=True)
        k = max(1, int(round(len(vv) * q)))
        return [i for i, _ in vv[:k]]

    # In this project, CCS is sometimes stored as "stability-like" (high=stable).
    # For "transition-likeness" we use CCS_change = 1 - CCS.
    truth_ccs_change: List[float] = []
    for v in truth_ccs:
        if math.isnan(v) or math.isinf(v):
            truth_ccs_change.append(float("nan"))
        else:
            truth_ccs_change.append(1.0 - v)

    top_ccs_change = set(topq_indices(truth_ccs_change, 0.10))  # top-10% (1-CCS)
    top_u = set(topq_indices(truth_u, 0.10))  # top-10% U

    def alloc_metrics(mode: str) -> Tuple[float, float, float, float, float]:
        trials = series_by_mode[mode]
        if not trials:
            return float("nan"), float("nan"), float("nan"), float("nan"), float("nan")
        mean_ccs_all = _mean(v for v in truth_ccs_change if not (math.isnan(v) or math.isinf(v)))
        # average across trials
        ccs_when100: List[float] = []
        cover_top_ccs: List[float] = []
        cover_top_u: List[float] = []
        for s in trials:
            idx100 = [i for i, itv in enumerate(s) if itv == 100]
            if idx100:
                ccs_when100.append(
                    _mean(
                        truth_ccs_change[i]
                        for i in idx100
                        if not (math.isnan(truth_ccs_change[i]) or math.isinf(truth_ccs_change[i]))
                    )
                )
            if top_ccs_change:
                cover_top_ccs.append(sum(1 for i in top_ccs_change if s[i] == 100) / len(top_ccs_change))
            if top_u:
                cover_top_u.append(sum(1 for i in top_u if s[i] == 100) / len(top_u))
        return mean_ccs_all, _mean(ccs_when100), _mean(cover_top_ccs), _mean(cover_top_u), _mean([sum(1 for itv in s if itv == 100) / len(s) for s in trials])

    ccs_all_p, ccs_100_p, topccs_p, topu_p, share_p = alloc_metrics("P")
    ccs_all_u, ccs_100_u, topccs_u, topu_u, share_u = alloc_metrics("U")

    _write_csv(
        args.out_dir / "alloc_efficiency_summary.csv",
        [
            "condition",
            "n_trials",
            "share100_time",
            "mean_CCS_change_all",
            "mean_CCS_change_when100",
            "top10pct_CCS_change_covered_by100",
            "top10pct_U_covered_by100",
        ],
        [
            ["policy(U+CCS)", len(series_by_mode["P"]), share_p, ccs_all_p, ccs_100_p, topccs_p, topu_p],
            ["u_only(CCS-off)", len(series_by_mode["U"]), share_u, ccs_all_u, ccs_100_u, topccs_u, topu_u],
        ],
    )

    _plot_bars_svg(
        args.out_dir / "fig_alloc_efficiency.svg",
        title="D4B timing (S4, scan90): allocation efficiency of 100ms (higher=better)",
        items=[
            ("top10 (1-CCS) P", topccs_p, "#10b981"),
            ("top10 (1-CCS) U", topccs_u, "#f59e0b"),
            ("mean (1-CCS)|100 P", ccs_100_p, "#10b981"),
            ("mean (1-CCS)|100 U", ccs_100_u, "#f59e0b"),
        ],
        y_label="ratio / score",
        y_max=max(1.0, topccs_p, topccs_u, ccs_100_p, ccs_100_u),
    )


if __name__ == "__main__":
    main()
