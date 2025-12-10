#!/usr/bin/env python3
"""
Plot Pout vs relative energy for stress causal real vs simulation.

Inputs:
  --real-summary: CSV from analyze_stress_causal_real.py (needs columns mode,pout_1s,avg_power_mW)
  --sim-summary:  CSV like Mode_C_2_シミュレート_causal/sim_timeline_metrics_causal_agg.csv
                  (needs columns mode,pout_1.0s or pout_1s)
Options:
  --energy-ref-mode: mode name to normalize energy (default: FIXED_100)
  --out: output PNG path (default: results/stress_causal_real_vs_sim.png)

Behavior:
  - Aggregates real summary by mode (mean).
  - Normalizes avg_power_mW by reference mode to show relative energy.
  - Plots Pout(1s) bars for real/sim (grouped) and relative energy as a line.
"""
from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path
from typing import Dict, List, Tuple


def read_real(path: Path) -> Dict[str, Dict[str, float]]:
    data: Dict[str, List[float]] = {}
    energy: Dict[str, List[float]] = {}
    with path.open() as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            mode = (row.get("mode") or "").upper()
            if not mode:
                continue
            pout = float(row.get("pout_1s") or row.get("pout_1.0s") or 0.0)
            pwr = float(row.get("avg_power_mW") or 0.0)
            data.setdefault(mode, []).append(pout)
            energy.setdefault(mode, []).append(pwr)
    agg = {}
    for m in data:
        agg[m] = {
            "pout_1s": statistics.mean(data[m]),
            "avg_power_mW": statistics.mean(energy.get(m, [0.0])),
        }
    return agg


def read_sim(path: Path) -> Dict[str, float]:
    res: Dict[str, float] = {}
    with path.open() as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            mode = (row.get("mode") or "").upper()
            pout = float(row.get("pout_1.0s") or row.get("pout_1s") or 0.0)
            res[mode] = pout
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description="Plot stress causal real vs simulation Pout and relative energy.")
    ap.add_argument("--real-summary", required=True, type=Path)
    ap.add_argument("--sim-summary", required=True, type=Path)
    ap.add_argument("--energy-ref-mode", default="FIXED_100")
    ap.add_argument("--out", default=Path("results/stress_causal_real_vs_sim.png"), type=Path)
    args = ap.parse_args()

    real = read_real(args.real_summary)
    sim = read_sim(args.sim_summary)
    modes = ["FIXED_100", "FIXED_2000", "CCS_CAUSAL"]
    modes = [m for m in modes if m in real]
    if not modes:
        modes = sorted(real.keys())

    ref_mode = args.energy_ref_mode.upper()
    ref_power = real.get(ref_mode, {}).get("avg_power_mW")
    if not ref_power:
        raise SystemExit(f"Reference mode {ref_mode} not found in real summary.")

    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as e:
        raise SystemExit(f"matplotlib is required for plotting: {e}")

    x = list(range(len(modes)))
    width = 0.35
    real_pout = [real[m]["pout_1s"] for m in modes]
    sim_pout = [sim.get(m, 0.0) for m in modes]
    rel_energy = [real[m]["avg_power_mW"] / ref_power for m in modes]

    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax2 = ax1.twinx()

    ax1.bar([i - width / 2 for i in x], real_pout, width=width, label="Real Pout(1s)", color="#4C6EF5")
    ax1.bar([i + width / 2 for i in x], sim_pout, width=width, label="Sim Pout(1s)", color="#FAB005")

    ax2.plot(x, rel_energy, marker="o", color="#2F9E44", label="Relative Energy (avg_power)")

    ax1.set_xticks(x)
    ax1.set_xticklabels(modes)
    ax1.set_ylabel("Pout(1s)")
    ax2.set_ylabel(f"Relative Energy vs {ref_mode} (avg_power)")
    ax1.set_ylim(0, max(real_pout + sim_pout + [0.5]) * 1.1)
    ax2.set_ylim(0, max(rel_energy + [1.0]) * 1.2)
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    ax1.set_title("Stress causal: Real vs Sim (Pout and Relative Energy)")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    print(f"[INFO] wrote plot to {args.out}")


if __name__ == "__main__":
    main()
