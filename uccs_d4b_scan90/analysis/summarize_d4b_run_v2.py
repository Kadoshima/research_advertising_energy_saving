#!/usr/bin/env python3
"""
Summarize uccs_d4b_scan90 run (RX + TXSD) and compute TL/Pout using step_idx-aligned payload.

Step D4B (CCS ablation):
  - S4 only
  - 4 conditions × 3 repeats = 12 trials
    - S4_fixed100 (F4-..-100)
    - S4_fixed500 (F4-..-500)
    - S4_policy (P4-..-itv)          # U+CCS
    - S4_ablation_ccs_off (U4-..-itv) # U-only (CCS-off)

RX ManufacturerData: "<step_idx>_<tag>"
  tag: "F4-<label>-<itv>" / "P4-<label>-<itv>" / "U4-<label>-<itv>"

Notes:
  - TXSD側は preamble（TICK）誤検出やSDコピーでmtimeが壊れるケースがあるため、
    cond_id/mtime に依存せず、adv_count（tick_count）を用いてクラスタリングして割り当てる。
  - TL/Poutは(100ms真値)遷移に対して、受信時刻をper-trial定数オフセットで整列して算出する（D2/D4と同じ）。
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

TAG_RE = re.compile(r"^(?P<mode>[FPU])(?P<sess>[14])-(?P<label>\d+)-(?P<itv>\d+)$")
RX_TRIAL_RE = re.compile(r"rx_trial_(?P<id>\d+)\.csv$")
TXSD_NAME_RE = re.compile(r"trial_(?P<idx>\d+)_c(?P<cond>\d+)_(?P<tag>.+)\.csv$")

# Drop stale/mixed low-power files (typically old logs) and wrong-signed logs.
TXSD_MIN_AVG_POWER_MW = 150.0


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
    session: int  # 4
    mode: str  # F/P/U
    fixed_itv: Optional[int]  # 100/500 if fixed
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


def parse_mfd(s: str) -> Optional[Tuple[int, str]]:
    s = (s or "").strip()
    if not s:
        return None
    us = s.find("_")
    if us <= 0:
        return None
    try:
        step_idx = int(s[:us])
    except Exception:
        return None
    tag = s[us + 1 :].strip()
    if not tag:
        return None
    return step_idx, tag


def read_rx_trial(path: Path) -> RxTrial:
    m = RX_TRIAL_RE.search(path.name)
    if not m:
        raise ValueError(f"not rx_trial: {path}")
    rx_id = int(m.group("id"))

    events: List[RxEvent] = []
    last_ms: float = 0.0
    mode_c: Dict[str, int] = {"F": 0, "P": 0, "U": 0}
    fixed_itv_c: Dict[int, int] = {}

    with path.open(newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            try:
                rx_ms = float(row.get("ms") or 0.0)
            except Exception:
                continue
            last_ms = max(last_ms, rx_ms)

            mfd = (row.get("mfd") or "").strip()
            pm = parse_mfd(mfd)
            if not pm:
                continue
            step_idx, tag = pm

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
            if mode == "F":
                fixed_itv_c[itv_ms] = fixed_itv_c.get(itv_ms, 0) + 1

            events.append(RxEvent(rx_ms=rx_ms, step_idx=step_idx, truth_label=truth_label, itv_ms=itv_ms, tag=tag))

    if not events:
        raise ValueError(f"empty/invalid RX: {path}")

    mode = max(mode_c.items(), key=lambda kv: kv[1])[0]
    fixed_itv = None
    if mode == "F":
        fixed_itv = max(fixed_itv_c.items(), key=lambda kv: kv[1])[0] if fixed_itv_c else None
        if fixed_itv not in (100, 500):
            raise ValueError(f"unexpected fixed interval {fixed_itv} in {path}")

    return RxTrial(rx_id=rx_id, path=path, duration_ms=last_ms, session=4, mode=mode, fixed_itv=fixed_itv, events=events)


def rx_bucket(t: RxTrial) -> str:
    if t.mode == "P":
        return "P4"
    if t.mode == "U":
        return "U4"
    return f"F4_{t.fixed_itv}"


def select_balanced_window(trials: List[RxTrial]) -> List[RxTrial]:
    candidates = [t for t in trials if t.duration_ms >= VALID_MIN_DURATION_MS]
    candidates.sort(key=lambda t: t.rx_id)
    if len(candidates) < 12:
        raise SystemExit(f"not enough valid RX trials (>= {VALID_MIN_DURATION_MS}ms): {len(candidates)}")

    want = {"F4_100", "F4_500", "P4", "U4"}
    best: Optional[List[RxTrial]] = None
    for start in range(0, len(candidates) - 12 + 1):
        window = candidates[start : start + 12]
        counts: Dict[str, int] = {}
        for t in window:
            counts[rx_bucket(t)] = counts.get(rx_bucket(t), 0) + 1
        if set(counts.keys()) == want and all(counts.get(k, 0) == 3 for k in want):
            best = window
    if not best:
        raise SystemExit("could not find balanced 12-trial RX window (F4_100/F4_500/P4/U4 × 3 repeats)")
    return best


def estimate_offset_ms(events: List[RxEvent]) -> Tuple[float, int]:
    first_ms: Dict[int, float] = {}
    for e in events:
        if e.step_idx not in first_ms:
            first_ms[e.step_idx] = e.rx_ms
    if not first_ms:
        return 0.0, 0
    offsets = [(idx * TRUTH_DT_MS) - ms for idx, ms in first_ms.items()]
    offsets.sort()
    return float(statistics.median(offsets)), len(offsets)


def compute_tl_and_pout(truth_labels: List[int], aligned_events: List[Tuple[float, int]]) -> Tuple[float, float, Dict[float, float]]:
    # truth transitions by 100ms grid
    transitions: List[Tuple[float, int]] = []
    prev = truth_labels[0]
    for i in range(1, len(truth_labels)):
        cur = truth_labels[i]
        if cur != prev:
            transitions.append((i * TRUTH_DT_MS, cur))
        prev = cur

    # index events by truth label
    events_by_label: Dict[int, List[float]] = {}
    for t_ms, lbl in aligned_events:
        events_by_label.setdefault(lbl, []).append(t_ms)
    for lbl in events_by_label:
        events_by_label[lbl].sort()

    tl_list_s: List[float] = []
    for t_ms, true_label in transitions:
        arr = events_by_label.get(true_label) or []
        arrival = None
        for ms in arr:
            if ms >= t_ms:
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
        pout[tau] = miss / len(tl_list_s) if tl_list_s else 0.0
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


def mean_std(xs: List[float]) -> Tuple[float, float]:
    if not xs:
        return 0.0, 0.0
    if len(xs) == 1:
        return xs[0], 0.0
    return statistics.mean(xs), statistics.stdev(xs)


def condition_name(rx: RxTrial) -> str:
    if rx.mode == "P":
        return "S4_policy"
    if rx.mode == "U":
        return "S4_ablation_ccs_off"
    return "S4_fixed100" if rx.fixed_itv == 100 else "S4_fixed500"


def pick_n_typical_by_power(group: List[TxsdTrial], n: int) -> List[TxsdTrial]:
    if len(group) < n:
        raise SystemExit(f"not enough TXSD trials in group: need {n}, got {len(group)}")
    powers = [t.avg_power_mw for t in group]
    med = statistics.median(powers)
    group_sorted = sorted(group, key=lambda t: abs(t.avg_power_mw - med))
    return group_sorted[:n]


def compute_share100_power_mix(p_dyn: float, p_100: float, p_500: float) -> Optional[float]:
    denom = (p_100 - p_500)
    if denom == 0:
        return None
    s = (p_dyn - p_500) / denom
    if s < 0:
        s = 0.0
    if s > 1:
        s = 1.0
    return float(s)


def classify_txsd_by_adv_count(
    txsd_trials: List[TxsdTrial],
    rx_share_policy: Optional[float],
    rx_share_uonly: Optional[float],
) -> Dict[str, List[TxsdTrial]]:
    """
    Classify TXSD trials into 4 conditions using adv_count clustering.
      - max adv_count -> fixed100
      - min adv_count -> fixed500
      - remaining 2 adv_count values -> policy vs u-only (matched by RX tag share100 if available)
    """
    by_adv: Dict[int, List[TxsdTrial]] = {}
    for t in txsd_trials:
        by_adv.setdefault(t.adv_count, []).append(t)
    adv_values = sorted(by_adv.keys())
    if len(adv_values) < 4:
        raise SystemExit(f"TXSD adv_count has <4 unique values: {adv_values}")

    adv_min = adv_values[0]
    adv_max = adv_values[-1]
    dyn = [v for v in adv_values if v not in (adv_min, adv_max)]
    if len(dyn) != 2:
        dyn = sorted(dyn, key=lambda v: len(by_adv[v]), reverse=True)[:2]
        dyn = sorted(dyn)
    if len(dyn) != 2:
        raise SystemExit(f"could not identify 2 dynamic adv_count values: {adv_values}")

    adv_dyn1, adv_dyn2 = dyn[0], dyn[1]

    def adv_to_share(a: int) -> float:
        denom = (adv_max - adv_min)
        if denom <= 0:
            return 0.0
        s = (a - adv_min) / denom
        if s < 0:
            s = 0.0
        if s > 1:
            s = 1.0
        return float(s)

    s1 = adv_to_share(adv_dyn1)
    s2 = adv_to_share(adv_dyn2)

    if rx_share_policy is not None and rx_share_uonly is not None:
        d11 = abs(s1 - rx_share_policy) + abs(s2 - rx_share_uonly)
        d12 = abs(s1 - rx_share_uonly) + abs(s2 - rx_share_policy)
        if d12 < d11:
            adv_dyn1, adv_dyn2 = adv_dyn2, adv_dyn1
            s1, s2 = s2, s1

    groups = {
        "S4_fixed500": by_adv[adv_min],
        "S4_fixed100": by_adv[adv_max],
        "S4_policy": by_adv[adv_dyn1],
        "S4_ablation_ccs_off": by_adv[adv_dyn2],
    }
    for k in groups:
        groups[k] = sorted(groups[k], key=lambda t: t.path.name)
    return groups


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
        if tt.ms_total >= VALID_MIN_DURATION_MS and tt.avg_power_mw >= TXSD_MIN_AVG_POWER_MW and tt.e_total_mj > 0:
            txsd_all.append(tt)
    if not txsd_all:
        raise SystemExit("no valid TXSD trials found after filtering")

    # RX share100 estimates for matching policy vs u-only TXSD clusters (optional).
    pol_shares = [estimate_rx_tag_share100_time_est(t.events) for t in rx_trials if t.mode == "P"]
    u_shares = [estimate_rx_tag_share100_time_est(t.events) for t in rx_trials if t.mode == "U"]
    pol_shares = [x for x in pol_shares if x is not None]
    u_shares = [x for x in u_shares if x is not None]
    rx_share_pol = statistics.mean(pol_shares) if pol_shares else None
    rx_share_u = statistics.mean(u_shares) if u_shares else None

    groups = classify_txsd_by_adv_count(txsd_all, rx_share_pol, rx_share_u)
    picked: Dict[str, List[TxsdTrial]] = {k: pick_n_typical_by_power(v, 3) for k, v in groups.items()}
    for k in picked:
        picked[k].sort(key=lambda t: t.path.name)

    pairs: List[Tuple[RxTrial, TxsdTrial]] = []
    for rx in rx_trials:
        cond = condition_name(rx)
        if cond not in picked or not picked[cond]:
            raise SystemExit(f"TXSD group missing for {cond}")
        pairs.append((rx, picked[cond].pop(0)))

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
                "mode": ("POLICY" if rx.mode == "P" else ("U_ONLY" if rx.mode == "U" else f"FIXED_{rx.fixed_itv}")),
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

    by_cond_rows: Dict[str, List[Dict[str, object]]] = {}
    for r in per_rows:
        by_cond_rows.setdefault(str(r["condition"]), []).append(r)

    summary_rows: List[Dict[str, object]] = []
    for cond, rows in sorted(by_cond_rows.items()):
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

    # Add share100_power_mix_mean for dynamic conditions (mean powers only).
    p100 = next((float(r["avg_power_mW_mean"]) for r in summary_rows if r["condition"] == "S4_fixed100"), None)
    p500 = next((float(r["avg_power_mW_mean"]) for r in summary_rows if r["condition"] == "S4_fixed500"), None)
    for r in summary_rows:
        r["share100_power_mix_mean"] = ""
        if p100 is None or p500 is None:
            continue
        if r["condition"] in ("S4_policy", "S4_ablation_ccs_off"):
            s = compute_share100_power_mix(float(r["avg_power_mW_mean"]), p100, p500)
            if s is not None:
                r["share100_power_mix_mean"] = round(s, 6)

    sum_path = args.out_dir / "summary_by_condition.csv"
    with sum_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        w.writerows(summary_rows)

    lines: List[str] = []
    lines.append("# uccs_d4b_scan90 metrics summary (v2)\n\n")
    lines.append(f"- source RX: `{args.rx_dir}`\n")
    lines.append(f"- source TXSD: `{args.txsd_dir}`\n")
    lines.append(f"- truth: `{args.truth_s4}` (n_steps={args.n_steps}, dt=100ms)\n")
    lines.append(f"- selected RX trials: {rx_trials[0].rx_id:03d}..{rx_trials[-1].rx_id:03d} (n={len(rx_trials)})\n")
    uniq_adv = sorted({tx.adv_count for _, tx in pairs})
    lines.append(f"- selected TXSD trials: grouped by adv_count={uniq_adv} (3 trials each)\n")
    lines.append(f"- generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} (local)\n")
    lines.append(f"- command: `python3 uccs_d4b_scan90/analysis/summarize_d4b_run_v2.py --rx-dir {args.rx_dir} --txsd-dir {args.txsd_dir} --out-dir {args.out_dir}`\n")

    lines.append("\n## Summary (mean ± std)\n")
    lines.append("| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) | share100_power_mix |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|\n")

    def fmt_pm(m: object, s: object, decimals: int) -> str:
        if m == "" or s == "":
            return ""
        return f"{float(m):.{decimals}f}±{float(s):.{decimals}f}"

    for r in summary_rows:
        share_mix = r.get("share100_power_mix_mean", "")
        lines.append(
            f"| {r['condition']} | {fmt_pm(r['pout_1s_mean'], r['pout_1s_std'], 4)} | "
            f"{fmt_pm(r['tl_mean_s_mean'], r['tl_mean_s_std'], 3)} | "
            f"{fmt_pm(r['pdr_unique_mean'], r['pdr_unique_std'], 3)} | "
            f"{fmt_pm(r['avg_power_mW_mean'], r['avg_power_mW_std'], 1)} | "
            f"{fmt_pm(r['adv_count_mean'], r['adv_count_std'], 1)} | "
            f"{fmt_pm(r['rx_tag_share100_time_est_mean'], r['rx_tag_share100_time_est_std'], 3) if r.get('rx_tag_share100_time_est_mean','')!='' else ''} | "
            f"{(f'{float(share_mix):.3f}' if share_mix != '' else '')} |"
            "\n"
        )

    lines.append("\n## Notes\n")
    lines.append("- RX window: latest 12 trials that form 4 conditions × 3 repeats (duration>=160s).\n")
    lines.append("- TXSD pairing: cond_idがズレる/mtimeが壊れる可能性があるため、adv_count（tick_count）でクラスタリングして割り当て。\n")
    lines.append(f"  - filter: avg_power_mW >= {TXSD_MIN_AVG_POWER_MW:.1f} かつ E_total_mJ>0（古いログ混在/逆符号を除外）\n")
    lines.append("- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).\n")
    lines.append("- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique.\n")
    lines.append("- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).\n")

    md_path = args.out_dir / "summary.md"
    md_path.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
