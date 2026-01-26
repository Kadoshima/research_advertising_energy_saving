#!/usr/bin/env python3
"""
Plot Pareto sweep results.

Inputs:
- results/mhealth_policy_eval/pareto_front/pareto_sweep.csv

Outputs:
- results/mhealth_policy_eval/pareto_front/pareto_plots.png (default paths; override via env CSV_PATH/OUT_PATH)
  - Left: scatter of pout_1s vs metric (avg_power or E_per_adv) colored by switch_rate, size by share_100.
  - Right: stacked bars of interval shares for top-10 configs under pout_1s<=0.2 sorted by metric.
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Avoid home dir cache issues
os.environ.setdefault("MPLCONFIGDIR", str(Path("results/mpl_cache")))


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df


POUT_LIMIT = float(os.environ.get("POUT_LIMIT", "0.2"))


def scatter_plot(ax, df: pd.DataFrame, metric: str, selected_path: Path):
    ycol = "avg_power_mW" if metric == "power" else "E_per_adv_uJ"
    ylabel = "Average power (mW)" if metric == "power" else "Energy per adv (uJ)"
    if POUT_LIMIT > 0:
        ax.axvspan(0.0, POUT_LIMIT, color="#d1fae5", alpha=0.18, zorder=0)
        ax.axvline(POUT_LIMIT, linestyle="--", linewidth=1.2, color="#111827", alpha=0.8)
    sc = ax.scatter(
        df["pout_1s"],
        df[ycol],
        c=df["switch_rate"],
        s=100 * (df["share_100"] + 1e-3),
        cmap="viridis",
        alpha=0.7,
        edgecolor="none",
    )
    ax.set_xlabel(r"$P_{\mathrm{out}}(1\,\mathrm{s})$")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("switch rate")
    # annotate best few low-energy points
    best = df.sort_values(ycol).head(5)
    for _, r in best.iterrows():
        ax.annotate(
            f"{r['u_mid']:.2f}/{r['u_high']:.2f}\n{r['c_mid']:.2f}/{r['c_high']:.2f}",
            (r["pout_1s"], r[ycol]),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=7,
        )

    # Highlight selected policies (if available).
    if selected_path.exists():
        sel = pd.read_csv(selected_path)
        sel_ycol = ycol if ycol in sel.columns else ("avg_power_mW" if "avg_power_mW" in sel.columns else "")
        if not sel_ycol:
            return
        sel_colors = {
            "P_minPower": "#d62728",
            "P_mid": "#ff7f0e",
            "P_safe": "#2ca02c",
        }
        for _, r in sel.iterrows():
            name = str(r["name"])
            ax.scatter(
                [r["pout_1s"]],
                [r[sel_ycol]],
                s=140,
                marker="o",
                c=sel_colors.get(name, "#111827"),
                edgecolors="#111827",
                linewidths=0.8,
                zorder=4,
                label=name,
            )
            ax.annotate(
                name,
                (r["pout_1s"], r[sel_ycol]),
                textcoords="offset points",
                xytext=(6, -10),
                fontsize=8,
                color=sel_colors.get(name, "#111827"),
            )
        ax.legend(loc="upper right", fontsize=8, frameon=True)


def stacked_bar(ax, df: pd.DataFrame, metric: str):
    df = df.copy()
    df["id"] = [f"{i+1}" for i in range(len(df))]
    ax.bar(df["id"], df["share_100"], label="100", color="#4caf50")
    ax.bar(df["id"], df["share_500"], bottom=df["share_100"], label="500", color="#2196f3")
    ax.bar(
        df["id"],
        df["share_2000"],
        bottom=df["share_100"] + df["share_500"],
        label="2000",
        color="#9c27b0",
    )
    ax.set_ylabel("interval share")
    ax.set_xlabel(f"top-10 under P_out(1 s) <= {POUT_LIMIT:.2f} (sorted by {metric})")
    ax.set_ylim(0, 1.05)
    ax.legend(title="interval (ms)")
    ax.grid(True, axis="y", alpha=0.3)
    # annotate power and switch_rate
    for idx, (_, r) in enumerate(df.iterrows()):
        ax.text(
            idx,
            1.02,
            f"{('P=' + str(r['avg_power_mW']) + 'mW') if metric=='power' else ('E=' + str(round(r['E_per_adv_uJ'],1)) + 'uJ')}\npout={r['pout_1s']:.3f}\nsw={r['switch_rate']:.2f}",
            ha="center",
            va="bottom",
            fontsize=7,
        )


def main():
    base = Path("results/mhealth_policy_eval/pareto_front")
    csv_path = Path(os.environ.get("CSV_PATH", base / "pareto_sweep.csv"))
    out_path = Path(os.environ.get("OUT_PATH", base / "pareto_plots.png"))
    metric = os.environ.get("METRIC", "power")
    selected_path = Path(os.environ.get("SELECTED_PATH", "results/mhealth_policy_eval/letter_v1/selected_policies.csv"))
    base.mkdir(parents=True, exist_ok=True)

    df = load_data(csv_path)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    scatter_plot(axes[0], df, metric, selected_path)

    sort_col = "avg_power_mW" if metric == "power" else "E_per_adv_uJ"
    top = df[df["pout_1s"] <= 0.2].sort_values(sort_col).head(10)
    stacked_bar(axes[1], top, metric)

    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
