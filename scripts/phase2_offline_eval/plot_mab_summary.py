#!/usr/bin/env python3
"""
Plot/format summary artifacts for Phase2 MAB offline studies.

Outputs:
1) tradeoff_cost_vs_pout.png/pdf
2) epsilon_tau_table_e{eps}.md
3) gateb_pareto_front.png/pdf
4) gateb_pareto_front_table.md
5) README.md (generation notes)
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_md_table(df: pd.DataFrame, out_path: Path) -> None:
    header = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    lines = [header, sep]
    for _, row in df.iterrows():
        vals = [str(v) for v in row.to_list()]
        lines.append("| " + " | ".join(vals) + " |")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_tradeoff(df: pd.DataFrame, out_png: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore

    fig, ax = plt.subplots(figsize=(6.8, 4.6), dpi=200)
    envs = sorted(df["env_id"].unique())
    colors: Dict[str, str] = {}
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b", "#e377c2"]
    for i, env in enumerate(envs):
        colors[env] = palette[i % len(palette)]

    for env in envs:
        g = df[df["env_id"] == env]
        ax.errorbar(
            g["cost_mean"],
            g["pout_1s"],
            xerr=g["cost_std"],
            yerr=g["pout_1s_std"] if "pout_1s_std" in g.columns else None,
            fmt="o",
            ms=6,
            color=colors[env],
            capsize=3,
            linestyle="none",
            label=env,
            alpha=0.9,
        )
        for _, r in g.iterrows():
            ax.annotate(
                f"{int(r['action_ms'])}",
                (r["cost_mean"], r["pout_1s"]),
                textcoords="offset points",
                xytext=(4, 4),
                fontsize=8,
                color=colors[env],
            )

    ax.set_xlabel("cost_mean (mJ/60s)")
    ax.set_ylabel("Pout(1s)")
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.legend(loc="best", fontsize=7, frameon=True)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=220)
    if out_png.suffix.lower() == ".png":
        fig.savefig(out_png.with_suffix(".pdf"))


def _env_sources(env_id: str) -> List[str]:
    env_map = {
        "E1_scan90_stress_v5": [
            "results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_full_scan90_v5.csv"
        ],
        "E2_fixed_v01": ["data/実験データ/研究室/phase1_e2_fixed_sweep_2026-01-21_v01/"],
        "E1_uccs_d4b_scan90": ["uccs_d4b_scan90/metrics/01/per_trial.csv"],
        "E1_uccs_d4b_scan70": ["uccs_d4b_scan70/metrics/01_fixed/per_trial.csv"],
    }
    if env_id not in env_map:
        raise KeyError(f"Unknown env_id for constraint sources: {env_id}")
    return env_map[env_id]


def _add_pout_std(df: pd.DataFrame, tau_s: float = 1.0) -> pd.DataFrame:
    # Load constraint models per env and attach std for Pout(1s).
    import sys

    phase2_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(phase2_dir))
    from models.constraint_model import ConstraintModel  # type: ignore

    cache: Dict[str, Dict[int, float]] = {}

    def _std(env_id: str, action: int) -> float:
        if env_id not in cache:
            cm = ConstraintModel(_env_sources(env_id), tau=float(tau_s))
            cache[env_id] = {a: float(cm.std(a)) for a in cm._stats.keys()}
        return float(cache[env_id].get(int(action), 0.0))

    df = df.copy()
    df["pout_1s_std"] = [
        _std(str(r.env_id), int(r.action_ms)) for r in df.itertuples(index=False)
    ]
    return df


def _plot_gateb_pareto(df: pd.DataFrame, out_png: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore

    fig, ax = plt.subplots(figsize=(7.2, 4.8), dpi=200)
    df = df.sort_values(["cost_worst_mean", "viol_first_worst_p95"]).reset_index(drop=True)

    # Scatter + connect to show Pareto ordering.
    ax.plot(
        df["cost_worst_mean"],
        df["viol_first_worst_p95"],
        color="#10b981",
        linewidth=1.5,
        alpha=0.6,
        zorder=1,
    )
    ax.scatter(
        df["cost_worst_mean"],
        df["viol_first_worst_p95"],
        s=70,
        color="#10b981",
        edgecolor="#064e3b",
        linewidth=0.8,
        zorder=2,
    )

    # Label points by margin m (short, readable).
    for _, r in df.iterrows():
        label = f"m={float(r['m']):.2f}"
        ax.annotate(
            label,
            (r["cost_worst_mean"], r["viol_first_worst_p95"]),
            textcoords="offset points",
            xytext=(8, 6),
            fontsize=9,
            color="#064e3b",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#10b981", alpha=0.85),
        )

    ax.set_xlabel("cost_worst_mean (mJ/60s)")
    ax.set_ylabel("violations_first_after_switch_k_worst_p95 (k=50)")
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.set_axisbelow(True)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=220)
    if out_png.suffix.lower() == ".png":
        fig.savefig(out_png.with_suffix(".pdf"))


def _plot_method_tradeoff(df: pd.DataFrame, out_png: Path, scenario_id: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore

    sub = df[df["scenario_id"] == scenario_id].copy()
    if sub.empty:
        raise RuntimeError(f"scenario not found in sim_summary: {scenario_id}")

    keep = ["oracle", "safe_ucb", "filter_ucb", "fixed_ccs", "ucb"]
    sub = sub[sub["method"].isin(keep)].copy()
    sub = sub.sort_values(["method"])

    colors = {
        "oracle": "#0f172a",
        "safe_ucb": "#1d4ed8",
        "filter_ucb": "#10b981",
        "fixed_ccs": "#a855f7",
        "ucb": "#ef4444",
    }
    label_offsets = {
        "oracle": (8, -10),
        "safe_ucb": (-46, 6),
        "filter_ucb": (8, 6),
        "fixed_ccs": (8, 6),
        "ucb": (8, 6),
    }

    fig, ax = plt.subplots(figsize=(6.8, 4.6), dpi=200)
    for _, r in sub.iterrows():
        m = str(r["method"])
        x = float(r["avg_cost_mean"])
        y = float(r["violation_rate_mean"])
        ax.scatter([x], [y], s=70, color=colors.get(m, "#111827"), edgecolor="white", linewidth=0.6, zorder=3)
        ox, oy = label_offsets.get(m, (6, 6))
        ax.annotate(m, (x, y), textcoords="offset points", xytext=(ox, oy), fontsize=9, color=colors.get(m, "#111827"))

    ax.set_xlabel("avg_cost_mean (mJ/60s)")
    ax.set_ylabel("violation_rate_mean")
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.set_axisbelow(True)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=220)
    if out_png.suffix.lower() == ".png":
        fig.savefig(out_png.with_suffix(".pdf"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run-dir",
        type=Path,
        default=Path("results/phase2_offline_studies_2026-01-26_v05"),
        help="phase2_offline_studies_* directory",
    )
    ap.add_argument("--out-dir", type=Path, default=None, help="output directory (default: <run-dir>/figs)")
    ap.add_argument("--epsilon", type=float, default=0.10)
    ap.add_argument("--gateb-top", type=int, default=10, help="rows to keep for gateb table")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    out_dir = args.out_dir or (run_dir / "figs")
    _ensure_dir(out_dir)

    tradeoff_csv = run_dir / "tradeoff_table.csv"
    eps_csv = run_dir / "epsilon_tau_sensitivity.csv"
    gateb_csv = run_dir / "gateb_pareto_front_cap25.csv"
    sim_summary_csv = run_dir / "sim_summary.csv"

    # 1) Tradeoff scatter
    trade = pd.read_csv(tradeoff_csv)
    trade = _add_pout_std(trade, tau_s=1.0)
    _plot_tradeoff(trade, out_dir / "tradeoff_cost_vs_pout.png")

    # 2) Epsilon-tau sensitivity table (filtered by epsilon)
    eps_df = pd.read_csv(eps_csv)
    eps_df = eps_df[eps_df["epsilon"] == float(args.epsilon)].copy()
    eps_df = eps_df.sort_values(["env_id", "action_ms"]).reset_index(drop=True)
    _write_md_table(eps_df, out_dir / f"epsilon_tau_table_e{args.epsilon:.2f}.md")

    # 3) Gate B Pareto front (plot + table)
    gateb_df = pd.read_csv(gateb_csv)
    gateb_df = gateb_df.sort_values(["viol_first_worst_p95", "cost_worst_mean"]).head(int(args.gateb_top))
    _plot_gateb_pareto(gateb_df, out_dir / "gateb_pareto_front.png")
    _write_md_table(
        gateb_df[
            [
                "method",
                "w",
                "m",
                "reset",
                "cost_worst_mean",
                "viol_first_worst_p95",
                "viol_after_worst_mean",
                "vr_worst_mean",
            ]
        ],
        out_dir / "gateb_pareto_front_table.md",
    )

    # 4) Method tradeoff (UCB breaks safety) on a representative scenario
    sim_df = pd.read_csv(sim_summary_csv)
    _plot_method_tradeoff(sim_df, out_dir / "method_tradeoff_e2_cold.png", "E2_actions_500_1000_2000_cold")

    # README (ASCII only)
    readme = out_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# MAB offline summary figures",
                "",
                f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"- Script: scripts/phase2_offline_eval/plot_mab_summary.py",
                f"- Source: {run_dir.as_posix()}",
                "",
                "## Outputs",
                "- tradeoff_cost_vs_pout.png/.pdf",
                f"- epsilon_tau_table_e{args.epsilon:.2f}.md",
                "- gateb_pareto_front.png/.pdf",
                "- method_tradeoff_e2_cold.png/.pdf",
                "- gateb_pareto_front_table.md",
                "",
                "## Inputs",
                f"- {tradeoff_csv.as_posix()}",
                f"- {eps_csv.as_posix()}",
                f"- {gateb_csv.as_posix()}",
                f"- {sim_summary_csv.as_posix()}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
