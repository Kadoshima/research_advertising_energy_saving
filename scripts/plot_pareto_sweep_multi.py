#!/usr/bin/env python3
"""
Plot Pareto sweep results with two scatters: (pout_1s vs avg_power) and (pout_1s vs adv_rate).

Inputs:
- CSV_PATH (env or default): results/mhealth_policy_eval/pareto_front/pareto_sweep.csv

Outputs:
- OUT_PATH (env or default): results/mhealth_policy_eval/pareto_front/pareto_plots_multi.png
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def load_df(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def scatter(ax, df: pd.DataFrame, ycol: str, ylab: str):
    sc = ax.scatter(df["pout_1s"], df[ycol], c=df["switch_rate"], s=100 * (df["share_100"] + 1e-3), cmap="viridis", alpha=0.7, edgecolor="none")
    ax.set_xlabel("pout_1s (lower better)")
    ax.set_ylabel(ylab)
    ax.grid(True, alpha=0.3)
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("switch_rate")
    # annotate a few best on this axis
    best = df.sort_values(ycol).head(5)
    for _, r in best.iterrows():
        ax.annotate(
            f"{r['u_mid']:.2f}/{r['u_high']:.2f}\n{r['c_mid']:.2f}/{r['c_high']:.2f}",
            (r["pout_1s"], r[ycol]),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=7,
        )


def main():
    base = Path("results/mhealth_policy_eval/pareto_front")
    csv_path = Path(os.environ.get("CSV_PATH", base / "pareto_sweep.csv"))
    out_path = Path(os.environ.get("OUT_PATH", base / "pareto_plots_multi.png"))

    df = load_df(csv_path)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    scatter(axes[0], df, "avg_power_mW", "avg_power (mW)")
    scatter(axes[1], df, "adv_rate", "adv_rate (events/s)")

    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
