#!/usr/bin/env python3
"""
Summarize uccs_d4_scan90 run (RX + TXSD) and compute TL/Pout using step_idx-aligned payload.

Step D4 idea:
  - TX ManufacturerData is "<step_idx>_<tag>", where step_idx is the 100ms truth grid index.
  - Tag includes mode:
      F4-<label>-<itv>  (fixed)
      P4-<label>-<itv>  (policy U+CCS)
      A4-<label>-<itv>  (ablation: U-shuffle)
  - Align RX time to truth time via a constant offset:
      offset_ms = median(step_idx*100 - first_rx_ms(step_idx))
  - Then compute TL/Pout on truth-time axis (100ms grid).

Inputs:
  - RX:  uccs_d4_scan90/data/<run>/RX/rx_trial_*.csv
  - TXSD: uccs_d4_scan90/data/<run>/TX/trial_*.csv (copied SD:/logs)
  - truth: Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv

Outputs (out_dir):
  - per_trial.csv
  - summary_by_condition.csv
  - summary.md
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

TAG_RE = re.compile(r"^(?P<mode>[FPA])(?P<sess>[14])-(?P<label>\d+)-(?P<itv>\d+)$")
RX_TRIAL_RE = re.compile(r"rx_trial_(?P<id>\d+)\.csv$")
TXSD_NAME_RE = re.compile(r"trial_(?P<idx>\d+)_c(?P<cond>\d+)_(?P<tag>.+)\.csv$")


@dataclass(frozen=True)
class RxEvent:
    rx_ms: float
    step_idx: int
    tag: str


@dataclass
class RxTrial:
    rx_id: int
    path: Path
    duration_ms: float
    session: int  # 1 or 4
    mode: str  # "F" / "P" / "A"
    fixed_itv: Optional[int]  # 100/500 if fixed, else None
    events: List[RxEvent]


@dataclass
class TxsdTrial:
    path: Path
    trial_idx: int
    cond_id: int
    tag: str
    ms_total: float
    adv_count: int
    e_total_mj: float
    avg_power_mw: float
    kind: str = "unk"  # fixed100/fixed500/policy/ablation/unk


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

    mode_c: Dict[str, int] = {"F": 0, "P": 0, "A": 0}
    sess_c: Dict[int, int] = {1: 0, 4: 0}
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
            if tag:
                tm = TAG_RE.match(tag)
                if tm:
                    mode_c[tm.group("mode")] += 1
                    sess_c[int(tm.group("sess"))] += 1
                    itv = int(tm.group("itv"))
                    itv_c[itv] = itv_c.get(itv, 0) + 1

            events.append(RxEvent(rx_ms=rx_ms, step_idx=step_idx, tag=tag))

    if not events:
        raise ValueError(f"empty RX: {path}")

    # robust majority
    mode = max(mode_c.items(), key=lambda kv: kv[1])[0]
    session = 4 if sess_c[4] >= sess_c[1] else 1

    fixed_itv: Optional[int] = None
    if mode == "F":
        if not itv_c:
            raise ValueError(f"cannot infer fixed interval from tags: {path}")
        fixed_itv = max(itv_c.items(), key=lambda kv: kv[1])[0]

    return RxTrial(
        rx_id=rx_id,
        path=path,
        duration_ms=last_ms,
        session=session,
        mode=mode,
        fixed_itv=fixed_itv,
        events=events,
    )


def _rx_bucket(t: RxTrial) -> str:
    if t.mode == "P":
        return f"P{t.session}"
    if t.mode == "A":
        return f"A{t.session}"
    return f"F{t.session}_{t.fixed_itv}"


def select_balanced_window(trials: List[RxTrial]) -> List[RxTrial]:
    """
    Pick the latest contiguous window that forms 4 conditions × 3 repeats = 12 trials (S4 only).
    Buckets required: F4_100, F4_500, P4, A4.
    """
    candidates = [t for t in trials if t.duration_ms >= VALID_MIN_DURATION_MS]
    candidates.sort(key=lambda t: t.rx_id)
    if len(candidates) < 12:
        raise SystemExit(f"not enough valid RX trials (>= {VALID_MIN_DURATION_MS}ms): {len(candidates)}")

    want = {"F4_100", "F4_500", "P4", "A4"}
    best: Optional[List[RxTrial]] = None
    for start in range(0, len(candidates) - 12 + 1):
        window = candidates[start : start + 12]
        counts: Dict[str, int] = {}
        for t in window:
            counts[_rx_bucket(t)] = counts.get(_rx_bucket(t), 0) + 1
        if set(counts.keys()) == want and all(v == 3 for v in counts.values()):
            best = window  # latest wins
    if not best:
        raise SystemExit("could not find balanced 12-trial window (F4_100/F4_500/P4/A4 × 3 repeats)")
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


def compute_tl_and_pout(
    truth_labels: List[int], aligned_events: List[Tuple[float, int]]
) -> Tuple[float, float, Dict[float, float]]:
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
        if not tl_list_s:
            pout[tau] = 0.0
        else:
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
        trial_idx=trial_idx,
        cond_id=cond_id,
        tag=tag,
        ms_total=ms_total,
        adv_count=adv_count,
        e_total_mj=e_total_mj,
        avg_power_mw=avg_power,
    )


def infer_txsd_kind(t: TxsdTrial) -> None:
    name = t.path.name.lower()
    tag = t.tag.lower()

    # Prefer explicit cond_id/tag when available.
    if t.cond_id == 1 or "fixed100" in name or "fixed100" in tag:
        t.kind = "fixed100"
        return
    if t.cond_id == 2 or "fixed500" in name or "fixed500" in tag:
        t.kind = "fixed500"
        return
    if t.cond_id == 3 or ("policy" in name or "policy" in tag):
        t.kind = "policy"
        return
    if t.cond_id == 4 or ("ablation" in name or "ushuf" in name or "ushuf" in tag):
        t.kind = "ablation"
        return

    # Fallback by adv_count
    if 300 <= t.adv_count <= 450:
        t.kind = "fixed500"
        return
    if 1750 <= t.adv_count <= 1850:
        t.kind = "fixed100"
        return
    t.kind = "unk"


def estimate_rx_tag_share100_time_est(events: List[RxEvent]) -> Optional[float]:
    rx_itv_by_step: Dict[int, int] = {}
    for e in events:
        step = e.step_idx
        if step < 0:
            continue
        tm = TAG_RE.match(e.tag)
        if tm and step not in rx_itv_by_step:
            try:
                rx_itv_by_step[step] = int(tm.group("itv"))
            except Exception:
                pass
    n100 = sum(1 for v in rx_itv_by_step.values() if v == 100)
    n500 = sum(1 for v in rx_itv_by_step.values() if v == 500)
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx-dir", type=Path, required=True)
    ap.add_argument("--txsd-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--truth-s4", type=Path, default=Path("Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv"))
    ap.add_argument("--n-steps", type=int, default=1800)
    args = ap.parse_args()

    truth = read_truth_labels(args.truth_s4, args.n_steps)

    rx_trials_all: List[RxTrial] = []
    for p in sorted(args.rx_dir.glob("rx_trial_*.csv")):
        try:
            rx_trials_all.append(read_rx_trial(p))
        except ValueError:
            continue
    rx_trials = select_balanced_window(rx_trials_all)

    # TXSD trials
    txsd_trials: List[TxsdTrial] = []
    for p in sorted(args.txsd_dir.glob("trial_*.csv")):
        tt = parse_txsd_summary(p)
        if not tt:
            continue
        infer_txsd_kind(tt)
        if tt.ms_total >= VALID_MIN_DURATION_MS:
            txsd_trials.append(tt)

    # Policy-like unknown recovery (optional): use RX-derived share targets to label missing policy/ablation.
    fixed100_counts = [t.adv_count for t in txsd_trials if t.kind == "fixed100"]
    fixed500_counts = [t.adv_count for t in txsd_trials if t.kind == "fixed500"]
    adv_fixed100 = statistics.median(fixed100_counts) if fixed100_counts else None
    adv_fixed500 = statistics.median(fixed500_counts) if fixed500_counts else None
    rx_share_policy = statistics.mean(
        [s for s in (estimate_rx_tag_share100_time_est(t.events) for t in rx_trials) if s is not None and t.mode == "P"]
    ) if any(t.mode == "P" for t in rx_trials) else None
    rx_share_ablation = statistics.mean(
        [s for s in (estimate_rx_tag_share100_time_est(t.events) for t in rx_trials) if s is not None and t.mode == "A"]
    ) if any(t.mode == "A" for t in rx_trials) else None
    if adv_fixed100 is not None and adv_fixed500 is not None and adv_fixed100 > adv_fixed500 and rx_share_policy is not None and rx_share_ablation is not None:
        denom = adv_fixed100 - adv_fixed500
        for t in txsd_trials:
            if t.kind != "unk":
                continue
            share_tx = (t.adv_count - adv_fixed500) / denom
            d_pol = abs(share_tx - rx_share_policy)
            d_abl = abs(share_tx - rx_share_ablation)
            best = "policy" if d_pol <= d_abl else "ablation"
            if min(d_pol, d_abl) <= 0.15:
                t.kind = best

    # Group RX/TXSD by condition
    def rx_cond_key(t: RxTrial) -> str:
        if t.session != 4:
            return "UNK"
        if t.mode == "F" and t.fixed_itv == 100:
            return "S4_fixed100"
        if t.mode == "F" and t.fixed_itv == 500:
            return "S4_fixed500"
        if t.mode == "P":
            return "S4_policy"
        if t.mode == "A":
            return "S4_ablation_u_shuf"
        return "UNK"

    def tx_cond_key(t: TxsdTrial) -> str:
        if t.kind == "fixed100":
            return "S4_fixed100"
        if t.kind == "fixed500":
            return "S4_fixed500"
        if t.kind == "policy":
            return "S4_policy"
        if t.kind == "ablation":
            return "S4_ablation_u_shuf"
        return "UNK"

    rx_by_cond: Dict[str, List[RxTrial]] = {}
    for t in rx_trials:
        rx_by_cond.setdefault(rx_cond_key(t), []).append(t)
    for v in rx_by_cond.values():
        v.sort(key=lambda t: t.rx_id)

    tx_by_cond: Dict[str, List[TxsdTrial]] = {}
    for t in txsd_trials:
        k = tx_cond_key(t)
        if k != "UNK":
            tx_by_cond.setdefault(k, []).append(t)
    for v in tx_by_cond.values():
        v.sort(key=lambda t: (t.trial_idx, t.cond_id, t.path.name))

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Per-trial table (paired within condition by order)
    per_rows: List[Dict[str, object]] = []
    for cond, rx_list in rx_by_cond.items():
        tx_list = tx_by_cond.get(cond, [])
        n_pair = len(rx_list) if not tx_list else min(len(rx_list), len(tx_list))
        for i in range(n_pair):
            rx = rx_list[i]
            tx = tx_list[i] if i < len(tx_list) else None

            offset_ms, offset_n = estimate_offset_ms(rx.events)
            aligned_events: List[Tuple[float, int]] = []
            step_set = set()
            rx_itv_by_step: Dict[int, int] = {}
            for e in rx.events:
                step = e.step_idx
                if 0 <= step < args.n_steps:
                    aligned_events.append((e.rx_ms + offset_ms, truth[step]))
                    step_set.add(step)
                    tm = TAG_RE.match(e.tag)
                    if tm and step not in rx_itv_by_step:
                        try:
                            rx_itv_by_step[step] = int(tm.group("itv"))
                        except Exception:
                            pass

            rx_tag_n100 = sum(1 for v in rx_itv_by_step.values() if v == 100)
            rx_tag_n500 = sum(1 for v in rx_itv_by_step.values() if v == 500)
            rx_tag_share100_time_est = ""
            denom_ms = rx_tag_n100 * 100 + rx_tag_n500 * 500
            if denom_ms > 0:
                rx_tag_share100_time_est = (rx_tag_n100 * 100) / denom_ms

            tl_mean, tl_p95, pout = compute_tl_and_pout(truth, aligned_events)

            rx_count = len(rx.events)
            rx_unique = len(step_set)
            adv_count = tx.adv_count if tx else ""
            pdr_unique = (
                (min(rx_unique, adv_count) / adv_count) if isinstance(adv_count, int) and adv_count > 0 else ""
            )

            per_rows.append(
                {
                    "rx_trial_id": rx.rx_id,
                    "condition": cond,
                    "repeat_idx": i + 1,
                    "mode": ("POLICY" if rx.mode == "P" else ("ABL_U_SHUF" if rx.mode == "A" else f"FIXED_{rx.fixed_itv}")),
                    "rx_count": rx_count,
                    "rx_unique": rx_unique,
                    "adv_count": adv_count,
                    "pdr_unique": round(pdr_unique, 6) if pdr_unique != "" else "",
                    "rx_tag_n100": rx_tag_n100,
                    "rx_tag_n500": rx_tag_n500,
                    "rx_tag_share100_time_est": (
                        round(rx_tag_share100_time_est, 6) if rx_tag_share100_time_est != "" else ""
                    ),
                    "tl_mean_s": round(tl_mean, 6),
                    "tl_p95_s": round(tl_p95, 6),
                    "pout_1s": round(pout[1.0], 6),
                    "pout_2s": round(pout[2.0], 6),
                    "pout_3s": round(pout[3.0], 6),
                    "tl_time_offset_ms": round(offset_ms, 3),
                    "tl_time_offset_n": offset_n,
                    "txsd_ms_total": tx.ms_total if tx else "",
                    "E_total_mJ": tx.e_total_mj if tx else "",
                    "avg_power_mW": tx.avg_power_mw if tx else "",
                    "txsd_path": str(tx.path) if tx else "",
                    "rx_path": str(rx.path),
                }
            )

    per_rows.sort(key=lambda r: int(r["rx_trial_id"]))
    per_path = args.out_dir / "per_trial.csv"
    with per_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_rows[0].keys()))
        w.writeheader()
        w.writerows(per_rows)

    # Summary by condition
    by_cond: Dict[str, List[Dict[str, object]]] = {}
    for r in per_rows:
        by_cond.setdefault(str(r["condition"]), []).append(r)

    summary_rows: List[Dict[str, object]] = []
    for cond, rows in sorted(by_cond.items()):
        pout_1s_list = [float(r["pout_1s"]) for r in rows if r["pout_1s"] != ""]
        tl_list = [float(r["tl_mean_s"]) for r in rows if r["tl_mean_s"] != ""]
        pdr_list = [float(r["pdr_unique"]) for r in rows if r["pdr_unique"] != ""]
        pwr_list = [float(r["avg_power_mW"]) for r in rows if r["avg_power_mW"] != ""]
        adv_list = [float(r["adv_count"]) for r in rows if isinstance(r["adv_count"], int)]
        share100_list = [
            float(r["rx_tag_share100_time_est"]) for r in rows if r["rx_tag_share100_time_est"] != ""
        ]

        pout_m, pout_s = mean_std(pout_1s_list)
        tl_m, tl_s = mean_std(tl_list)
        pdr_m, pdr_s = mean_std(pdr_list)
        pwr_m, pwr_s = mean_std(pwr_list)
        adv_m, adv_s = mean_std(adv_list)
        sh_m, sh_s = mean_std(share100_list)

        summary_rows.append(
            {
                "condition": cond,
                "n_trials": len(rows),
                "pout_1s_mean": round(pout_m, 6),
                "pout_1s_std": round(pout_s, 6),
                "tl_mean_s_mean": round(tl_m, 6),
                "tl_mean_s_std": round(tl_s, 6),
                "pdr_unique_mean": round(pdr_m, 6) if pdr_list else "",
                "pdr_unique_std": round(pdr_s, 6) if pdr_list else "",
                "rx_tag_share100_time_est_mean": round(sh_m, 6) if share100_list else "",
                "rx_tag_share100_time_est_std": round(sh_s, 6) if share100_list else "",
                "avg_power_mW_mean": round(pwr_m, 3) if pwr_list else "",
                "avg_power_mW_std": round(pwr_s, 3) if pwr_list else "",
                "adv_count_mean": round(adv_m, 3) if adv_list else "",
                "adv_count_std": round(adv_s, 3) if adv_list else "",
            }
        )

    sum_path = args.out_dir / "summary_by_condition.csv"
    with sum_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        w.writerows(summary_rows)

    # Markdown summary
    lines: List[str] = []
    lines.append("# uccs_d4_scan90 metrics summary\n\n")
    lines.append(f"- source RX: `{args.rx_dir}`\n")
    lines.append(f"- source TXSD: `{args.txsd_dir}`\n")
    lines.append(f"- truth: `{args.truth_s4}` (n_steps={args.n_steps}, dt=100ms)\n")
    lines.append(
        f"- selected RX trials: {rx_trials[0].rx_id:03d}..{rx_trials[-1].rx_id:03d} (n={len(rx_trials)})\n"
    )
    lines.append(f"- generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} (local)\n")
    lines.append(
        f"- command: `python3 uccs_d4_scan90/analysis/summarize_d4_run.py --rx-dir {args.rx_dir} --txsd-dir {args.txsd_dir} --out-dir {args.out_dir}`\n"
    )
    lines.append("\n## Summary (mean ± std)\n")
    lines.append("| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|\n")
    for r in summary_rows:
        def fmt_pm(mean_key: str, std_key: str, decimals: int = 4) -> str:
            m = r.get(mean_key, "")
            s = r.get(std_key, "")
            if m == "" or s == "":
                return ""
            return f"{float(m):.{decimals}f}±{float(s):.{decimals}f}"

        pout = fmt_pm("pout_1s_mean", "pout_1s_std", 4)
        tl = fmt_pm("tl_mean_s_mean", "tl_mean_s_std", 3)
        pdr = fmt_pm("pdr_unique_mean", "pdr_unique_std", 3) if r.get("pdr_unique_mean", "") != "" else ""
        pwr = fmt_pm("avg_power_mW_mean", "avg_power_mW_std", 1) if r.get("avg_power_mW_mean", "") != "" else ""
        adv = fmt_pm("adv_count_mean", "adv_count_std", 1) if r.get("adv_count_mean", "") != "" else ""
        sh = fmt_pm("rx_tag_share100_time_est_mean", "rx_tag_share100_time_est_std", 3) if r.get("rx_tag_share100_time_est_mean", "") != "" else ""
        lines.append(f"| {r['condition']} | {pout} | {tl} | {pdr} | {pwr} | {adv} | {sh} |\n")

    lines.append("\n## Notes\n")
    lines.append("- RX trial selection: latest 12 trials that form 4 conditions × 3 repeats (duration>=160s).\n")
    lines.append("- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).\n")
    lines.append("- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique when available.\n")
    lines.append("- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).\n")

    md_path = args.out_dir / "summary.md"
    md_path.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
