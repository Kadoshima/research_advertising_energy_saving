#!/usr/bin/env python3
"""
D4B story analysis (no new data):
  - Extract per-transition TL and outage events (TL>tau) exactly as the v5 scripts do:
      * truth transitions by 100ms grid
      * align RX timestamps by per-trial constant offset (median(step_idx*100ms - rx_ms))
      * TL at transition = time until first received packet whose *truth label == new label* after the transition
        (indexing RX events by label)
  - Rank which transitions contribute most to Pout(1s)
  - Generate a single failure-centered "story timeline" SVG comparing U-only vs Policy(U+CCS)

Outputs (out_dir):
  - per_transition.csv
  - outage_ranking.csv
  - selected_event.json
  - fig_outage_timeline.svg

No external dependencies.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DT_MS = 100


@dataclass(frozen=True)
class RxEvent:
    rx_ms: float
    step_idx: int
    truth_label: int
    itv_ms: int
    mode: str  # "P" or "U"


@dataclass(frozen=True)
class Trial:
    path: Path
    mode: str  # "P" or "U"
    offset_ms: float
    aligned_events: List[Tuple[float, int, int, int]]  # (aligned_ms, truth_label, step_idx, itv_ms)
    itv_by_step: Dict[int, int]
    lbl_by_step: Dict[int, int]


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
        lbl = int(parts[1])
        itv = int(parts[2])
    except Exception:
        return None
    if itv not in (100, 500):
        return None
    return mode, lbl, itv


def _read_rx_events(path: Path, n_steps: int) -> List[RxEvent]:
    evs: List[RxEvent] = []
    with path.open(newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            parsed = _parse_tag(row.get("label") or "")
            if parsed is None:
                continue
            mode, lbl, itv = parsed
            step = _parse_step_idx_from_mfd(row.get("mfd") or "")
            if step is None or not (0 <= step < n_steps):
                continue
            try:
                rx_ms = float(row.get("ms") or "")
            except Exception:
                continue
            evs.append(RxEvent(rx_ms=rx_ms, step_idx=step, truth_label=lbl, itv_ms=itv, mode=mode))
    return evs


def _dominant_mode(events: List[RxEvent]) -> Optional[str]:
    c: Dict[str, int] = {"P": 0, "U": 0}
    for e in events:
        if e.mode in c:
            c[e.mode] += 1
    if c["P"] == 0 and c["U"] == 0:
        return None
    return "P" if c["P"] >= c["U"] else "U"


def _estimate_offset_ms(events: List[RxEvent]) -> Tuple[float, int]:
    first_ms: Dict[int, float] = {}
    for e in events:
        if e.step_idx not in first_ms:
            first_ms[e.step_idx] = e.rx_ms
    if not first_ms:
        return 0.0, 0
    offsets = [(idx * DT_MS) - ms for idx, ms in first_ms.items()]
    offsets.sort()
    return float(statistics.median(offsets)), len(offsets)


def _build_trial(path: Path, n_steps: int) -> Optional[Trial]:
    events = _read_rx_events(path, n_steps=n_steps)
    if not events:
        return None
    mode = _dominant_mode(events)
    if mode is None:
        return None
    events = [e for e in events if e.mode == mode]
    if len(events) < 80:
        return None

    offset_ms, _ = _estimate_offset_ms(events)
    aligned: List[Tuple[float, int, int, int]] = []
    itv_by_step: Dict[int, int] = {}
    lbl_by_step: Dict[int, int] = {}
    for e in events:
        aligned_ms = e.rx_ms + offset_ms
        aligned.append((aligned_ms, e.truth_label, e.step_idx, e.itv_ms))
        if e.step_idx not in itv_by_step:
            itv_by_step[e.step_idx] = e.itv_ms
        if e.step_idx not in lbl_by_step:
            lbl_by_step[e.step_idx] = e.truth_label
    aligned.sort(key=lambda x: x[0])
    return Trial(path=path, mode=mode, offset_ms=offset_ms, aligned_events=aligned, itv_by_step=itv_by_step, lbl_by_step=lbl_by_step)


def _compute_tl_list(
    truth_labels: List[int],
    aligned_events: List[Tuple[float, int, int, int]],
) -> Tuple[List[float], List[Optional[int]]]:
    # transitions: at step i (i>=1), new label = truth_labels[i]
    transitions: List[Tuple[float, int]] = []
    prev = truth_labels[0]
    for i in range(1, len(truth_labels)):
        cur = truth_labels[i]
        if cur != prev:
            transitions.append((i * DT_MS, cur))
        prev = cur

    events_by_label: Dict[int, List[Tuple[float, int]]] = {}
    for t_ms, lbl, step, _itv in aligned_events:
        events_by_label.setdefault(lbl, []).append((t_ms, step))
    for lbl in events_by_label:
        events_by_label[lbl].sort()

    tl_s: List[float] = []
    arrival_step: List[Optional[int]] = []
    for t_ms, new_lbl in transitions:
        arr = events_by_label.get(new_lbl) or []
        found: Optional[Tuple[float, int]] = None
        for ms, step in arr:
            if ms >= t_ms:
                found = (ms, step)
                break
        if found is None:
            tl_s.append(float("inf"))
            arrival_step.append(None)
        else:
            tl_s.append((found[0] - t_ms) / 1000.0)
            arrival_step.append(found[1])
    return tl_s, arrival_step


def _svg_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _fmt(v: float, digits: int = 2) -> str:
    if math.isnan(v) or math.isinf(v):
        return "NA"
    return f"{v:.{digits}f}"


def _write_csv(path: Path, header: List[str], rows: List[List[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _ffill_series(n_steps: int, by_step: Dict[int, int]) -> List[int]:
    if not by_step:
        return [500] * n_steps
    first = min(by_step.keys())
    cur = by_step[first]
    out = [cur] * n_steps
    for t in range(n_steps):
        if t in by_step:
            cur = by_step[t]
        out[t] = cur
    return out


def _plot_story_svg(
    out_svg: Path,
    title: str,
    truth_step: int,
    truth_new_label: int,
    window_steps: int,
    u_trial: Trial,
    u_tl: float,
    u_arr_step: Optional[int],
    p_trial: Trial,
    p_tl: float,
    p_arr_step: Optional[int],
    n_steps: int,
) -> None:
    width, height = 1000, 560
    ml, mr, mt, mb = 80, 30, 70, 60
    row_h = 200
    pw = width - ml - mr
    axis = "#111827"
    grid = "#e5e7eb"
    bg = "#ffffff"
    c100 = "#ef4444"
    c500 = "#3b82f6"
    c_hit = "#10b981"
    c_miss = "#111827"

    # Expand window to include arrival step if outside.
    lo = max(0, truth_step - window_steps)
    hi = min(n_steps - 1, truth_step + window_steps)
    for arr in [u_arr_step, p_arr_step]:
        if arr is not None:
            lo = min(lo, max(0, arr - window_steps))
            hi = max(hi, min(n_steps - 1, arr + window_steps))
    span = max(1, hi - lo)

    def xpx(step: int) -> float:
        return ml + (step - lo) * pw / span

    def rel_s(step: int) -> float:
        return (step - truth_step) * DT_MS / 1000.0

    svg: List[str] = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append('<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#111827"/></marker></defs>')
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>')
    svg.append(f'<text x="{width/2:.1f}" y="38" font-size="20" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(title)}</text>')
    svg.append(f'<rect x="{ml}" y="{mt}" width="{pw}" height="{row_h*2}" fill="none" stroke="{axis}" stroke-width="1.2"/>')

    # x ticks in seconds
    for i in range(7):
        step = lo + int(round(span * i / 6))
        px = xpx(step)
        svg.append(f'<line x1="{px:.2f}" y1="{mt}" x2="{px:.2f}" y2="{mt+row_h*2}" stroke="{grid}" stroke-width="1"/>')
        svg.append(f'<text x="{px:.2f}" y="{mt+row_h*2+28}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_fmt(rel_s(step),1)}</text>')
    svg.append(f'<text x="{ml+pw/2:.1f}" y="{height-22}" font-size="14" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">time relative to selected transition [s]</text>')

    # transition line
    px0 = xpx(truth_step)
    svg.append(f'<line x1="{px0:.2f}" y1="{mt}" x2="{px0:.2f}" y2="{mt+row_h*2}" stroke="#6b7280" stroke-width="2" stroke-dasharray="6 4"/>')
    svg.append(f'<text x="{px0+6:.2f}" y="{mt-10}" font-size="12" fill="#6b7280" font-family="ui-sans-serif, system-ui, -apple-system">truth transition (label={truth_new_label})</text>')

    def draw_row(y0: int, name: str, tr: Trial, tl: float, arr_step: Optional[int]) -> None:
        itv = _ffill_series(n_steps, tr.itv_by_step)
        y_band = y0 + 28
        h_band = 26
        y_rx = y0 + 84
        y_arrow = y0 + 140

        svg.append(f'<text x="{ml}" y="{y0+18}" font-size="13" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">{_svg_escape(name)} (TL={_fmt(tl,2)}s)</text>')

        # interval blocks
        cur = itv[lo]
        seg_start = lo
        for t in range(lo + 1, hi + 2):
            v = itv[t] if t <= hi else None
            if v != cur:
                x1 = xpx(seg_start)
                x2 = xpx(t - 1)
                w = max(1.0, x2 - x1)
                col = c100 if cur == 100 else c500
                svg.append(f'<rect x="{x1:.2f}" y="{y_band:.2f}" width="{w:.2f}" height="{h_band}" fill="{col}" opacity="0.22"/>')
                seg_start = t
                cur = v
        svg.append(f'<text x="{ml+6}" y="{y_band+18}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">interval</text>')

        # RX marks; green if new label, black otherwise
        for step, lbl in tr.lbl_by_step.items():
            if step < lo or step > hi:
                continue
            px = xpx(step)
            col = c_hit if lbl == truth_new_label and step >= truth_step else c_miss
            svg.append(f'<line x1="{px:.2f}" y1="{y_rx:.2f}" x2="{px:.2f}" y2="{y_rx+18:.2f}" stroke="{col}" stroke-width="1.4" opacity="0.9"/>')
        svg.append(f'<text x="{ml+6}" y="{y_rx+14}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">RX (green=new label)</text>')

        # TL arrow to arrival
        if arr_step is not None:
            px1 = xpx(arr_step)
            svg.append(f'<line x1="{px0:.2f}" y1="{y_arrow:.2f}" x2="{px1:.2f}" y2="{y_arrow:.2f}" stroke="{axis}" stroke-width="2" marker-end="url(#arr)"/>')
            svg.append(f'<text x="{(px0+px1)/2:.2f}" y="{y_arrow-8:.2f}" font-size="12" text-anchor="middle" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">TL</text>')

    draw_row(mt + 0 * row_h, "U-only (CCS-off)", u_trial, u_tl, u_arr_step)
    draw_row(mt + 1 * row_h, "Policy (U+CCS)", p_trial, p_tl, p_arr_step)

    # legend for hit/miss
    lx, ly = ml + pw - 260, mt + 10
    svg.append(f'<rect x="{lx}" y="{ly}" width="240" height="66" fill="#ffffff" stroke="{grid}" stroke-width="1"/>')
    svg.append(f'<line x1="{lx+14}" y1="{ly+22}" x2="{lx+14}" y2="{ly+40}" stroke="{c_hit}" stroke-width="2"/>')
    svg.append(f'<text x="{lx+26}" y="{ly+36}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">RX new-label packet</text>')
    svg.append(f'<line x1="{lx+14}" y1="{ly+46}" x2="{lx+14}" y2="{ly+64}" stroke="{c_miss}" stroke-width="2"/>')
    svg.append(f'<text x="{lx+26}" y="{ly+60}" font-size="12" fill="{axis}" font-family="ui-sans-serif, system-ui, -apple-system">RX other packet</text>')

    svg.append("</svg>\n")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(svg), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx-dir", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--title", type=str, default="D4B outage story (S4): failure-centered view")
    ap.add_argument(
        "--per-trial-csv",
        type=Path,
        default=None,
        help="Optional: restrict RX files to those listed in per_trial.csv (recommended to avoid mixed logs)",
    )
    ap.add_argument("--n-steps", type=int, default=1800)
    ap.add_argument("--tau-s", type=float, default=1.0)
    ap.add_argument("--window-s", type=float, default=3.0)
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    tau = args.tau_s
    window_steps = int(round(args.window_s * 1000 / DT_MS))

    truth_labels = _read_truth_labels(args.truth, n_steps=args.n_steps)
    transitions = _extract_transitions(truth_labels)
    if not transitions:
        raise SystemExit("no transitions found in truth")

    trials: List[Trial] = []
    rx_files: List[Path] = []
    if args.per_trial_csv is not None:
        # Use only policy + U-only RX files from per_trial.csv to avoid contamination from other conditions.
        with args.per_trial_csv.open(newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                cond = (row.get("condition") or "").strip()
                if cond not in ("S4_policy", "S4_ablation_ccs_off"):
                    continue
                p = (row.get("rx_path") or "").strip()
                if not p:
                    continue
                rx_files.append(Path(p))
        # de-dup while preserving order
        seen = set()
        rx_files = [p for p in rx_files if not (str(p) in seen or seen.add(str(p)))]
    else:
        rx_files = sorted(args.rx_dir.glob("rx_trial_*.csv"))

    for p in rx_files:
        t = _build_trial(p, n_steps=args.n_steps)
        if t is not None:
            trials.append(t)
    if not trials:
        raise SystemExit("no usable trials")

    # Per-transition extraction
    per_rows: List[List[object]] = []
    # Aggregate per transition across trials
    agg: Dict[Tuple[str, int], Dict[str, float]] = {}

    for tr in trials:
        tl_list, arr_steps = _compute_tl_list(truth_labels, tr.aligned_events)
        if len(tl_list) != len(transitions):
            raise SystemExit("internal mismatch in transitions length")
        for idx, step in enumerate(transitions):
            new_lbl = truth_labels[step]
            tl = tl_list[idx]
            arr_step = arr_steps[idx]
            outage = 1 if (tl == float("inf") or tl > tau) else 0
            per_rows.append([tr.path.name, tr.mode, step, truth_labels[step - 1], new_lbl, tl, outage, "" if arr_step is None else arr_step, tr.offset_ms])

            key = (tr.mode, step)
            a = agg.setdefault(key, {"n": 0.0, "out": 0.0, "tl_sum": 0.0})
            a["n"] += 1.0
            a["out"] += float(outage)
            if tl != float("inf"):
                a["tl_sum"] += float(tl)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        args.out_dir / "per_transition.csv",
        ["rx_file", "mode", "transition_step", "label_prev", "label_cur", "tl_s", "outage_gt_tau", "arrival_step", "offset_ms"],
        per_rows,
    )

    # Ranking by outage-rate difference (U - P)
    ranking: List[List[object]] = []
    for step in transitions:
        np_ = agg.get(("P", step), {}).get("n", 0.0)
        nu_ = agg.get(("U", step), {}).get("n", 0.0)
        p_out = agg.get(("P", step), {}).get("out", 0.0)
        u_out = agg.get(("U", step), {}).get("out", 0.0)
        p_rate = (p_out / np_) if np_ else float("nan")
        u_rate = (u_out / nu_) if nu_ else float("nan")
        ranking.append([step, truth_labels[step - 1], truth_labels[step], p_out, np_, p_rate, u_out, nu_, u_rate, (u_rate - p_rate) if (not math.isnan(u_rate) and not math.isnan(p_rate)) else float("nan")])
    ranking.sort(key=lambda r: (r[-1], r[6]), reverse=True)
    _write_csv(
        args.out_dir / "outage_ranking.csv",
        ["transition_step", "label_prev", "label_cur", "policy_out_n", "policy_n", "policy_out_rate", "u_only_out_n", "u_only_n", "u_only_out_rate", "u_minus_p_out_rate"],
        ranking,
    )

    # Choose a transition where U-only has more outages than policy, else fall back to largest TL in U-only.
    selected_step = None
    for r in ranking:
        if r[6] > r[3]:
            selected_step = int(r[0])
            break
    if selected_step is None:
        selected_step = int(ranking[0][0])

    # Pick representative trials (U: max TL, P: min TL) at that transition
    def pick_trial(mode: str, want_max: bool) -> Tuple[Trial, float, Optional[int]]:
        best = None
        # Recompute TL list for each candidate and take the specific transition index.
        for tr in trials:
            if tr.mode != mode:
                continue
            tl_list, arr_steps = _compute_tl_list(truth_labels, tr.aligned_events)
            idx = transitions.index(selected_step)
            tl = tl_list[idx]
            arr = arr_steps[idx]
            if tl == float("inf"):
                continue
            cand = (tr, tl, arr)
            if best is None:
                best = cand
            else:
                if want_max and cand[1] > best[1]:
                    best = cand
                if not want_max and cand[1] < best[1]:
                    best = cand
        if best is None:
            raise SystemExit(f"no candidate trials for mode={mode}")
        return best

    u_tr, u_tl, u_arr = pick_trial("U", want_max=True)
    p_tr, p_tl, p_arr = pick_trial("P", want_max=False)

    selected = {
        "transition_step": selected_step,
        "new_label": truth_labels[selected_step],
        "tau_s": tau,
        "window_s": args.window_s,
        "u_only_rx_file": u_tr.path.name,
        "u_only_tl_s": u_tl,
        "policy_rx_file": p_tr.path.name,
        "policy_tl_s": p_tl,
    }
    (args.out_dir / "selected_event.json").write_text(json.dumps(selected, indent=2), encoding="utf-8")

    _plot_story_svg(
        args.out_dir / "fig_outage_timeline.svg",
        title=f"{args.title} (TL>{tau:.1f}s)",
        truth_step=selected_step,
        truth_new_label=truth_labels[selected_step],
        window_steps=window_steps,
        u_trial=u_tr,
        u_tl=u_tl,
        u_arr_step=u_arr,
        p_trial=p_tr,
        p_tl=p_tl,
        p_arr_step=p_arr,
        n_steps=args.n_steps,
    )


if __name__ == "__main__":
    main()
