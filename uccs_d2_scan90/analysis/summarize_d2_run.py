#!/usr/bin/env python3
"""
Summarize uccs_d2_scan90 run (RX + TXSD) and compute TL/Pout using step_idx-aligned payload.

Step D2 idea:
  - TX ManufacturerData is "<step_idx>_<tag>", where step_idx is the 100ms truth grid index.
  - RX logs `ms` (since session start) and `seq` (=step_idx).
  - Align RX time to truth time via a constant offset:
      offset_ms = median(step_idx*100 - first_rx_ms(step_idx))
  - Then compute TL/Pout on truth-time axis (100ms grid).

Inputs:
  - RX:  uccs_d2_scan90/data/RX/rx_trial_*.csv
  - TXSD: uccs_d2_scan90/data/TX/trial_*.csv (copied SD:/logs)
  - truth: Mode_C_2_シミュレート_causal/ccs/stress_causal_S1.csv and S4.csv

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

TAG_RE = re.compile(r"^(?P<mode>[FP])(?P<sess>[14])-(?P<label>\d+)-(?P<itv>\d+)$")
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
    mode: str  # "F" or "P"
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
    # inferred
    session: Optional[int] = None  # 1/4 if known
    kind: str = "unk"  # fixed100/fixed500/policy/unk


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
    mode = "F" if mode_c["F"] >= mode_c["P"] else "P"
    session = 1 if sess_c[1] >= sess_c[4] else 4

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
    return f"F{t.session}_{t.fixed_itv}"


def select_balanced_window(trials: List[RxTrial]) -> List[RxTrial]:
    """
    Pick the latest contiguous window that forms 6 conditions × 3 repeats = 18 trials.
    Conditions are defined by (mode, session, fixed_itv bucket).
    """
    candidates = [t for t in trials if t.duration_ms >= VALID_MIN_DURATION_MS]
    candidates.sort(key=lambda t: t.rx_id)
    if len(candidates) < 18:
        raise SystemExit(f"not enough valid RX trials (>= {VALID_MIN_DURATION_MS}ms): {len(candidates)}")

    best: Optional[List[RxTrial]] = None
    for start in range(0, len(candidates) - 18 + 1):
        window = candidates[start : start + 18]
        counts: Dict[str, int] = {}
        for t in window:
            k = _rx_bucket(t)
            counts[k] = counts.get(k, 0) + 1
        if len(counts) == 6 and all(v == 3 for v in counts.values()):
            best = window  # keep updating; latest wins
    if not best:
        raise SystemExit("could not find balanced 18-trial window (6 conditions × 3 repeats)")
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
    """
    aligned_events: list of (t_ms_aligned, label) where t_ms_aligned is on truth-time axis.
    """
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
            tl_list_s.append(max((len(truth_labels) * TRUTH_DT_MS - t_ms), 0) / 1000.0)
        else:
            tl_list_s.append((arrival - t_ms) / 1000.0)

    tl_mean = statistics.mean(tl_list_s) if tl_list_s else 0.0
    tl_p95 = statistics.quantiles(tl_list_s, n=100)[94] if len(tl_list_s) >= 2 else (tl_list_s[0] if tl_list_s else 0.0)
    pout = {tau: (sum(1 for tl in tl_list_s if tl > tau) / len(tl_list_s)) for tau in TAU_VALUES_S}
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

    # Session hint (may be mis-labeled; policy trials can be corrected later by share-based matching).
    if "_s1_" in name or tag.startswith("s1_"):
        t.session = 1
    elif "_s4_" in name or tag.startswith("s4_"):
        t.session = 4

    # Kind inference from adv_count (tick_count ~= number of payload updates).
    if 300 <= t.adv_count <= 450:
        t.kind = "fixed500"
        return
    if 1750 <= t.adv_count <= 1850:
        # Could be fixed100 or a policy that collapsed to 100ms.
        t.kind = "policy" if ("policy" in name or "policy" in tag) else "fixed100"
        return
    # In-between counts are treated as policy (two-valued 100/500 switching).
    t.kind = "policy"


def estimate_rx_tag_share100_time_est(events: List[RxEvent]) -> Optional[float]:
    # Same definition as per-trial table: time share estimated from RX tags (sanity only; RX has drops).
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


def maybe_fix_policy_session_by_share(
    txsd_trials: List[TxsdTrial],
    *,
    rx_share_s1: Optional[float],
    rx_share_s4: Optional[float],
    adv_count_fixed100: Optional[float],
    adv_count_fixed500: Optional[float],
    min_confident_delta: float = 0.15,
) -> None:
    # For policy trials, the TXSD filename/session tag can be wrong (preamble decode issues).
    # We estimate share100_time from adv_count and map to the closest RX-estimated share per session.
    if (
        rx_share_s1 is None
        or rx_share_s4 is None
        or adv_count_fixed100 is None
        or adv_count_fixed500 is None
        or adv_count_fixed100 <= adv_count_fixed500
    ):
        return

    denom = adv_count_fixed100 - adv_count_fixed500
    for t in txsd_trials:
        if t.kind != "policy":
            continue
        share_tx = (t.adv_count - adv_count_fixed500) / denom
        d1 = abs(share_tx - rx_share_s1)
        d4 = abs(share_tx - rx_share_s4)
        best_sess = 1 if d1 <= d4 else 4
        best_d = min(d1, d4)
        if best_d > min_confident_delta:
            continue
        t.session = best_sess


def rx_condition_key(t: RxTrial) -> str:
    if t.session == 1 and t.mode == "F" and t.fixed_itv == 100:
        return "S1_fixed100"
    if t.session == 1 and t.mode == "F" and t.fixed_itv == 500:
        return "S1_fixed500"
    if t.session == 1 and t.mode == "P":
        return "S1_policy"
    if t.session == 4 and t.mode == "F" and t.fixed_itv == 100:
        return "S4_fixed100"
    if t.session == 4 and t.mode == "F" and t.fixed_itv == 500:
        return "S4_fixed500"
    if t.session == 4 and t.mode == "P":
        return "S4_policy"
    return "UNK"


def txsd_condition_key(t: TxsdTrial) -> str:
    if t.session == 1 and t.kind == "fixed100":
        return "S1_fixed100"
    if t.session == 1 and t.kind == "fixed500":
        return "S1_fixed500"
    if t.session == 1 and t.kind == "policy":
        return "S1_policy"
    if t.session == 4 and t.kind == "fixed100":
        return "S4_fixed100"
    if t.session == 4 and t.kind == "fixed500":
        return "S4_fixed500"
    if t.session == 4 and t.kind == "policy":
        return "S4_policy"
    return "UNK"


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
    ap.add_argument("--truth-s1", type=Path, default=Path("Mode_C_2_シミュレート_causal/ccs/stress_causal_S1.csv"))
    ap.add_argument("--truth-s4", type=Path, default=Path("Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv"))
    ap.add_argument("--n-steps", type=int, default=1800)
    args = ap.parse_args()

    truth_s1 = read_truth_labels(args.truth_s1, args.n_steps)
    truth_s4 = read_truth_labels(args.truth_s4, args.n_steps)

    rx_trials_all: List[RxTrial] = []
    for p in sorted(args.rx_dir.glob("rx_trial_*.csv")):
        try:
            rx_trials_all.append(read_rx_trial(p))
        except ValueError:
            continue
    rx_trials = select_balanced_window(rx_trials_all)

    # RX-derived policy share targets (used to correct TXSD session labels for policy trials).
    s1_policy_shares: List[float] = []
    s4_policy_shares: List[float] = []
    for t in rx_trials:
        if t.mode != "P":
            continue
        sh = estimate_rx_tag_share100_time_est(t.events)
        if sh is None:
            continue
        k = rx_condition_key(t)
        if k == "S1_policy":
            s1_policy_shares.append(sh)
        elif k == "S4_policy":
            s4_policy_shares.append(sh)
    rx_share_s1 = statistics.mean(s1_policy_shares) if s1_policy_shares else None
    rx_share_s4 = statistics.mean(s4_policy_shares) if s4_policy_shares else None

    # TXSD trials
    txsd_trials: List[TxsdTrial] = []
    for p in sorted(args.txsd_dir.glob("trial_*.csv")):
        tt = parse_txsd_summary(p)
        if not tt:
            continue
        infer_txsd_kind(tt)
        if tt.ms_total >= VALID_MIN_DURATION_MS:
            txsd_trials.append(tt)

    # Use fixed trials to estimate the "100ms" and "500ms" adv_count reference points.
    fixed100_counts = [float(t.adv_count) for t in txsd_trials if t.kind == "fixed100"]
    fixed500_counts = [float(t.adv_count) for t in txsd_trials if t.kind == "fixed500"]
    adv_count_fixed100 = statistics.median(fixed100_counts) if fixed100_counts else None
    adv_count_fixed500 = statistics.median(fixed500_counts) if fixed500_counts else None
    maybe_fix_policy_session_by_share(
        txsd_trials,
        rx_share_s1=rx_share_s1,
        rx_share_s4=rx_share_s4,
        adv_count_fixed100=adv_count_fixed100,
        adv_count_fixed500=adv_count_fixed500,
    )

    # Group RX/TXSD by condition
    rx_by_cond: Dict[str, List[RxTrial]] = {}
    for t in rx_trials:
        rx_by_cond.setdefault(rx_condition_key(t), []).append(t)
    for v in rx_by_cond.values():
        v.sort(key=lambda t: t.rx_id)

    tx_by_cond: Dict[str, List[TxsdTrial]] = {}
    unknown_fixed100 = [t for t in txsd_trials if t.session is None and t.kind == "fixed100"]
    for t in txsd_trials:
        k = txsd_condition_key(t)
        if k != "UNK":
            tx_by_cond.setdefault(k, []).append(t)
    # If S1_fixed100 is short, fill from unknown fixed100 (likely preamble decode failed).
    if len(tx_by_cond.get("S1_fixed100", [])) < 3 and unknown_fixed100:
        need = 3 - len(tx_by_cond.get("S1_fixed100", []))
        unknown_fixed100.sort(key=lambda t: t.trial_idx)
        tx_by_cond.setdefault("S1_fixed100", []).extend(unknown_fixed100[-need:])
    for v in tx_by_cond.values():
        v.sort(key=lambda t: (t.trial_idx, t.cond_id, t.path.name))

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Per-trial table (paired within condition by order)
    per_rows: List[Dict[str, object]] = []
    for cond, rx_list in rx_by_cond.items():
        tx_list = tx_by_cond.get(cond, [])
        # Pair by order (repeat index) if TXSD exists, else RX-only.
        n_pair = len(rx_list) if not tx_list else min(len(rx_list), len(tx_list))
        for i in range(n_pair):
            rx = rx_list[i]
            tx = tx_list[i] if i < len(tx_list) else None
            truth = truth_s1 if rx.session == 1 else truth_s4

            offset_ms, offset_n = estimate_offset_ms(rx.events)

            aligned_events: List[Tuple[float, int]] = []
            step_set = set()
            # RX tag-based interval estimate (sanity only; RX has drops)
            # Count unique step_idx by interval indicated in tag (100/500).
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
                    "session": rx.session,
                    "mode": ("POLICY" if rx.mode == "P" else f"FIXED_{rx.fixed_itv}"),
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
    md_path = args.out_dir / "summary.md"
    lines: List[str] = []
    lines.append("# uccs_d2_scan90 metrics summary\n\n")
    lines.append(f"- source RX: `{args.rx_dir}`\n")
    lines.append(f"- source TXSD: `{args.txsd_dir}`\n")
    lines.append(f"- truth: `{args.truth_s1}`, `{args.truth_s4}` (n_steps={args.n_steps}, dt={TRUTH_DT_MS}ms)\n")

    rx_ids = [t.rx_id for t in rx_trials]
    lines.append(f"- selected RX trials: {min(rx_ids):03d}..{max(rx_ids):03d} (n={len(rx_ids)})\n")
    lines.append(f"- generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} (local)\n")
    lines.append(
        "- command: "
        f"`python3 uccs_d2_scan90/analysis/summarize_d2_run.py --rx-dir {args.rx_dir} --txsd-dir {args.txsd_dir} --out-dir {args.out_dir}`\n"
    )

    lines.append("\n## Summary (mean ± std, n=3 each)\n")
    lines.append("| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|\n")
    for r in summary_rows:
        cond = r["condition"]
        pout = f"{r['pout_1s_mean']:.4f}±{r['pout_1s_std']:.4f}"
        tl = f"{r['tl_mean_s_mean']:.3f}±{r['tl_mean_s_std']:.3f}"
        pdr = (
            f"{r['pdr_unique_mean']:.3f}±{r['pdr_unique_std']:.3f}"
            if r["pdr_unique_mean"] != ""
            else ""
        )
        pwr = (
            f"{r['avg_power_mW_mean']:.1f}±{r['avg_power_mW_std']:.1f}"
            if r["avg_power_mW_mean"] != ""
            else ""
        )
        adv = (
            f"{r['adv_count_mean']:.1f}±{r['adv_count_std']:.1f}"
            if r["adv_count_mean"] != ""
            else ""
        )
        sh = (
            f"{r['rx_tag_share100_time_est_mean']:.3f}±{r['rx_tag_share100_time_est_std']:.3f}"
            if r["rx_tag_share100_time_est_mean"] != ""
            else ""
        )
        lines.append(f"| {cond} | {pout} | {tl} | {pdr} | {pwr} | {adv} | {sh} |\n")

    lines.append("\n## Notes\n")
    lines.append("- RX trial selection: latest 18 trials that form 6 conditions × 3 repeats (duration>=160s).\n")
    lines.append("- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).\n")
    lines.append("- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique when available.\n")
    lines.append("- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).\n")

    md_path.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
