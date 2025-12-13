#!/usr/bin/env python3
"""
Build a single "letter-ready" plot:
- x: avg_power_mW (optionally overridden by power_table)
- y: pout_1s
- draw δ lines (default: 0.13/0.15/0.17)
- show all Pareto sweep points (U+CCS grid)
- overlay fixed baselines (Fixed 100/500/1000/2000) computed with the same stable/transition mixing rule
- highlight 3 selected policies:
    - P_minPower at δ=0.13
    - P_mid at δ=0.15 (power + switch penalty)
    - P_safe at δ=0.17 (min switch_rate)

This is for Phase 1 (letter) narrative: "constraint boundary exists and a simple rule can trade off QoS vs power".
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def compute_transition_flags(har_df: pd.DataFrame, truth_df: pd.DataFrame, ccs_thresh: float) -> np.ndarray:
    truth_times = truth_df["time_s"].to_numpy()
    truth_labels = truth_df["truth_label4"].to_numpy()
    flags: List[bool] = []
    for _, row in har_df.iterrows():
        t = float(row["time_center_s"])
        half = float(row["window_len_s"]) / 2.0
        lo = t - half
        hi = t + half
        mask = (truth_times >= lo) & (truth_times <= hi)
        uniq = set(truth_labels[mask])
        transition = len(uniq) > 1
        if not transition and float(row["CCS_ema"]) >= ccs_thresh:
            transition = True
        flags.append(bool(transition))
    return np.asarray(flags, dtype=bool)


def compute_context_weights(har_dir: Path, ccs_transition_thresh: float) -> Tuple[float, float]:
    """
    Returns: (stable_ratio, transition_ratio) over all windows with mask_eval_window==1.
    The transition definition matches sweep_policy_pareto.py:
      - truth window contains >1 label OR CCS_ema >= threshold.
    """
    stable = 0
    trans = 0
    for har_fp in sorted(har_dir.glob("*_har.csv")):
        har_df = pd.read_csv(har_fp)
        truth_fp = har_fp.with_name(har_fp.name.replace("_har.csv", "_truth100ms.csv"))
        truth_df = pd.read_csv(truth_fp)

        flags = compute_transition_flags(har_df, truth_df, ccs_transition_thresh)
        mask = har_df["mask_eval_window"].to_numpy() == 1
        flags = flags[mask]
        trans += int(flags.sum())
        stable += int((~flags).sum())
    total = stable + trans
    if total <= 0:
        raise SystemExit("No valid windows found (mask_eval_window==1).")
    return stable / total, trans / total


def load_power_table(power_table: Path) -> Dict[int, float]:
    df = pd.read_csv(power_table)
    if "interval_ms" not in df.columns or "avg_power_mW" not in df.columns:
        raise SystemExit(f"power_table must have columns interval_ms,avg_power_mW: {power_table}")
    return {int(r["interval_ms"]): float(r["avg_power_mW"]) for _, r in df.iterrows()}


def fixed_point(
    fixed_metrics: pd.DataFrame,
    power_map: Dict[int, float],
    interval_ms: int,
    stable_ratio: float,
    transition_ratio: float,
) -> Tuple[float, float]:
    """
    Returns (avg_power_mW, pout_1s) for Fixed interval, using stable->S1 / transition->S4 mixing.
    """
    s1 = fixed_metrics[fixed_metrics["session"] == "S1"].set_index("interval_ms")
    s4 = fixed_metrics[fixed_metrics["session"] == "S4"].set_index("interval_ms")
    if interval_ms not in s1.index or interval_ms not in s4.index:
        raise SystemExit(f"interval_ms={interval_ms} missing in fixed metrics (need S1 and S4 rows).")
    pout = stable_ratio * float(s1.loc[interval_ms, "pout_1s_mean"]) + transition_ratio * float(s4.loc[interval_ms, "pout_1s_mean"])
    power = float(power_map.get(interval_ms, np.nan))
    if not np.isfinite(power):
        raise SystemExit(f"interval_ms={interval_ms} missing in power_table.")
    return power, pout


@dataclass(frozen=True)
class Selected:
    name: str
    delta: float
    row: Dict[str, float]


def pick_policies(pareto: pd.DataFrame) -> List[Selected]:
    """
    Pick 3 representative policies from the Pareto sweep.
    Assumes pareto has columns: pout_1s, avg_power_mW, switch_rate, adv_rate, u_mid/u_high/c_mid/c_high/hyst.
    """
    def pick_min_power(delta: float) -> Selected:
        df = pareto[pareto["pout_1s"] <= delta].copy()
        df = df.sort_values(["avg_power_mW", "pout_1s", "switch_rate", "adv_rate"]).head(1)
        if df.empty:
            raise SystemExit(f"No feasible policies for δ={delta}")
        r = df.iloc[0].to_dict()
        return Selected(name="P_minPower", delta=delta, row=r)

    def pick_mid(delta: float, power_slack_mw: float = 2.5) -> Selected:
        df = pareto[pareto["pout_1s"] <= delta].copy()
        if df.empty:
            raise SystemExit(f"No feasible policies for δ={delta}")
        min_power = float(df["avg_power_mW"].min())
        # "Balanced": keep power near the minimum, then minimize switching.
        cand = df[df["avg_power_mW"] <= (min_power + power_slack_mw)].copy()
        if cand.empty:
            cand = df
        cand = cand.sort_values(["switch_rate", "avg_power_mW", "pout_1s", "adv_rate"]).head(1)
        r = cand.iloc[0].to_dict()
        r["power_slack_mw"] = power_slack_mw
        return Selected(name="P_mid", delta=delta, row=r)

    def pick_safe(delta: float) -> Selected:
        df = pareto[pareto["pout_1s"] <= delta].copy()
        df = df.sort_values(["switch_rate", "avg_power_mW", "pout_1s", "adv_rate"]).head(1)
        if df.empty:
            raise SystemExit(f"No feasible policies for δ={delta}")
        r = df.iloc[0].to_dict()
        return Selected(name="P_safe", delta=delta, row=r)

    # Backward-compatible defaults (used by letter_v1).
    return [pick_min_power(0.13), pick_mid(0.15), pick_safe(0.17)]


def pick_policies_for_deltas(pareto: pd.DataFrame, select_deltas: List[float], style: str) -> List[Selected]:
    """
    Select up to 3 policies based on user-provided deltas.

    - If len(select_deltas) >= 3: pick (minPower, mid, safe) at the first 3 deltas.
    - If len(select_deltas) == 2: pick (minPower, safe).
    - If len(select_deltas) == 1: pick (minPower) only.
    """
    if not select_deltas:
        return pick_policies(pareto)

    def pick_min_power(delta: float) -> Selected:
        df = pareto[pareto["pout_1s"] <= delta].copy()
        df = df.sort_values(["avg_power_mW", "pout_1s", "switch_rate", "adv_rate"]).head(1)
        if df.empty:
            raise SystemExit(f"No feasible policies for δ={delta}")
        return Selected(name="P_minPower", delta=delta, row=df.iloc[0].to_dict())

    def pick_mid(delta: float, power_slack_mw: float = 2.5) -> Selected:
        df = pareto[pareto["pout_1s"] <= delta].copy()
        if df.empty:
            raise SystemExit(f"No feasible policies for δ={delta}")
        min_power = float(df["avg_power_mW"].min())
        cand = df[df["avg_power_mW"] <= (min_power + power_slack_mw)].copy()
        if cand.empty:
            cand = df
        cand = cand.sort_values(["switch_rate", "avg_power_mW", "pout_1s", "adv_rate"]).head(1)
        r = cand.iloc[0].to_dict()
        r["power_slack_mw"] = power_slack_mw
        return Selected(name="P_mid", delta=delta, row=r)

    def pick_safe(delta: float) -> Selected:
        df = pareto[pareto["pout_1s"] <= delta].copy()
        df = df.sort_values(["switch_rate", "avg_power_mW", "pout_1s", "adv_rate"]).head(1)
        if df.empty:
            raise SystemExit(f"No feasible policies for δ={delta}")
        return Selected(name="P_safe", delta=delta, row=df.iloc[0].to_dict())

    ds = list(select_deltas)[:3]
    if style == "minpower":
        out: List[Selected] = []
        for d in ds:
            s = pick_min_power(d)
            out.append(Selected(name=f"P_minPower@{d:.2f}", delta=d, row=s.row))
        return out
    # mixed (default): (minPower, mid, safe)
    if len(ds) >= 3:
        return [pick_min_power(ds[0]), pick_mid(ds[1]), pick_safe(ds[2])]
    if len(ds) == 2:
        return [pick_min_power(ds[0]), pick_safe(ds[1])]
    return [pick_min_power(ds[0])]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pareto-csv", type=Path, default=Path("results/mhealth_policy_eval/pareto_front_v5_power_table/pareto_sweep.csv"))
    ap.add_argument("--fixed-metrics", type=Path, default=Path("results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv"))
    ap.add_argument("--power-table", type=Path, default=Path("results/mhealth_policy_eval/power_table_sleep_eval_2025-12-13.csv"))
    ap.add_argument("--har-dir", type=Path, default=Path("data/mhealth_synthetic_sessions_v1/sessions"))
    ap.add_argument("--transition-ccs-thresh", type=float, default=0.30)
    ap.add_argument("--deltas", type=str, default="0.13,0.15,0.17")
    ap.add_argument(
        "--select-deltas",
        type=str,
        default="",
        help="Comma-separated deltas for selecting representative policies (default: use v1 defaults 0.13/0.15/0.17)",
    )
    ap.add_argument(
        "--select-style",
        choices=["mixed", "minpower"],
        default="mixed",
        help="How to select representative policies when --select-deltas is provided (default: mixed)",
    )
    ap.add_argument("--out-dir", type=Path, default=Path("results/mhealth_policy_eval/letter_v1"))
    args = ap.parse_args()

    deltas = [float(x.strip()) for x in args.deltas.split(",") if x.strip()]
    if not deltas:
        raise SystemExit("No deltas specified.")
    select_deltas = [float(x.strip()) for x in args.select_deltas.split(",") if x.strip()]

    pareto = pd.read_csv(args.pareto_csv)
    fixed = pd.read_csv(args.fixed_metrics)
    power_map = load_power_table(args.power_table)
    stable_ratio, transition_ratio = compute_context_weights(args.har_dir, args.transition_ccs_thresh)

    fixed_points = []
    for i in [100, 500, 1000, 2000]:
        x, y = fixed_point(fixed, power_map, i, stable_ratio, transition_ratio)
        fixed_points.append({"interval_ms": i, "avg_power_mW": x, "pout_1s": y})
    fixed_df = pd.DataFrame(fixed_points)

    selected = pick_policies_for_deltas(pareto, select_deltas, args.select_style)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_png = args.out_dir / "fig_delta_band.png"
    out_json = args.out_dir / "selected_policies.json"
    out_csv = args.out_dir / "selected_policies.csv"

    out_json.write_text(
        json.dumps(
            {
                "inputs": {
                    "pareto_csv": str(args.pareto_csv),
                    "fixed_metrics": str(args.fixed_metrics),
                    "power_table": str(args.power_table),
                    "har_dir": str(args.har_dir),
                    "transition_ccs_thresh": args.transition_ccs_thresh,
                },
                "context_weights": {"stable_ratio": stable_ratio, "transition_ratio": transition_ratio},
                "selected": [
                    {"name": s.name, "delta": s.delta, **{k: s.row.get(k) for k in ["u_mid", "u_high", "c_mid", "c_high", "hyst", "pout_1s", "avg_power_mW", "adv_rate", "switch_rate"]}}
                    for s in selected
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    sel_rows = []
    for s in selected:
        sel_rows.append(
            {
                "name": s.name,
                "delta": s.delta,
                "u_mid": s.row.get("u_mid"),
                "u_high": s.row.get("u_high"),
                "c_mid": s.row.get("c_mid"),
                "c_high": s.row.get("c_high"),
                "hyst": s.row.get("hyst"),
                "pout_1s": s.row.get("pout_1s"),
                "avg_power_mW": s.row.get("avg_power_mW"),
                "adv_rate": s.row.get("adv_rate"),
                "switch_rate": s.row.get("switch_rate"),
            }
        )
    pd.DataFrame(sel_rows).to_csv(out_csv, index=False)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.4, 4.8), dpi=180)

    # all grid points
    ax.scatter(
        pareto["avg_power_mW"],
        pareto["pout_1s"],
        s=16,
        c="#999999",
        alpha=0.25,
        linewidths=0.0,
        label="Rule-based sweep (U+CCS)",
    )

    # delta lines
    for d in deltas:
        ax.axhline(d, linestyle="--", linewidth=1.2, color="#333333", alpha=0.8)

    # fixed points
    ax.scatter(
        fixed_df["avg_power_mW"],
        fixed_df["pout_1s"],
        s=90,
        marker="s",
        c="#1f77b4",
        edgecolors="white",
        linewidths=1.2,
        label="Fixed interval baselines",
        zorder=5,
    )
    for _, r in fixed_df.iterrows():
        ax.annotate(
            f"Fixed {int(r['interval_ms'])}",
            (r["avg_power_mW"], r["pout_1s"]),
            xytext=(6, 4),
            textcoords="offset points",
            fontsize=8,
            color="#1f77b4",
        )

    # selected policies
    colors = {"P_minPower": "#d62728", "P_mid": "#ff7f0e", "P_safe": "#2ca02c"}
    for s in selected:
        x = float(s.row["avg_power_mW"])
        y = float(s.row["pout_1s"])
        key = "P_minPower" if s.name.startswith("P_minPower") else ("P_mid" if s.name.startswith("P_mid") else ("P_safe" if s.name.startswith("P_safe") else s.name))
        ax.scatter(
            [x],
            [y],
            s=120,
            marker="o",
            c=colors.get(key, "#000000"),
            edgecolors="white",
            linewidths=1.4,
            zorder=6,
            label=f"{s.name} (δ={s.delta:.2f})",
        )
        ax.annotate(
            f"{s.name}\nδ={s.delta:.2f}",
            (x, y),
            xytext=(8, -18),
            textcoords="offset points",
            fontsize=9,
            color=colors.get(key, "#000000"),
        )

    ax.set_xlabel("avg_power_mW (power table applied)")
    ax.set_ylabel("pout_1s (context mixing: stable→S1, transition→S4)")
    ax.set_title("QoS (pout_1s) vs Power: Rule-based (U/CCS) with δ bands")
    ax.grid(True, alpha=0.25)
    y_min = min(
        float(min(deltas)) if deltas else float(pareto["pout_1s"].min()),
        float(fixed_df["pout_1s"].min()),
        float(pareto["pout_1s"].min()),
    )
    y_max = max(
        float(max(deltas)) if deltas else float(pareto["pout_1s"].max()),
        float(fixed_df["pout_1s"].max()),
        float(pareto["pout_1s"].max()),
    )
    ax.set_ylim(max(0.0, y_min - 0.01), min(1.0, y_max + 0.02))
    ax.legend(loc="best", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


if __name__ == "__main__":
    main()
