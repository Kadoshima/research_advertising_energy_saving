#!/usr/bin/env python3
"""
Build comparison table: Fixed vs U-only vs CCS-only vs U+CCS (default).

Inputs:
- Synthetic HAR logs: data/mhealth_synthetic_sessions_v1/sessions/*_har.csv
- Fixed metrics (scan90 agg v4): results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv
Optional:
- Power table override (interval_ms,avg_power_mW) to replace avg_power_mW_mean.

Outputs:
- Markdown table at results/mhealth_policy_eval/policy_table.md
"""

from __future__ import annotations

import argparse
import pandas as pd
from pathlib import Path
from typing import Dict, List


def load_har_sessions(har_dir: Path) -> List[pd.DataFrame]:
    files = sorted(har_dir.glob("*_har.csv"))
    sessions = []
    for fp in files:
        df = pd.read_csv(fp)
        df["session_id"] = fp.stem.replace("_har", "")
        sessions.append(df)
    return sessions


def load_fixed_metrics(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = [
        "pdr_unique_mean",
        "pout_1s_mean",
        "tl_mean_s_mean",
        "E_per_adv_uJ_mean",
        "avg_power_mW_mean",
    ]
    return df.groupby("interval_ms")[cols].mean().reset_index()


def apply_power_table(fixed: pd.DataFrame, power_table: Path) -> pd.DataFrame:
    """
    Override avg_power_mW_mean using an external table.

    power_table CSV schema:
      interval_ms,avg_power_mW
    """
    pt = pd.read_csv(power_table)
    if "interval_ms" not in pt.columns or "avg_power_mW" not in pt.columns:
        raise SystemExit(f"power_table must have columns interval_ms,avg_power_mW: {power_table}")
    m = pt.set_index("interval_ms")["avg_power_mW"].to_dict()
    out = fixed.copy()
    out["avg_power_mW_mean_orig"] = out["avg_power_mW_mean"]
    override = out["interval_ms"].map(m)
    out["avg_power_mW_mean"] = override.fillna(out["avg_power_mW_mean_orig"])
    return out


def apply_policy(
    df: pd.DataFrame,
    mode: str,
    u_mid: float,
    u_high: float,
    c_mid: float,
    c_high: float,
    hysteresis: float,
    initial_interval: int = 500,
) -> Dict[int, int]:
    counts = {100: 0, 500: 0, 1000: 0, 2000: 0}
    prev = initial_interval
    for _, row in df.iterrows():
        if row["mask_eval_window"] != 1:
            continue
        u = row["U_ema"]
        c = row["CCS_ema"]
        # select effective signals
        if mode == "u_only":
            c = -1.0  # never trigger
        elif mode == "ccs_only":
            u = -1.0  # never trigger

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

        counts[new_interval] += 1
        prev = new_interval
    return counts


def evaluate_dynamic(
    sessions: List[pd.DataFrame],
    mode: str,
    u_mid: float,
    u_high: float,
    c_mid: float,
    c_high: float,
    hysteresis: float,
    initial_interval: int = 500,
) -> Dict[str, object]:
    total = {100: 0, 500: 0, 1000: 0, 2000: 0}
    for df in sessions:
        counts = apply_policy(df, mode, u_mid, u_high, c_mid, c_high, hysteresis, initial_interval)
        for k in total:
            total[k] += counts[k]
    total_windows = sum(total.values()) or 1
    shares = {k: v / total_windows for k, v in total.items()}
    return {"counts": total, "shares": shares}


def combine_metrics(shares: Dict[int, float], fixed: pd.DataFrame) -> Dict[str, float]:
    merged = fixed.set_index("interval_ms")
    out = {}
    for col in ["pdr_unique_mean", "pout_1s_mean", "tl_mean_s_mean", "E_per_adv_uJ_mean", "avg_power_mW_mean"]:
        out[col] = float(sum(shares.get(i, 0) * merged.loc[i, col] for i in merged.index))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--har-dir", type=Path, default=Path("data/mhealth_synthetic_sessions_v1/sessions"))
    ap.add_argument(
        "--metrics",
        type=Path,
        default=Path("results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv"),
    )
    ap.add_argument("--power-table", type=Path, default=None, help="Optional CSV to override avg_power_mW (interval_ms,avg_power_mW)")
    ap.add_argument("--out-md", type=Path, default=Path("results/mhealth_policy_eval/policy_table.md"))
    args = ap.parse_args()

    sessions = load_har_sessions(args.har_dir)
    fixed = load_fixed_metrics(args.metrics)
    if args.power_table:
        fixed = apply_power_table(fixed, args.power_table)

    policies = [
        ("Fixed 100", {"shares": {100: 1.0, 500: 0.0, 1000: 0.0, 2000: 0.0}}),
        ("Fixed 500", {"shares": {100: 0.0, 500: 1.0, 1000: 0.0, 2000: 0.0}}),
        ("Fixed 1000", {"shares": {100: 0.0, 500: 0.0, 1000: 1.0, 2000: 0.0}}),
        ("Fixed 2000", {"shares": {100: 0.0, 500: 0.0, 1000: 0.0, 2000: 1.0}}),
    ]

    # dynamic policies
    params = {"u_mid": 0.15, "u_high": 0.30, "c_mid": 0.20, "c_high": 0.35, "hysteresis": 0.05, "initial_interval": 500}
    for name, mode in [("U-only", "u_only"), ("CCS-only", "ccs_only"), ("U+CCS", "uc")]:
        res = evaluate_dynamic(sessions, mode, **params)
        policies.append((name, res))

    rows = []
    for name, info in policies:
        shares = info["shares"]
        metrics = combine_metrics(shares, fixed)
        rows.append(
            {
                "policy": name,
                "share_100": shares.get(100, 0.0),
                "share_500": shares.get(500, 0.0),
                "share_1000": shares.get(1000, 0.0),
                "share_2000": shares.get(2000, 0.0),
                "pdr_unique": metrics["pdr_unique_mean"],
                "pout_1s": metrics["pout_1s_mean"],
                "tl_mean_s": metrics["tl_mean_s_mean"],
                "E_per_adv_uJ": metrics["E_per_adv_uJ_mean"],
                "avg_power_mW": metrics["avg_power_mW_mean"],
            }
        )

    df_out = pd.DataFrame(rows)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_md, "w") as f:
        f.write("| policy | share100 | share500 | share1000 | share2000 | pdr_unique | pout_1s | tl_mean_s | E_per_adv_uJ | avg_power_mW |\n")
        f.write("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n")
        for _, r in df_out.iterrows():
            f.write(
                f"| {r['policy']} | {r['share_100']:.3f} | {r['share_500']:.3f} | {r['share_1000']:.3f} | {r['share_2000']:.3f} | "
                f"{r['pdr_unique']:.3f} | {r['pout_1s']:.3f} | {r['tl_mean_s']:.2f} | {r['E_per_adv_uJ']:.1f} | {r['avg_power_mW']:.2f} |\n"
            )
    print(f"Wrote {args.out_md}")


if __name__ == "__main__":
    main()
