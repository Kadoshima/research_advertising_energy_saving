#!/usr/bin/env python3
"""
CCS Experiment Visualization

Generates figures for the CCS experiment paper:
- Figure 1: Pout-Energy tradeoff curve
- Figure 2: CCS control time series example
- Figure 3: Energy saving comparison bar chart

Usage:
  python scripts/plot_ccs_results.py \
    --json-input results/ccs_experiment_summary.json \
    --out-dir figures/

Requirements:
  pip install matplotlib numpy
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Dict, List, Optional

import numpy as np

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("Warning: matplotlib not available. Install with: pip install matplotlib")


# =============================================================================
# Color Scheme
# =============================================================================
COLORS = {
    'FIXED100': '#2196F3',   # Blue
    'FIXED2000': '#4CAF50',  # Green
    'CCS': '#FF9800',        # Orange
    'E1': '#333333',         # Dark gray
    'E2': '#999999',         # Light gray
}

MARKERS = {
    'FIXED100': 'o',
    'FIXED2000': 's',
    'CCS': '^',
}


# =============================================================================
# Figure 1: Pout-Energy Tradeoff
# =============================================================================
def plot_tradeoff(data: Dict, out_path: str, tau: float = 2.0):
    """
    Plot Pout(tau) vs Average Current tradeoff curve.

    X-axis: Average Current (mA) - lower is better
    Y-axis: Pout(tau) (%) - lower is better
    """
    if not HAS_MPL:
        print("Skipping plot_tradeoff: matplotlib not available")
        return

    fig, ax = plt.subplots(figsize=(8, 6))

    # Plot each condition
    for summary in data['summaries']:
        cond = summary['condition']
        env = summary['environment']

        x = summary['avg_current_ma']['mean']
        y = summary['pout'][f'{int(tau)}s'] * 100  # Convert to percentage
        xerr = summary['avg_current_ma']['std']

        color = COLORS.get(cond, '#666666')
        marker = MARKERS.get(cond, 'o')
        alpha = 1.0 if env == 'E1' else 0.6

        ax.errorbar(x, y, xerr=xerr, fmt=marker, color=color, alpha=alpha,
                    markersize=10, capsize=5, label=f'{cond} ({env})')

    # Theoretical curve (optional)
    # Pout(tau | T_adv) = (1 - p_d)^floor(tau / T_adv)
    p_d = 0.85
    tau_s = tau
    intervals = [100, 500, 1000, 2000]
    # This would need actual current values to plot properly

    # Add Pout constraint line
    ax.axhline(y=5, color='red', linestyle='--', alpha=0.5, label='Pout=5% constraint')

    ax.set_xlabel('Average Current (mA)', fontsize=12)
    ax.set_ylabel(f'Pout({int(tau)}s) (%)', fontsize=12)
    ax.set_title('Energy-QoS Tradeoff', fontsize=14)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    # Invert x-axis so "better" (lower current) is to the right? No, keep standard.
    # Lower-left is the best region

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_path}")


# =============================================================================
# Figure 2: Time Series Example
# =============================================================================
def plot_timeseries(
    power_log_path: str,
    ccs_session_path: str,
    out_path: str,
    duration_s: float = 120  # Show first 2 minutes
):
    """
    Plot CCS control time series example.

    Top: CCS value and thresholds
    Middle: T_adv changes
    Bottom: Current waveform
    """
    if not HAS_MPL:
        print("Skipping plot_timeseries: matplotlib not available")
        return

    import csv

    # Load CCS session
    ccs_data = []
    with open(ccs_session_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_s = int(row['timestamp_ms']) / 1000.0
            if ts_s <= duration_s:
                ccs_data.append({
                    't': ts_s,
                    'ccs': float(row['ccs']),
                    'interval': int(row['interval_ms']),
                })

    if not ccs_data:
        print(f"No CCS data found in {ccs_session_path}")
        return

    # Load power log (optional - for current waveform)
    power_data = []
    if os.path.exists(power_log_path):
        with open(power_log_path, 'r') as f:
            reader = csv.reader(f)
            header_seen = False
            for row in reader:
                if not row or row[0].startswith('#'):
                    continue
                if row[0].lower() == 'ms':
                    header_seen = True
                    continue
                try:
                    ms = float(row[0])
                    ua = float(row[2]) if len(row) > 2 else 0
                    if ms / 1000.0 <= duration_s:
                        power_data.append({'t': ms / 1000.0, 'ua': ua})
                except (ValueError, IndexError):
                    continue

    # Create figure
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)

    # Top: CCS with thresholds
    ax1 = axes[0]
    t_ccs = [d['t'] for d in ccs_data]
    ccs_vals = [d['ccs'] for d in ccs_data]

    ax1.plot(t_ccs, ccs_vals, 'b-', linewidth=1.5, label='CCS')
    ax1.axhline(y=0.90, color='green', linestyle='--', alpha=0.7, label='θ_high=0.90')
    ax1.axhline(y=0.80, color='orange', linestyle='--', alpha=0.7, label='θ_low=0.80')
    ax1.set_ylabel('CCS', fontsize=11)
    ax1.set_ylim(0, 1.05)
    ax1.legend(loc='upper right', fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Middle: T_adv
    ax2 = axes[1]
    t_interval = [d['t'] for d in ccs_data]
    intervals = [d['interval'] for d in ccs_data]

    ax2.step(t_interval, intervals, 'r-', where='post', linewidth=2)
    ax2.set_ylabel('T_adv (ms)', fontsize=11)
    ax2.set_ylim(0, 2200)
    ax2.set_yticks([100, 500, 2000])
    ax2.grid(True, alpha=0.3)

    # Add state labels
    for interval, color, label in [(100, 'red', 'ACTIVE'), (500, 'orange', 'UNCERTAIN'), (2000, 'green', 'QUIET')]:
        ax2.axhline(y=interval, color=color, alpha=0.2, linestyle='-')

    # Bottom: Current (if available)
    ax3 = axes[2]
    if power_data:
        t_pwr = [d['t'] for d in power_data]
        ua_vals = [d['ua'] / 1000.0 for d in power_data]  # Convert to mA

        ax3.plot(t_pwr, ua_vals, 'k-', linewidth=0.5, alpha=0.7)
        ax3.set_ylabel('Current (mA)', fontsize=11)
        ax3.set_ylim(0, max(ua_vals) * 1.1 if ua_vals else 50)
    else:
        ax3.text(0.5, 0.5, 'Power data not available', transform=ax3.transAxes,
                 ha='center', va='center', fontsize=12, color='gray')
        ax3.set_ylabel('Current (mA)', fontsize=11)

    ax3.set_xlabel('Time (s)', fontsize=11)
    ax3.grid(True, alpha=0.3)

    plt.suptitle('CCS-driven BLE Advertising Control', fontsize=14, y=0.98)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_path}")


# =============================================================================
# Figure 3: Energy Saving Bar Chart
# =============================================================================
def plot_energy_saving(data: Dict, out_path: str):
    """
    Plot energy saving comparison as bar chart.

    Grouped by environment (E1, E2), bars for each condition.
    """
    if not HAS_MPL:
        print("Skipping plot_energy_saving: matplotlib not available")
        return

    # Group by environment
    by_env: Dict[str, Dict[str, float]] = {}
    for summary in data['summaries']:
        env = summary['environment']
        cond = summary['condition']
        saving = summary['energy_saving_pct']
        by_env.setdefault(env, {})[cond] = saving

    if not by_env:
        print("No data for energy saving plot")
        return

    fig, ax = plt.subplots(figsize=(8, 6))

    envs = sorted(by_env.keys())
    conditions = ['FIXED100', 'FIXED2000', 'CCS']
    x = np.arange(len(envs))
    width = 0.25

    for i, cond in enumerate(conditions):
        values = [by_env.get(env, {}).get(cond, 0) for env in envs]
        offset = (i - 1) * width
        bars = ax.bar(x + offset, values, width, label=cond, color=COLORS.get(cond, '#666666'))

        # Add value labels
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.annotate(f'{val:+.1f}%',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9)

    ax.set_ylabel('Energy Saving vs FIXED100 (%)', fontsize=12)
    ax.set_xlabel('Environment', fontsize=12)
    ax.set_title('Energy Saving Comparison', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(envs)
    ax.legend()
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_path}")


# =============================================================================
# Figure 4: Interval Distribution (CCS mode)
# =============================================================================
def plot_interval_distribution(data: Dict, out_path: str):
    """
    Plot interval distribution for CCS condition as stacked bar or pie.
    """
    if not HAS_MPL:
        print("Skipping plot_interval_distribution: matplotlib not available")
        return

    # Aggregate interval distribution from trials
    ccs_trials = [t for t in data['trials'] if t['condition'] == 'CCS']
    if not ccs_trials:
        print("No CCS trials for interval distribution plot")
        return

    # Sum distributions
    total_dist = {}
    for trial in ccs_trials:
        for interval, count in trial.get('interval_distribution', {}).items():
            interval_int = int(interval)
            total_dist[interval_int] = total_dist.get(interval_int, 0) + count

    if not total_dist:
        print("No interval distribution data")
        return

    # Calculate percentages
    total = sum(total_dist.values())
    intervals = sorted(total_dist.keys())
    percentages = [total_dist[i] / total * 100 for i in intervals]

    fig, ax = plt.subplots(figsize=(8, 6))

    colors = ['#2196F3', '#FF9800', '#4CAF50']  # 100ms, 500ms, 2000ms
    bars = ax.bar([f'{i}ms' for i in intervals], percentages, color=colors[:len(intervals)])

    # Add percentage labels
    for bar, pct in zip(bars, percentages):
        height = bar.get_height()
        ax.annotate(f'{pct:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=11)

    ax.set_ylabel('Time Fraction (%)', fontsize=12)
    ax.set_xlabel('Advertising Interval', fontsize=12)
    ax.set_title('CCS Mode: Interval Distribution', fontsize=14)
    ax.set_ylim(0, max(percentages) * 1.15)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_path}")


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Generate CCS experiment figures")
    parser.add_argument("--json-input", required=True, help="JSON output from analyze_ccs_experiment.py")
    parser.add_argument("--out-dir", default="figures", help="Output directory for figures")
    parser.add_argument("--power-log", help="Power log for time series plot (optional)")
    parser.add_argument("--ccs-session", default="data/esp32_sessions/session_01.csv",
                        help="CCS session CSV for time series plot")
    args = parser.parse_args()

    if not HAS_MPL:
        print("Error: matplotlib is required. Install with: pip install matplotlib")
        return

    # Load data
    with open(args.json_input, 'r') as f:
        data = json.load(f)

    # Create output directory
    os.makedirs(args.out_dir, exist_ok=True)

    # Generate figures
    print("Generating figures...")

    # Figure 1: Tradeoff curve
    plot_tradeoff(data, os.path.join(args.out_dir, 'fig1_tradeoff.png'))

    # Figure 2: Time series (if power log available)
    if args.power_log and os.path.exists(args.power_log):
        plot_timeseries(
            args.power_log,
            args.ccs_session,
            os.path.join(args.out_dir, 'fig2_timeseries.png')
        )
    elif os.path.exists(args.ccs_session):
        # Plot without power data
        plot_timeseries(
            "",  # No power log
            args.ccs_session,
            os.path.join(args.out_dir, 'fig2_timeseries.png')
        )

    # Figure 3: Energy saving bar chart
    plot_energy_saving(data, os.path.join(args.out_dir, 'fig3_energy_saving.png'))

    # Figure 4: Interval distribution
    plot_interval_distribution(data, os.path.join(args.out_dir, 'fig4_interval_dist.png'))

    print("Done!")


if __name__ == "__main__":
    main()
