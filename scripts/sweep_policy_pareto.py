#!/usr/bin/env python3
"""
Grid sweep for threshold/hysteresis settings to approximate a Pareto front.

Inputs:
- HAR logs with U/CCS: data/mhealth_synthetic_sessions_v1/sessions/*_har.csv
- Fixed-interval metrics (scan90 S1/S4 avg): results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv

Outputs:
- CSV with all grid results
- Markdown summary with top candidates under Pout(1s) constraints (δ=0.1,0.2)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


ALL_INTERVALS = (100, 500, 1000, 2000)


def parse_actions(actions_str: str) -> List[int]:
    parts = [p.strip() for p in (actions_str or "").split(",") if p.strip()]
    if not parts:
        return list(ALL_INTERVALS)
    out: List[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError as e:
            raise SystemExit(f"invalid --actions value: {p}") from e
    invalid = sorted(set(out) - set(ALL_INTERVALS))
    if invalid:
        raise SystemExit(f"--actions must be subset of {ALL_INTERVALS}, got invalid: {invalid}")
    out = sorted(set(out))
    if len(out) < 2:
        raise SystemExit("--actions must contain at least two intervals (e.g. 100,500)")
    return out


def clamp_interval(interval_ms: int, allowed: List[int]) -> int:
    if interval_ms in allowed:
        return interval_ms
    # Nearest interval; tie-break towards smaller interval.
    return min(allowed, key=lambda a: (abs(a - interval_ms), a))


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
    return pd.read_csv(path)


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
    params: Dict[str, float],
    allowed_actions: List[int],
    initial_interval: int = 500,
) -> Dict[str, object]:
    counts = {100: 0, 500: 0, 1000: 0, 2000: 0}
    prev = clamp_interval(initial_interval, allowed_actions)
    switches = 0
    for _, row in df.iterrows():
        if row["mask_eval_window"] != 1:
            continue
        u = row["U_ema"]
        c = row["CCS_ema"]
        u_hi_up = params["u_high"]
        u_hi_down = params["u_high"] - params["hyst"]
        u_mid_up = params["u_mid"]
        u_mid_down = params["u_mid"] - params["hyst"]
        c_hi_up = params["c_high"]
        c_hi_down = params["c_high"] - params["hyst"]
        c_mid_up = params["c_mid"]
        c_mid_down = params["c_mid"] - params["hyst"]

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

        new_interval = clamp_interval(new_interval, allowed_actions)
        if new_interval != prev:
            switches += 1
        counts[new_interval] += 1
        prev = new_interval
    total = sum(counts.values()) or 1
    shares = {k: counts[k] / total for k in counts}
    return {"counts": counts, "shares": shares, "switches": switches, "total": total}


def compute_transition_flags(har_df: pd.DataFrame, truth_df: pd.DataFrame, ccs_thresh: float) -> List[bool]:
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
    params: Dict[str, float],
    ccs_transition_thresh: float,
    allowed_actions: List[int],
    initial_interval: int = 500,
) -> Dict[str, object]:
    counts_ctx = {
        "stable": {100: 0, 500: 0, 1000: 0, 2000: 0},
        "transition": {100: 0, 500: 0, 1000: 0, 2000: 0},
    }
    switches = 0
    prev = clamp_interval(initial_interval, allowed_actions)
    flags = compute_transition_flags(har_df, truth_df, ccs_transition_thresh)
    for row, is_trans in zip(har_df.itertuples(index=False), flags):
        if row.mask_eval_window != 1:
            continue
        u = row.U_ema
        c = row.CCS_ema
        u_hi_up = params["u_high"]
        u_hi_down = params["u_high"] - params["hyst"]
        u_mid_up = params["u_mid"]
        u_mid_down = params["u_mid"] - params["hyst"]
        c_hi_up = params["c_high"]
        c_hi_down = params["c_high"] - params["hyst"]
        c_mid_up = params["c_mid"]
        c_mid_down = params["c_mid"] - params["hyst"]

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

        new_interval = clamp_interval(new_interval, allowed_actions)
        if new_interval != prev:
            switches += 1
        ctx = "transition" if is_trans else "stable"
        counts_ctx[ctx][new_interval] += 1
        prev = new_interval

    totals = {k: counts_ctx["stable"][k] + counts_ctx["transition"][k] for k in [100, 500, 1000, 2000]}
    return {"counts_ctx": counts_ctx, "switches": switches, "total": sum(totals.values())}


def combine_metrics(shares: Dict[int, float], fixed: pd.DataFrame) -> Dict[str, float]:
    merged = fixed.set_index("interval_ms")
    out = {}
    for col in ["pdr_unique_mean", "pout_1s_mean", "tl_mean_s_mean", "E_per_adv_uJ_mean", "avg_power_mW_mean"]:
        out[col] = float(sum(shares.get(i, 0.0) * merged.loc[i, col] for i in merged.index))
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
        stable_val = sum(shares_stable.get(i, 0.0) * stable_df.loc[i, col] for i in stable_df.index)
        trans_val = sum(shares_transition.get(i, 0.0) * trans_df.loc[i, col] for i in trans_df.index)
        out[col] = float(stable_val + trans_val)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--har-dir", type=Path, default=Path("data/mhealth_synthetic_sessions_v1/sessions"))
    ap.add_argument("--metrics", type=Path, default=Path("results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv"))
    ap.add_argument("--power-table", type=Path, default=None, help="Optional CSV to override avg_power_mW (interval_ms,avg_power_mW)")
    ap.add_argument("--out-csv", type=Path, default=Path("results/mhealth_policy_eval/pareto_front/pareto_sweep.csv"))
    ap.add_argument("--out-summary", type=Path, default=Path("results/mhealth_policy_eval/pareto_front/pareto_summary.md"))
    ap.add_argument("--metric", choices=["energy", "power"], default="energy", help="Objective for sorting summaries: energy=E_per_adv_uJ, power=avg_power_mW")
    ap.add_argument("--context-mixing", action="store_true", help="Use stable/transition mixing (S1/S4)")
    ap.add_argument("--transition-ccs-thresh", type=float, default=0.30, help="CCS_ema threshold to mark transition")
    ap.add_argument("--actions", type=str, default="100,500,1000,2000", help="Allowed intervals (subset of 100,500,1000,2000), e.g. 100,500")
    ap.add_argument("--deltas", type=str, default="0.10,0.20", help="Comma-separated δ values for summary (default: 0.10,0.20)")
    ap.add_argument("--top-n", type=int, default=10, help="Top-N rows per summary table (default 10)")
    args = ap.parse_args()

    sessions = load_har_sessions(args.har_dir, with_truth=args.context_mixing)
    fixed = load_fixed_metrics(args.metrics)
    if args.power_table:
        fixed = apply_power_table(fixed, args.power_table)
    allowed_actions = parse_actions(args.actions)

    grid_u_mid = [0.10, 0.15, 0.20]
    grid_u_high = [0.25, 0.30, 0.35]
    grid_c_mid = [0.10, 0.15, 0.20]
    grid_c_high = [0.25, 0.30, 0.35]
    grid_hyst = [0.02, 0.05, 0.08]

    rows = []
    for u_mid in grid_u_mid:
        for u_high in grid_u_high:
            if u_high <= u_mid:
                continue
            for c_mid in grid_c_mid:
                for c_high in grid_c_high:
                    if c_high <= c_mid:
                        continue
                    for hyst in grid_hyst:
                        params = {"u_mid": u_mid, "u_high": u_high, "c_mid": c_mid, "c_high": c_high, "hyst": hyst}
                        total_counts = {100: 0, 500: 0, 1000: 0, 2000: 0}
                        total_switches = 0
                        total_windows = 0
                        shares_ctx = None
                        if args.context_mixing:
                            total_counts_ctx = {
                                "stable": {100: 0, 500: 0, 1000: 0, 2000: 0},
                                "transition": {100: 0, 500: 0, 1000: 0, 2000: 0},
                            }
                            for df_har, df_truth in sessions:
                                res = apply_policy_with_context(
                                    df_har,
                                    df_truth,
                                    params,
                                    args.transition_ccs_thresh,
                                    allowed_actions,
                                )
                                for ctx in total_counts_ctx:
                                    for k in total_counts_ctx[ctx]:
                                        total_counts_ctx[ctx][k] += res["counts_ctx"][ctx][k]
                                total_switches += res["switches"]
                                total_windows += res["total"]
                            for k in total_counts:
                                total_counts[k] = total_counts_ctx["stable"][k] + total_counts_ctx["transition"][k]
                            # weighted by total windows (not per-context normalization)
                            stable_weight = sum(total_counts_ctx["stable"].values()) or 1
                            trans_weight = sum(total_counts_ctx["transition"].values()) or 1
                            total_windows = stable_weight + trans_weight
                            shares_ctx = {
                                "stable": {k: total_counts_ctx["stable"][k] / total_windows for k in total_counts_ctx["stable"]},
                                "transition": {k: total_counts_ctx["transition"][k] / total_windows for k in total_counts_ctx["transition"]},
                            }
                        else:
                            for df in sessions:
                                res = apply_policy(df, params, allowed_actions)
                                for k in total_counts:
                                    total_counts[k] += res["counts"][k]
                                total_switches += res["switches"]
                                total_windows += res["total"]
                        shares = {k: total_counts[k] / total_windows for k in total_counts}
                        metrics = (
                            combine_metrics_context(shares_ctx["stable"], shares_ctx["transition"], fixed)
                            if args.context_mixing
                            else combine_metrics(shares, fixed)
                        )
                        adv_rate = (
                            shares[100] / 0.1
                            + shares[500] / 0.5
                            + shares[1000] / 1.0
                            + shares[2000] / 2.0
                        )
                        mean_interval_ms = 1000.0 / adv_rate if adv_rate > 0 else 0
                        rows.append(
                            {
                                "u_mid": u_mid,
                                "u_high": u_high,
                                "c_mid": c_mid,
                                "c_high": c_high,
                                "hyst": hyst,
                                "share_100": shares[100],
                                "share_500": shares[500],
                                "share_1000": shares[1000],
                                "share_2000": shares[2000],
                                "switch_rate": total_switches / total_windows if total_windows else 0,
                                "pdr_unique": metrics["pdr_unique_mean"],
                                "pout_1s": metrics["pout_1s_mean"],
                                "tl_mean_s": metrics["tl_mean_s_mean"],
                                "E_per_adv_uJ": metrics["E_per_adv_uJ_mean"],
                                "avg_power_mW": metrics["avg_power_mW_mean"],
                                "adv_rate": adv_rate,
                                "mean_interval_ms": mean_interval_ms,
                            }
                        )
    df = pd.DataFrame(rows)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_csv, index=False)
    print(f"wrote {args.out_csv} ({len(df)} rows)")

    def _parse_deltas(s: str) -> List[float]:
        out: List[float] = []
        for part in s.split(","):
            part = part.strip()
            if not part:
                continue
            out.append(float(part))
        return out or [0.10, 0.20]

    deltas = _parse_deltas(args.deltas)
    top_n = max(1, int(args.top_n))

    cols_common = [
        "u_mid",
        "u_high",
        "c_mid",
        "c_high",
        "hyst",
        "pout_1s",
        "E_per_adv_uJ",
        "avg_power_mW",
        "adv_rate",
        "switch_rate",
        "share_100",
        "share_500",
        "share_1000",
        "share_2000",
    ]

    def summarize_block(df_all: pd.DataFrame, delta: float) -> str:
        df_f = df_all[df_all["pout_1s"] <= delta].copy()
        lines = [f"## δ = {delta:.2f}", f"- feasible: {len(df_f)}/{len(df_all)}", ""]
        if df_f.empty:
            return "\n".join(lines)

        def render(title: str, df_sub: pd.DataFrame) -> List[str]:
            out = [f"### {title}", ""]
            out.append(
                "| u_mid | u_high | c_mid | c_high | hyst | pout_1s | E_per_adv_uJ | avg_power_mW | adv_rate | switch_rate | share100 | share500 | share1000 | share2000 |"
            )
            out.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
            for _, r in df_sub.iterrows():
                out.append(
                    f"| {r.u_mid:.2f} | {r.u_high:.2f} | {r.c_mid:.2f} | {r.c_high:.2f} | {r.hyst:.2f} | "
                    f"{r.pout_1s:.3f} | {r.E_per_adv_uJ:.1f} | {r.avg_power_mW:.2f} | {r.adv_rate:.2f} | {r.switch_rate:.3f} | "
                    f"{r.share_100:.3f} | {r.share_500:.3f} | {r.share_1000:.3f} | {r.share_2000:.3f} |"
                )
            return out

        by_adv = df_f.sort_values(["adv_rate", "avg_power_mW", "switch_rate", "pout_1s"]).head(top_n)
        by_switch = df_f.sort_values(["switch_rate", "avg_power_mW", "adv_rate", "pout_1s"]).head(top_n)
        by_pout = df_f.sort_values(["pout_1s", "avg_power_mW", "adv_rate", "switch_rate"]).head(top_n)
        by_power = df_f.sort_values(["avg_power_mW", "pout_1s", "switch_rate", "adv_rate"]).head(top_n)

        lines += render("Top by avg_power_mW (power-min)", by_power)
        lines.append("")
        lines += render("Top by adv_rate (event-min)", by_adv)
        lines.append("")
        lines += render("Top by switch_rate (stable)", by_switch)
        lines.append("")
        lines += render("Top by pout_1s (QoS)", by_pout)
        return "\n".join(lines)

    summary_lines = ["# Pareto-like sweep (U+CCS)", "", f"Total grid points: {len(df)}", ""]
    summary_lines.append(f"- metric: `{args.metric}`")
    summary_lines.append(f"- context_mixing: `{args.context_mixing}`")
    summary_lines.append(f"- actions: `{allowed_actions}`")
    summary_lines.append(f"- power_table: `{args.power_table}`")
    summary_lines.append("")
    for d in deltas:
        summary_lines.append(summarize_block(df[cols_common], d))
        summary_lines.append("")
    args.out_summary.write_text("\n".join(summary_lines))
    print(f"wrote {args.out_summary}")


if __name__ == "__main__":
    main()
