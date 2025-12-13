#!/usr/bin/env python3
"""
Offline policy evaluation for synthetic mHealth sessions.

Inputs:
- Synthetic HAR logs with U/CCS (data/mhealth_synthetic_sessions_v1/sessions/*_har.csv)
- Fixed-interval real metrics (scan90): results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv

Process:
- Apply a rule-based policy (U/CCS + hysteresis) to each window (mask_eval_window==1) to pick interval {100,500,1000,2000}.
- Count action shares.
- Combine shares with fixed-interval metrics (averaged over S1/S4) to estimate expected QoS/energy.

Outputs:
- JSON summary to stdout (and optionally --out-json).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


def load_har_sessions(har_dir: Path, with_truth: bool = False):
    files = sorted(har_dir.glob("*_har.csv"))
    sessions = []
    for fp in files:
        df = pd.read_csv(fp)
        df["session_id"] = fp.stem.replace("_har", "")
        if with_truth:
            truth_fp = fp.with_name(fp.name.replace("_har.csv", "_truth100ms.csv"))
            truth_df = pd.read_csv(truth_fp)
            sessions.append((df, truth_df))
        else:
            sessions.append(df)
    return sessions


def load_fixed_metrics(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df


def apply_power_table(fixed: pd.DataFrame, power_table: Path) -> pd.DataFrame:
    """
    Override avg_power_mW_mean in the fixed-metrics table using an external table.

    power_table CSV schema:
      interval_ms,avg_power_mW
    """
    pt = pd.read_csv(power_table)
    if "interval_ms" not in pt.columns or "avg_power_mW" not in pt.columns:
        raise SystemExit(f"power_table must have columns interval_ms,avg_power_mW: {power_table}")
    m = pt.set_index("interval_ms")["avg_power_mW"].to_dict()
    out = fixed.copy()
    if "avg_power_mW_mean" in out.columns:
        out["avg_power_mW_mean_orig"] = out["avg_power_mW_mean"]
        override = out["interval_ms"].map(m)
        out["avg_power_mW_mean"] = override.fillna(out["avg_power_mW_mean_orig"])
    return out


def apply_policy(
    df: pd.DataFrame,
    u_mid: float,
    u_high: float,
    c_mid: float,
    c_high: float,
    hysteresis: float,
    initial_interval: int = 500,
) -> Dict[int, int]:
    counts: Dict[int, int] = {100: 0, 500: 0, 1000: 0, 2000: 0}
    prev = initial_interval
    for _, row in df.iterrows():
        if row["mask_eval_window"] != 1:
            continue
        u = row["U_ema"]
        c = row["CCS_ema"]
        # hysteresis bands
        u_hi_up = u_high
        u_hi_down = u_high - hysteresis
        u_mid_up = u_mid
        u_mid_down = u_mid - hysteresis
        c_hi_up = c_high
        c_hi_down = c_high - hysteresis
        c_mid_up = c_mid
        c_mid_down = c_mid - hysteresis

        new_interval = prev
        if prev == 2000:
            if (u >= u_hi_up) or (c >= c_hi_up):
                new_interval = 100
            elif (u >= u_mid_up) or (c >= c_mid_up):
                new_interval = 500
        elif prev == 500:
            if (u >= u_hi_up) or (c >= c_hi_up):
                new_interval = 100
            elif (u < u_mid_down) and (c < c_mid_down):
                new_interval = 2000
        else:  # prev == 100
            if (u < u_mid_down) and (c < c_mid_down):
                new_interval = 500
            if (u < u_hi_down) and (c < c_hi_down) and (u < u_mid_down) and (c < c_mid_down):
                # allow jump to 2000 only when well below mids
                new_interval = 2000

        counts[new_interval] += 1
        prev = new_interval
    return counts


def compute_transition_flags(
    har_df: pd.DataFrame, truth_df: pd.DataFrame, ccs_thresh: float
) -> List[bool]:
    truth_times = truth_df["time_s"].to_numpy()
    truth_labels = truth_df["truth_label4"].to_numpy()
    flags: List[bool] = []
    for _, row in har_df.iterrows():
        t = row["time_center_s"]
        half = row["window_len_s"] / 2.0
        lo = t - half
        hi = t + half
        mask = (truth_times >= lo) & (truth_times <= hi)
        uniq = set(truth_labels[mask])
        transition = len(uniq) > 1
        if not transition and row["CCS_ema"] >= ccs_thresh:
            transition = True
        flags.append(bool(transition))
    return flags


def apply_policy_with_context(
    har_df: pd.DataFrame,
    truth_df: pd.DataFrame,
    u_mid: float,
    u_high: float,
    c_mid: float,
    c_high: float,
    hysteresis: float,
    ccs_transition_thresh: float,
    initial_interval: int = 500,
):
    counts_ctx = {
        "stable": {100: 0, 500: 0, 1000: 0, 2000: 0},
        "transition": {100: 0, 500: 0, 1000: 0, 2000: 0},
    }
    prev = initial_interval
    flags = compute_transition_flags(har_df, truth_df, ccs_transition_thresh)
    for row, is_trans in zip(har_df.itertuples(index=False), flags):
        if row.mask_eval_window != 1:
            continue
        u = row.U_ema
        c = row.CCS_ema
        u_hi_up = u_high
        u_hi_down = u_high - hysteresis
        u_mid_up = u_mid
        u_mid_down = u_mid - hysteresis
        c_hi_up = c_high
        c_hi_down = c_high - hysteresis
        c_mid_up = c_mid
        c_mid_down = c_mid - hysteresis

        new_interval = prev
        if prev == 2000:
            if (u >= u_hi_up) or (c >= c_hi_up):
                new_interval = 100
            elif (u >= u_mid_up) or (c >= c_mid_up):
                new_interval = 500
        elif prev == 500:
            if (u >= u_hi_up) or (c >= c_hi_up):
                new_interval = 100
            elif (u < u_mid_down) and (c < c_mid_down):
                new_interval = 2000
        else:  # prev == 100
            if (u < u_mid_down) and (c < c_mid_down):
                new_interval = 500
            if (u < u_hi_down) and (c < c_hi_down) and (u < u_mid_down) and (c < c_mid_down):
                new_interval = 2000

        ctx = "transition" if is_trans else "stable"
        counts_ctx[ctx][new_interval] += 1
        prev = new_interval
    return counts_ctx


def evaluate_policy(
    sessions,
    u_mid: float,
    u_high: float,
    c_mid: float,
    c_high: float,
    hysteresis: float,
    initial_interval: int,
    ccs_transition_thresh: float = 0.3,
    context_mixing: bool = False,
) -> Dict[str, object]:
    if not context_mixing:
        total_counts = {100: 0, 500: 0, 1000: 0, 2000: 0}
        for df in sessions:
            counts = apply_policy(df, u_mid, u_high, c_mid, c_high, hysteresis, initial_interval)
            for k in total_counts:
                total_counts[k] += counts[k]
        total_windows = sum(total_counts.values()) or 1
        shares = {k: v / total_windows for k, v in total_counts.items()}
        return {"counts": total_counts, "shares": shares, "total_windows": total_windows}

    # context-aware: stable -> S1, transition -> S4
    total_counts_ctx = {
        "stable": {100: 0, 500: 0, 1000: 0, 2000: 0},
        "transition": {100: 0, 500: 0, 1000: 0, 2000: 0},
    }
    total_windows_ctx = {"stable": 0, "transition": 0}
    for df_har, df_truth in sessions:
        counts_ctx = apply_policy_with_context(
            df_har,
            df_truth,
            u_mid,
            u_high,
            c_mid,
            c_high,
            hysteresis,
            ccs_transition_thresh,
            initial_interval,
        )
        for ctx in total_counts_ctx:
            for k in total_counts_ctx[ctx]:
                total_counts_ctx[ctx][k] += counts_ctx[ctx][k]
            total_windows_ctx[ctx] += sum(counts_ctx[ctx].values())

    # avoid div0
    for ctx in total_windows_ctx:
        if total_windows_ctx[ctx] == 0:
            total_windows_ctx[ctx] = 1
    shares_ctx_norm = {
        ctx: {k: v / total_windows_ctx[ctx] for k, v in total_counts_ctx[ctx].items()}
        for ctx in total_counts_ctx
    }
    total_counts = {k: total_counts_ctx["stable"][k] + total_counts_ctx["transition"][k] for k in [100, 500, 1000, 2000]}
    total_windows = sum(total_counts.values()) or 1
    shares = {k: v / total_windows for k, v in total_counts.items()}
    shares_ctx_weighted = {
        ctx: {k: total_counts_ctx[ctx][k] / total_windows for k in total_counts_ctx[ctx]} for ctx in total_counts_ctx
    }
    return {
        "counts": total_counts,
        "shares": shares,
        "counts_ctx": total_counts_ctx,
        "shares_ctx": shares_ctx_norm,
        "shares_ctx_weighted": shares_ctx_weighted,
        "total_windows": total_windows,
    }


def combine_metrics(shares: Dict[int, float], fixed: pd.DataFrame) -> Dict[str, float]:
    cols = ["pdr_unique_mean", "pout_1s_mean", "tl_mean_s_mean", "E_per_adv_uJ_mean", "avg_power_mW_mean"]
    merged = fixed.groupby("interval_ms")[cols].mean()
    out = {}
    for col in cols:
        out[col] = float(sum(shares[i] * merged.loc[i, col] for i in shares if i in merged.index))
    return out


def combine_metrics_context(
    shares_stable: Dict[int, float],
    shares_transition: Dict[int, float],
    fixed: pd.DataFrame,
) -> Dict[str, float]:
    cols = ["pdr_unique_mean", "pout_1s_mean", "tl_mean_s_mean", "E_per_adv_uJ_mean", "avg_power_mW_mean"]
    stable_df = fixed[fixed["session"] == "S1"].set_index("interval_ms")
    trans_df = fixed[fixed["session"] == "S4"].set_index("interval_ms")
    out: Dict[str, float] = {}
    for col in cols:
        stable_val = sum(shares_stable[i] * stable_df.loc[i, col] for i in shares_stable if i in stable_df.index)
        trans_val = sum(shares_transition[i] * trans_df.loc[i, col] for i in shares_transition if i in trans_df.index)
        out[col] = float(stable_val + trans_val)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--har-dir", type=Path, default=Path("data/mhealth_synthetic_sessions_v1/sessions"))
    ap.add_argument("--metrics", type=Path, default=Path("results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv"))
    ap.add_argument("--power-table", type=Path, default=None, help="Optional CSV to override avg_power_mW (interval_ms,avg_power_mW)")
    ap.add_argument("--u-mid", type=float, default=0.15)
    ap.add_argument("--u-high", type=float, default=0.30)
    ap.add_argument("--c-mid", type=float, default=0.20)
    ap.add_argument("--c-high", type=float, default=0.35)
    ap.add_argument("--hysteresis", type=float, default=0.05)
    ap.add_argument("--initial-interval", type=int, default=500)
    ap.add_argument("--context-mixing", action="store_true", help="Use stable/transition mixing (S1/S4 metrics)")
    ap.add_argument("--transition-ccs-thresh", type=float, default=0.30, help="CCS_ema threshold to mark transition")
    ap.add_argument("--out-json", type=Path, help="Optional path to save JSON summary")
    args = ap.parse_args()

    sessions = load_har_sessions(args.har_dir, with_truth=args.context_mixing)
    fixed = load_fixed_metrics(args.metrics)
    if args.power_table:
        fixed = apply_power_table(fixed, args.power_table)

    pol = evaluate_policy(
        sessions,
        u_mid=args.u_mid,
        u_high=args.u_high,
        c_mid=args.c_mid,
        c_high=args.c_high,
        hysteresis=args.hysteresis,
        initial_interval=args.initial_interval,
        ccs_transition_thresh=args.transition_ccs_thresh,
        context_mixing=args.context_mixing,
    )
    if args.context_mixing:
        combined = combine_metrics_context(
            pol["shares_ctx_weighted"]["stable"],
            pol["shares_ctx_weighted"]["transition"],
            fixed,
        )
    else:
        combined = combine_metrics(pol["shares"], fixed)

    summary = {
        "policy": {
            "u_mid": args.u_mid,
            "u_high": args.u_high,
            "c_mid": args.c_mid,
            "c_high": args.c_high,
            "hysteresis": args.hysteresis,
            "initial_interval": args.initial_interval,
            "context_mixing": args.context_mixing,
            "transition_ccs_thresh": args.transition_ccs_thresh,
            "power_table": str(args.power_table) if args.power_table else None,
        },
        "counts": pol["counts"],
        "shares": pol["shares"],
        "total_windows": pol["total_windows"],
        "counts_ctx": pol.get("counts_ctx"),
        "shares_ctx": pol.get("shares_ctx"),
        "shares_ctx_weighted": pol.get("shares_ctx_weighted"),
        "expected_metrics": combined,
        "notes": "Evaluation uses mask_eval_window==1 only. If context_mixing=True, stable->S1 metrics, transition->S4 metrics.",
    }

    print(json.dumps(summary, indent=2))
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
