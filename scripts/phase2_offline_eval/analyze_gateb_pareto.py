"""
Gate B Pareto analysis helper (Phase 2 offline studies).

This script aggregates v04 outputs and produces:
- A candidate table that merges:
  - Gate B (shift at start): E2 warm shift from E1 (reset is NOT used here)
  - Gate B (explicit mid-run shift): E1 -> E2 switch mid-run (reset may be used)
- A Pareto front over (cost_worst_mean, violations_first_after_switch_k_worst_p95).

Design note:
- In real operation, reset_on_switch is relevant only when a shift is detected.
  For "shift at start" (warm shift), we evaluate reset=0 and use that as the
  start-shift part of the candidate. For the mid-run shift part, we use the
  candidate's reset flag.

Run from repo root, e.g.:
  python scripts/phase2_offline_eval/analyze_gateb_pareto.py --run-dir results/phase2_offline_studies_2026-01-26_v04
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def _p95(series: pd.Series) -> float:
    s = series.dropna().to_numpy()
    if len(s) == 0:
        return float("nan")
    return float(np.quantile(s, 0.95))


def _pareto_front(points: pd.DataFrame, x_col: str, y_col: str) -> pd.DataFrame:
    """
    Return a subset of non-dominated points (minimize x and y).
    A dominates B if (x_a <= x_b and y_a <= y_b) and at least one strict.
    """
    xs = points[x_col].to_numpy()
    ys = points[y_col].to_numpy()
    keep = np.ones(len(points), dtype=bool)
    for i, (x_i, y_i) in enumerate(zip(xs, ys)):
        if not keep[i]:
            continue
        for j, (x_j, y_j) in enumerate(zip(xs, ys)):
            if i == j:
                continue
            if (x_j <= x_i and y_j <= y_i) and (x_j < x_i or y_j < y_i):
                keep[i] = False
                break
    return points[keep].copy()


def _md_table(df: pd.DataFrame, cols: List[str], float_cols: Dict[str, int]) -> str:
    lines: List[str] = []
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines.extend([header, sep])
    for _, r in df.iterrows():
        row = []
        for c in cols:
            v = r.get(c, "")
            if c in float_cols and pd.notna(v):
                row.append(f"{float(v):.{int(float_cols[c])}f}")
            else:
                row.append(str(v))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run-dir",
        type=str,
        default="results/phase2_offline_studies_2026-01-26_v04",
        help="Directory containing sim_summary.csv and sim_replicates.csv",
    )
    ap.add_argument("--epsilon", type=float, default=0.10, help="QoS constraint epsilon")
    ap.add_argument("--top-n", type=int, default=6, help="Top N to print in markdown")
    ap.add_argument(
        "--max-viol-after-worst-mean",
        type=float,
        default=float("nan"),
        help="Optional cap: keep only candidates with viol_after_worst_mean <= this value",
    )
    ap.add_argument(
        "--max-viol-after-worst-p95",
        type=float,
        default=float("nan"),
        help="Optional cap: keep only candidates with viol_after_worst_p95 <= this value",
    )
    ap.add_argument(
        "--scenario-start",
        type=str,
        default="E2_actions_500_1000_2000_warm_shift_from_E1",
        help="Gate B start-shift scenario_id",
    )
    ap.add_argument(
        "--scenario-mid",
        type=str,
        default="E1_to_E2_actions_500_1000_2000_switch_mid",
        help="Gate B mid-run switch scenario_id",
    )
    ap.add_argument(
        "--out-candidates",
        type=str,
        default="",
        help="Output CSV path for all candidates (default: <run-dir>/gateb_candidates.csv)",
    )
    ap.add_argument(
        "--out-pareto",
        type=str,
        default="",
        help="Output CSV path for pareto front (default: <run-dir>/gateb_pareto_front.csv)",
    )
    ap.add_argument(
        "--out-md",
        type=str,
        default="",
        help="Output markdown path (default: <run-dir>/gateb_pareto.md)",
    )
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    sim_summary = run_dir / "sim_summary.csv"
    sim_reps = run_dir / "sim_replicates.csv"
    if not sim_summary.exists():
        raise FileNotFoundError(sim_summary)
    if not sim_reps.exists():
        raise FileNotFoundError(sim_reps)

    df_sum = pd.read_csv(sim_summary)
    df_rep = pd.read_csv(sim_reps)

    sc_start = str(args.scenario_start)
    sc_mid = str(args.scenario_mid)
    eps = float(args.epsilon)
    cap_after_mean = float(args.max_viol_after_worst_mean)
    cap_after_p95 = float(args.max_viol_after_worst_p95)

    start_df = df_sum[
        (df_sum["scenario_id"] == sc_start)
        & df_sum["method"].astype(str).str.startswith("filter_ucb_online")
    ].copy()
    mid_df = df_sum[
        (df_sum["scenario_id"] == sc_mid)
        & df_sum["method"].astype(str).str.startswith("filter_ucb_online")
    ].copy()
    if start_df.empty:
        raise RuntimeError(f"start scenario not found: {sc_start}")
    if mid_df.empty:
        raise RuntimeError(f"mid scenario not found: {sc_mid}")

    # Index start-shift rows by (w, m). reset is treated as "not used".
    start_idx: Dict[Tuple[float, float], pd.Series] = {}
    start_p95: Dict[Tuple[float, float], Dict[str, float]] = {}
    for _, s1 in start_df.iterrows():
        w = float(s1.get("filter_prior_weight", np.nan))
        m = float(s1.get("filter_margin", np.nan))
        key = (w, m)
        start_idx[key] = s1
        r1 = df_rep[(df_rep["scenario_id"] == sc_start) & (df_rep["method"] == s1["method"])]
        start_p95[key] = {
            "viol_first_p95": _p95(r1["violations_first_after_switch_k"]),
            "viol_after_p95": _p95(r1["violations_after_switch"]),
            "vr_p95": _p95(r1["violation_rate"]),
        }

    rows: List[Dict] = []
    for _, s2 in mid_df.iterrows():
        w = float(s2.get("filter_prior_weight", np.nan))
        m = float(s2.get("filter_margin", np.nan))
        reset = int(s2.get("filter_reset_on_switch", 0))
        key = (w, m)
        if key not in start_idx:
            continue
        s1 = start_idx[key]

        r2 = df_rep[(df_rep["scenario_id"] == sc_mid) & (df_rep["method"] == s2["method"])]
        mid_p95 = {
            "viol_first_p95": _p95(r2["violations_first_after_switch_k"]),
            "viol_after_p95": _p95(r2["violations_after_switch"]),
            "vr_p95": _p95(r2["violation_rate"]),
        }
        s1p = start_p95[key]

        rows.append(
            {
                "method": str(s2["method"]),
                "w": w,
                "m": m,
                "reset": reset,
                "cost_start_mean": float(s1["avg_cost_mean"]),
                "cost_mid_mean": float(s2["avg_cost_mean"]),
                "viol_first_start_mean": float(s1["violations_first_after_switch_k_mean"]),
                "viol_first_mid_mean": float(s2["violations_first_after_switch_k_mean"]),
                "viol_after_start_mean": float(s1["violations_after_switch_mean"]),
                "viol_after_mid_mean": float(s2["violations_after_switch_mean"]),
                "vr_start_mean": float(s1["violation_rate_mean"]),
                "vr_mid_mean": float(s2["violation_rate_mean"]),
                "viol_first_start_p95": float(s1p["viol_first_p95"]),
                "viol_first_mid_p95": float(mid_p95["viol_first_p95"]),
                "viol_after_start_p95": float(s1p["viol_after_p95"]),
                "viol_after_mid_p95": float(mid_p95["viol_after_p95"]),
                "vr_start_p95": float(s1p["vr_p95"]),
                "vr_mid_p95": float(mid_p95["vr_p95"]),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No candidates found (start/mid key mismatch?)")

    # Worst-case across the two Gate B scenarios.
    for base in ("cost", "viol_first", "viol_after", "vr"):
        df[f"{base}_worst_mean"] = df[[f"{base}_start_mean", f"{base}_mid_mean"]].max(axis=1)
    for base in ("viol_first", "viol_after", "vr"):
        df[f"{base}_worst_p95"] = df[[f"{base}_start_p95", f"{base}_mid_p95"]].max(axis=1)

    # Gate filter: keep candidates that satisfy mean constraint in both scenarios.
    df_ok = df[df["vr_worst_mean"] <= eps].copy()
    if np.isfinite(cap_after_mean):
        df_ok = df_ok[df_ok["viol_after_worst_mean"] <= cap_after_mean].copy()
    if np.isfinite(cap_after_p95):
        df_ok = df_ok[df_ok["viol_after_worst_p95"] <= cap_after_p95].copy()

    # Pareto front: (energy cost, early violations p95)
    pareto = _pareto_front(df_ok, "cost_worst_mean", "viol_first_worst_p95")
    pareto = pareto.sort_values(["viol_first_worst_p95", "cost_worst_mean"]).reset_index(drop=True)

    out_candidates = Path(args.out_candidates) if args.out_candidates else (run_dir / "gateb_candidates.csv")
    out_pareto = Path(args.out_pareto) if args.out_pareto else (run_dir / "gateb_pareto_front.csv")
    out_md = Path(args.out_md) if args.out_md else (run_dir / "gateb_pareto.md")
    df_ok.to_csv(out_candidates, index=False)
    pareto.to_csv(out_pareto, index=False)

    top_n = max(1, int(args.top_n))
    show = pareto.head(top_n).copy()
    show_cols = [
        "method",
        "w",
        "m",
        "reset",
        "cost_worst_mean",
        "viol_first_worst_p95",
        "viol_after_worst_mean",
        "vr_worst_mean",
    ]
    md = []
    md.append("# Gate B Pareto (auto-generated)")
    md.append("")
    md.append(f"- run_dir: `{run_dir.as_posix()}`")
    md.append(f"- epsilon: {eps}")
    if np.isfinite(cap_after_mean) or np.isfinite(cap_after_p95):
        md.append("- caps:")
        if np.isfinite(cap_after_mean):
            md.append(f"  - max_viol_after_worst_mean: {cap_after_mean}")
        if np.isfinite(cap_after_p95):
            md.append(f"  - max_viol_after_worst_p95: {cap_after_p95}")
    md.append(f"- scenario_start: `{sc_start}` (reset=0; treated as shift-at-start)")
    md.append(f"- scenario_mid: `{sc_mid}` (reset may be used)")
    md.append("")
    md.append("Pareto front definition:")
    md.append("- x: cost_worst_mean (mJ/60s, lower is better)")
    md.append("- y: violations_first_after_switch_k_worst_p95 (k=50, lower is better)")
    md.append("")
    md.append("Top candidates on Pareto front:")
    md.append(_md_table(show[show_cols], show_cols, {"cost_worst_mean": 3, "viol_first_worst_p95": 2, "viol_after_worst_mean": 2, "vr_worst_mean": 5}))
    md.append("")
    md.append(f"Full tables: `{out_candidates.as_posix()}`, `{out_pareto.as_posix()}`")
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"[OK] wrote: {out_candidates}")
    print(f"[OK] wrote: {out_pareto}")
    print(f"[OK] wrote: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
