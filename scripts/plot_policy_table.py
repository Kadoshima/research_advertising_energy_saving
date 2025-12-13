#!/usr/bin/env python3
"""
Plot policy comparison from results/mhealth_policy_eval/policy_table.md.

Reads the Markdown table and produces a 2x2 bar chart for:
- pdr_unique
- pout_1s
- tl_mean_s
- E_per_adv_uJ

Outputs:
- results/mhealth_policy_eval/policy_table.png
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import pandas as pd


def load_md_table(path: Path) -> pd.DataFrame:
    lines = [ln.strip() for ln in path.read_text().splitlines() if ln.strip().startswith("|")]
    data_lines = lines[2:]  # skip header row and separator
    rows: List[List[str]] = []
    for ln in data_lines:
        parts = [p.strip() for p in ln.strip("|").split("|")]
        rows.append(parts)
    cols = [c.strip() for c in lines[0].strip("|").split("|")]
    df = pd.DataFrame(rows, columns=cols)
    # convert numeric columns
    num_cols = [
        "share100",
        "share500",
        "share1000",
        "share2000",
        "pdr_unique",
        "pout_1s",
        "tl_mean_s",
        "E_per_adv_uJ",
        "avg_power_mW",
    ]
    for c in num_cols:
        df[c] = df[c].astype(float)
    return df


def plot(df: pd.DataFrame, out_path: Path):
    policies = df["policy"].tolist()
    x = range(len(policies))
    fig, axes = plt.subplots(2, 2, figsize=(10, 6))
    ax1, ax2, ax3, ax4 = axes.flatten()

    ax1.bar(x, df["pdr_unique"], color="#4caf50")
    ax1.set_title("pdr_unique (higher better)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(policies, rotation=20, ha="right")
    ax1.set_ylim(0.7, 1.05)

    ax2.bar(x, df["pout_1s"], color="#f44336")
    ax2.set_title("pout_1s (lower better)")
    ax2.set_xticks(x)
    ax2.set_xticklabels(policies, rotation=20, ha="right")

    ax3.bar(x, df["tl_mean_s"], color="#2196f3")
    ax3.set_title("tl_mean_s (lower better)")
    ax3.set_xticks(x)
    ax3.set_xticklabels(policies, rotation=20, ha="right")

    ax4.bar(x, df["E_per_adv_uJ"] / 1000.0, color="#9c27b0")
    ax4.set_title("E_per_adv (mJ per adv)")
    ax4.set_xticks(x)
    ax4.set_xticklabels(policies, rotation=20, ha="right")

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    md_path = Path("results/mhealth_policy_eval/policy_table.md")
    out_path = Path("results/mhealth_policy_eval/policy_table.png")
    df = load_md_table(md_path)
    plot(df, out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
