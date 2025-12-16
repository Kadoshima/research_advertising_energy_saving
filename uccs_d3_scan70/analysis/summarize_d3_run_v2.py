#!/usr/bin/env python3
"""
Summarize uccs_d3_scan70 run (RX + TXSD) and compute TL/Pout using step_idx-aligned payload.

This pairs RX↔TXSD by file modification time order because TXSD trial index is allocated per tag/cond
and is not globally monotonic.

Step D3 (scan duty down):
  - S4 only
  - 3 conditions × 3 repeats = 9 trials
    - S4_fixed100
    - S4_fixed500
    - S4_policy
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


TRUTH_DT_MS = 100
TAU_VALUES_S = (1.0, 2.0, 3.0)
VALID_MIN_DURATION_MS = 160_000  # ~180s trials

TAG_RE = re.compile(r"^(?P<mode>[FP])(?P<sess>[14])-(?P<label>\d+)-(?P<itv>\d+)$")
RX_TRIAL_RE = re.compile(r"rx_trial_(?P<id>\d+)\.csv$")
TXSD_NAME_RE = re.compile(r"trial_(?P<idx>\d+)_c(?P<cond>\d+)_(?P<tag>.+)\.csv$")


@dataclass(frozen=True)
class RxEvent:
    rx_ms: float
    step_idx: int
    truth_label: int
    itv_ms: int
    tag: str


@dataclass
class RxTrial:
    rx_id: int
    path: Path
    duration_ms: float
    mode: str  # F/P
    fixed_itv: Optional[int]
    events: List[RxEvent]


@dataclass
class TxsdTrial:
    path: Path
    mtime_s: float
    trial_idx: int
    cond_id: int
    tag: str
    ms_total: float
    adv_count: int
    e_total_mj: float
    avg_power_mw: float


def read_truth_labels(path: Path, n_steps: int) -> List[int]:
    labels: List[int] = []
    with path.open(newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            labels.append(int(row["label"]))
            if len(labels) >= n_steps:
                break
    if len(labels) < n_steps:
        raise SystemExit(f"truth too short: {path} rows={len(labels)} < {n_steps}")
    return labels


def read_rx_trial(path: Path) -> RxTrial:
    m = RX_TRIAL_RE.search(path.name)
    if not m:
        raise ValueError(f"not rx_trial: {path}")
    rx_id = int(m.group("id"))

    events: List[RxEvent] = []
    last_ms: float = 0.0

    mode_c: Dict[str, int] = {"F": 0, "P": 0}
    itv_c: Dict[int, int] = {}

    with path.open(newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            try:
                rx_ms = float(row.get("ms") or 0.0)
            except Exception:
                continue
            last_ms = max(last_ms, rx_ms)

            try:
                step_idx = int(row.get("seq") or 0)
            except Exception:
                continue

            tag = (row.get("label") or "").strip()
            tm = TAG_RE.match(tag)
            if not tm:
                continue
            mode = tm.group("mode")
            sess = int(tm.group("sess"))
            if sess != 4:
                continue
            truth_label = int(tm.group("label"))
            itv_ms = int(tm.group("itv"))

            mode_c[mode] = mode_c.get(mode, 0) + 1
            itv_c[itv_ms] = itv_c.get(itv_ms, 0) + 1

            events.append(
                RxEvent(
                    rx_ms=rx_ms,
                    step_idx=step_idx,
                    truth_label=truth_label,
                    itv_ms=itv_ms,
                    tag=tag,
                )
            )

    if not events:
        raise ValueError(f"empty/invalid RX: {path}")

    mode = max(mode_c.items(), key=lambda kv: kv[1])[0]
    fixed_itv: Optional[int] = None
    if mode == "F":
        fixed_itv = max(itv_c.items(), key=lambda kv: kv[1])[0] if itv_c else None
        if fixed_itv not in (100, 500):
            raise ValueError(f"unexpected fixed interval {fixed_itv} in {path}")

    return RxTrial(rx_id=rx_id, path=path, duration_ms=last_ms, mode=mode, fixed_itv=fixed_itv, events=events)


def rx_bucket(t: RxTrial) -> str:
    if t.mode == "P":
        return "P4"
    return f"F4_{t.fixed_itv}"


def select_balanced_window(trials: List[RxTrial]) -> List[RxTrial]:
    candidates = [t for t in trials if t.duration_ms >= VALID_MIN_DURATION_MS]
    candidates.sort(key=lambda t: t.rx_id)
    if len(candidates) < 9:
        raise SystemExit(f"not enough valid RX trials (>= {VALID_MIN_DURATION_MS}ms): {len(candidates)}")

    want = {"F4_100", "F4_500", "P4"}
    best: Optional[List[RxTrial]] = None
    for start in range(0, len(candidates) - 9 + 1):
        window = candidates[start : start + 9]
        counts: Dict[str, int] = {}
        for t in window:
            counts[rx_bucket(t)] = counts.get(rx_bucket(t), 0) + 1
        if set(counts.keys()) == want and counts.get("F4_100", 0) == 3 and counts.get("F4_500", 0) == 3 and counts.get("P4", 0) == 3:
            best = window
    if not best:
        raise SystemExit("could not find balanced 9-trial RX window (F4_100/F4_500/P4 × 3 repeats)")
    return best


def estimate_offset_ms(events: List[RxEvent]) -> Tuple[float, int]:
    first_ms: Dict[int, float] = {}
    for e in sorted(events, key=lambda x: x.rx_ms):
        if e.step_idx not in first_ms:
            first_ms[e.step_idx] = e.rx_ms
    deltas: List[float] = []
    for step, ms in first_ms.items():
        if step <= 0:
            continue
        deltas.append(step * TRUTH_DT_MS - ms)
    if not deltas:
        return 0.0, 0
    return statistics.median(deltas), len(deltas)


def compute_tl_and_pout(truth_labels: List[int], aligned_events: List[Tuple[float, int]]) -> Tuple[float, float, Dict[float, float]]:
    transitions_ms: List[int] = []
    prev = truth_labels[0]
    for idx, lab in enumerate(truth_labels[1:], start=1):
        if lab != prev:
            transitions_ms.append(idx * TRUTH_DT_MS)
            prev = lab
    if not transitions_ms:
        return 0.0, 0.0, {tau: 0.0 for tau in TAU_VALUES_S}

    aligned_events_sorted = sorted(aligned_events, key=lambda x: x[0])
    tl_list_s: List[float] = []
    for t_ms in transitions_ms:
        idx = min(t_ms // TRUTH_DT_MS, len(truth_labels) - 1)
        true_label = truth_labels[idx]
        arrival: Optional[float] = None
        for ms, lbl in aligned_events_sorted:
            if ms > t_ms and lbl == true_label:
                arrival = ms
                break
        if arrival is None:
            tl_list_s.append(float("inf"))
        else:
            tl_list_s.append((arrival - t_ms) / 1000.0)

    finite = [x for x in tl_list_s if x != float("inf")]
    tl_mean = statistics.mean(finite) if finite else float("inf")
    tl_p95 = statistics.quantiles(finite, n=20)[18] if len(finite) >= 20 else (max(finite) if finite else float("inf"))
    pout: Dict[float, float] = {}
    for tau in TAU_VALUES_S:
        miss = sum(1 for x in tl_list_s if x == float("inf") or x > tau)
        pout[tau] = miss / len(tl_list_s)
    return tl_mean, tl_p95, pout


def parse_txsd_summary(path: Path) -> Optional[TxsdTrial]:
    m = TXSD_NAME_RE.match(path.name)
    if not m:
        return None
    trial_idx = int(m.group("idx"))
    cond_id = int(m.group("cond"))
    tag = m.group("tag")

    ms_total = None
    adv_count = None
    e_total_mj = None
    with path.open() as f:
        for line in f:
            if line.startswith("# summary"):
                parts = [p.strip() for p in line.strip().split(",")]
                kv: Dict[str, str] = {}
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        kv[k.strip("# ").strip()] = v.strip()
                ms_total = float(kv.get("ms_total")) if kv.get("ms_total") else None
                adv_count = int(kv.get("adv_count")) if kv.get("adv_count") else None
                e_total_mj = float(kv.get("E_total_mJ")) if kv.get("E_total_mJ") else None
                break
    if ms_total is None or adv_count is None or e_total_mj is None:
        return None
    if ms_total <= 0:
        return None
    avg_power = e_total_mj / (ms_total / 1000.0)
    return TxsdTrial(
        path=path,
        mtime_s=path.stat().st_mtime,
        trial_idx=trial_idx,
        cond_id=cond_id,
        tag=tag,
        ms_total=ms_total,
        adv_count=adv_count,
        e_total_mj=e_total_mj,
        avg_power_mw=avg_power,
    )


def estimate_rx_tag_share100_time_est(events: List[RxEvent]) -> Optional[float]:
    itv_by_step: Dict[int, int] = {}
    for e in events:
        if e.step_idx not in itv_by_step:
            itv_by_step[e.step_idx] = e.itv_ms
    n100 = sum(1 for v in itv_by_step.values() if v == 100)
    n500 = sum(1 for v in itv_by_step.values() if v == 500)
    denom_ms = n100 * 100 + n500 * 500
    if denom_ms <= 0:
        return None
    return (n100 * 100) / denom_ms


def mean_std(xs: List[float]) -> Tuple[float, float]:
    if not xs:
        return 0.0, 0.0
    if len(xs) == 1:
        return xs[0], 0.0
    return statistics.mean(xs), statistics.stdev(xs)


def condition_name(rx: RxTrial) -> str:
    if rx.mode == "F":
        return "S4_fixed100" if rx.fixed_itv == 100 else "S4_fixed500"
    return "S4_policy"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx-dir", type=Path, required=True)
    ap.add_argument("--txsd-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--truth-s4", type=Path, default=Path("Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv"))
    ap.add_argument("--n-steps", type=int, default=1800)
    args = ap.parse_args()

    truth = read_truth_labels(args.truth_s4, args.n_steps)

    rx_all: List[RxTrial] = []
    for p in sorted(args.rx_dir.glob("rx_trial_*.csv")):
        try:
            rx_all.append(read_rx_trial(p))
        except Exception:
            continue
    rx_trials = select_balanced_window(rx_all)
    rx_trials.sort(key=lambda t: t.rx_id)

    txsd_all: List[TxsdTrial] = []
    for p in sorted(args.txsd_dir.glob("trial_*.csv")):
        tt = parse_txsd_summary(p)
        if not tt:
            continue
        if tt.ms_total >= VALID_MIN_DURATION_MS:
            txsd_all.append(tt)
    txsd_all.sort(key=lambda t: t.mtime_s)
    if len(txsd_all) < len(rx_trials):
        raise SystemExit(f"not enough valid TXSD trials: {len(txsd_all)} < {len(rx_trials)}")
    txsd_trials = txsd_all[-len(rx_trials):]

    pairs = list(zip(rx_trials, txsd_trials))

    rep_counter: Dict[str, int] = {}
    per_rows: List[Dict[str, object]] = []
    for rx, tx in pairs:
        cond = condition_name(rx)
        rep_counter[cond] = rep_counter.get(cond, 0) + 1
        rep_idx = rep_counter[cond]

        offset_ms, offset_n = estimate_offset_ms(rx.events)
        aligned_events: List[Tuple[float, int]] = []
        step_set: set[int] = set()
        for e in rx.events:
            t_ms = e.rx_ms + offset_ms
            if 0.0 <= t_ms < (args.n_steps * TRUTH_DT_MS):
                aligned_events.append((t_ms, e.truth_label))
            if e.step_idx >= 0:
                step_set.add(e.step_idx)

        tl_mean, tl_p95, pout = compute_tl_and_pout(truth, aligned_events)
        rx_unique = len(step_set)
        pdr_unique = min(rx_unique, tx.adv_count) / tx.adv_count if tx.adv_count > 0 else 0.0
        share100 = estimate_rx_tag_share100_time_est(rx.events)

        per_rows.append(
            {
                "rx_trial_id": rx.rx_id,
                "condition": cond,
                "repeat_idx": rep_idx,
                "mode": ("POLICY" if rx.mode == "P" else f"FIXED_{rx.fixed_itv}"),
                "rx_count": len(rx.events),
                "rx_unique": rx_unique,
                "adv_count": tx.adv_count,
                "pdr_unique": round(pdr_unique, 6),
                "rx_tag_share100_time_est": (round(share100, 6) if share100 is not None else ""),
                "tl_mean_s": round(tl_mean, 6),
                "tl_p95_s": round(tl_p95, 6),
                "pout_1s": round(pout[1.0], 6),
                "pout_2s": round(pout[2.0], 6),
                "pout_3s": round(pout[3.0], 6),
                "tl_time_offset_ms": round(offset_ms, 3),
                "tl_time_offset_n": offset_n,
                "txsd_ms_total": tx.ms_total,
                "E_total_mJ": tx.e_total_mj,
                "avg_power_mW": tx.avg_power_mw,
                "txsd_mtime_s": round(tx.mtime_s, 3),
                "txsd_path": str(tx.path),
                "rx_path": str(rx.path),
            }
        )

    per_rows.sort(key=lambda r: int(r["rx_trial_id"]))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    per_path = args.out_dir / "per_trial.csv"
    with per_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_rows[0].keys()))
        w.writeheader()
        w.writerows(per_rows)

    by_cond: Dict[str, List[Dict[str, object]]] = {}
    for r in per_rows:
        by_cond.setdefault(str(r["condition"]), []).append(r)

    summary_rows: List[Dict[str, object]] = []
    for cond, rows in sorted(by_cond.items()):
        pout_1s_list = [float(r["pout_1s"]) for r in rows]
        tl_list = [float(r["tl_mean_s"]) for r in rows]
        pdr_list = [float(r["pdr_unique"]) for r in rows]
        pwr_list = [float(r["avg_power_mW"]) for r in rows]
        adv_list = [float(r["adv_count"]) for r in rows]
        share_list = [float(r["rx_tag_share100_time_est"]) for r in rows if r["rx_tag_share100_time_est"] != ""]

        pout_m, pout_s = mean_std(pout_1s_list)
        tl_m, tl_s = mean_std(tl_list)
        pdr_m, pdr_s = mean_std(pdr_list)
        pwr_m, pwr_s = mean_std(pwr_list)
        adv_m, adv_s = mean_std(adv_list)
        sh_m, sh_s = mean_std(share_list) if share_list else (0.0, 0.0)

        summary_rows.append(
            {
                "condition": cond,
                "n_trials": len(rows),
                "pout_1s_mean": round(pout_m, 6),
                "pout_1s_std": round(pout_s, 6),
                "tl_mean_s_mean": round(tl_m, 6),
                "tl_mean_s_std": round(tl_s, 6),
                "pdr_unique_mean": round(pdr_m, 6),
                "pdr_unique_std": round(pdr_s, 6),
                "rx_tag_share100_time_est_mean": (round(sh_m, 6) if share_list else ""),
                "rx_tag_share100_time_est_std": (round(sh_s, 6) if share_list else ""),
                "avg_power_mW_mean": round(pwr_m, 3),
                "avg_power_mW_std": round(pwr_s, 3),
                "adv_count_mean": round(adv_m, 3),
                "adv_count_std": round(adv_s, 3),
            }
        )

    sum_path = args.out_dir / "summary_by_condition.csv"
    with sum_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        w.writerows(summary_rows)

    lines: List[str] = []
    lines.append("# uccs_d3_scan70 metrics summary (v2)\n\n")
    lines.append(f"- source RX: `{args.rx_dir}`\n")
    lines.append(f"- source TXSD: `{args.txsd_dir}`\n")
    lines.append(f"- truth: `{args.truth_s4}` (n_steps={args.n_steps}, dt=100ms)\n")
    lines.append(f"- selected RX trials: {rx_trials[0].rx_id:03d}..{rx_trials[-1].rx_id:03d} (n={len(rx_trials)})\n")
    lines.append(f"- selected TXSD trials (by mtime): {Path(txsd_trials[0].path).name} .. {Path(txsd_trials[-1].path).name} (n={len(txsd_trials)})\n")
    lines.append(f"- generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} (local)\n")
    lines.append(f"- command: `python3 uccs_d3_scan70/analysis/summarize_d3_run_v2.py --rx-dir {args.rx_dir} --txsd-dir {args.txsd_dir} --out-dir {args.out_dir}`\n")

    lines.append("\n## Summary (mean ± std)\n")
    lines.append("| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|\n")

    def fmt_pm(m: object, s: object, decimals: int) -> str:
        if m == "" or s == "":
            return ""
        return f"{float(m):.{decimals}f}±{float(s):.{decimals}f}"

    for r in summary_rows:
        lines.append(
            f"| {r['condition']} | {fmt_pm(r['pout_1s_mean'], r['pout_1s_std'], 4)} | "
            f"{fmt_pm(r['tl_mean_s_mean'], r['tl_mean_s_std'], 3)} | "
            f"{fmt_pm(r['pdr_unique_mean'], r['pdr_unique_std'], 3)} | "
            f"{fmt_pm(r['avg_power_mW_mean'], r['avg_power_mW_std'], 1)} | "
            f"{fmt_pm(r['adv_count_mean'], r['adv_count_std'], 1)} | "
            f"{fmt_pm(r['rx_tag_share100_time_est_mean'], r['rx_tag_share100_time_est_std'], 3) if r.get('rx_tag_share100_time_est_mean','')!='' else ''} |"
            "\n"
        )

    lines.append("\n## Notes\n")
    lines.append("- RX window: latest 9 trials that form 3 conditions × 3 repeats (duration>=160s).\n")
    lines.append("- TXSD pairing: last 9 TXSD trials by file modification time; zipped in order with RX window.\n")
    lines.append("- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).\n")
    lines.append("- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique.\n")
    lines.append("- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).\n")

    md_path = args.out_dir / "summary.md"
    md_path.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

