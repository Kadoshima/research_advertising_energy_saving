#!/usr/bin/env python3
"""
CCS Experiment Analysis Pipeline

Analyzes CCS experiment data to compute:
- Energy metrics: average current (mA), total energy (mJ), energy per interval
- QoS metrics: Pout(tau), TL distribution (p50/p95), PDR
- Comparison across conditions: FIXED-100, FIXED-2000, CCS

Usage:
  python scripts/analyze_ccs_experiment.py \
    --data-dir data/ccs_experiments \
    --session-manifest data/esp32_sessions/session_manifest.json \
    --baseline-p-off 22.1 \
    --out results/ccs_experiment_summary.md

Expected directory structure:
  data/ccs_experiments/
  ├── E1/  (or E2/)
  │   ├── FIXED100/
  │   │   ├── pwr_E1_FIXED100_01.csv  (TXSD power log)
  │   │   └── rx_E1_FIXED100_01.csv   (RX log)
  │   ├── FIXED2000/
  │   └── CCS/
  └── manifest.yaml  (optional: include/exclude trials)

Log formats:
  - Power log (TXSD): ms,mv,uA,p_mW or ms,mv,uA,interval_ms
  - RX log: ms,event,rssi,addr,mfd
  - CCS session definition: data/esp32_sessions/session_*.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import statistics as stats
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# =============================================================================
# Constants
# =============================================================================
INTERVALS_MS = [100, 500, 2000]
TAU_VALUES_S = [1.0, 2.0, 3.0]  # Pout evaluation thresholds
P_D_DEFAULT = 0.85  # Default packet delivery probability per advertisement


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class PowerSample:
    ms: float
    mv: float
    ua: float
    p_mw: float
    interval_ms: Optional[int] = None


@dataclass
class RxEvent:
    ms: float
    rssi: int
    mfd: str
    seq: Optional[int] = None


@dataclass
class TrialResult:
    trial_id: str
    condition: str  # FIXED100, FIXED2000, CCS
    environment: str  # E1, E2

    # Power metrics
    duration_ms: float = 0.0
    total_energy_mj: float = 0.0
    avg_current_ma: float = 0.0
    avg_power_mw: float = 0.0

    # Advertising metrics
    adv_count: int = 0
    interval_distribution: Dict[int, int] = field(default_factory=dict)

    # RX metrics
    rx_count: int = 0
    rx_unique: int = 0
    pdr: float = 0.0

    # TL metrics (per activity transition event)
    tl_values_ms: List[float] = field(default_factory=list)
    tl_p50_ms: float = 0.0
    tl_p95_ms: float = 0.0

    # Pout metrics
    pout: Dict[float, float] = field(default_factory=dict)  # tau -> pout


@dataclass
class ConditionSummary:
    condition: str
    environment: str
    n_trials: int = 0

    # Power (mean ± std)
    avg_current_ma_mean: float = 0.0
    avg_current_ma_std: float = 0.0
    total_energy_mj_mean: float = 0.0
    total_energy_mj_std: float = 0.0

    # QoS (mean ± std)
    tl_p50_mean: float = 0.0
    tl_p95_mean: float = 0.0
    pout_1s_mean: float = 0.0
    pout_2s_mean: float = 0.0
    pout_3s_mean: float = 0.0
    pdr_mean: float = 0.0

    # Energy saving vs FIXED100
    energy_saving_pct: float = 0.0


# =============================================================================
# Parsing Functions
# =============================================================================
def parse_power_log(path: str) -> Tuple[List[PowerSample], Dict]:
    """
    Parse TXSD power log.

    Returns:
        samples: List of PowerSample
        summary: Dict with summary line data if present
    """
    samples = []
    summary = {}

    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        reader = csv.reader(fh)
        header = None
        col_map = {}

        for row in reader:
            if not row:
                continue

            # Parse summary/meta lines
            if row[0].startswith('#'):
                line = ','.join(row)
                if 'summary' in line.lower():
                    # Extract summary values
                    m = re.search(r'E_total_mJ=([0-9.]+)', line)
                    if m:
                        summary['E_total_mJ'] = float(m.group(1))
                    m = re.search(r'adv_count=([0-9]+)', line)
                    if m:
                        summary['adv_count'] = int(m.group(1))
                    m = re.search(r'ms_total=([0-9]+)', line)
                    if m:
                        summary['ms_total'] = int(m.group(1))
                continue

            # Detect header row
            if header is None and any(c.lower() in ('ms', 't', 'mv', 'ua', 'p_mw') for c in row):
                header = [c.lower().strip() for c in row]
                for i, c in enumerate(header):
                    if c in ('ms', 't', 'time_ms'):
                        col_map['ms'] = i
                    elif c in ('mv', 'mV'):
                        col_map['mv'] = i
                    elif c in ('ua', 'µa', 'ua '):
                        col_map['ua'] = i
                    elif c == 'p_mw':
                        col_map['p_mw'] = i
                    elif c == 'interval_ms':
                        col_map['interval_ms'] = i
                continue

            # Parse data row
            try:
                ms = float(row[col_map.get('ms', 0)])
                mv = float(row[col_map.get('mv', 1)])
                ua = float(row[col_map.get('ua', 2)])

                # p_mw: use column if present, otherwise compute
                if 'p_mw' in col_map and len(row) > col_map['p_mw']:
                    try:
                        p_mw = float(row[col_map['p_mw']])
                    except (ValueError, IndexError):
                        p_mw = (mv * ua) / 1_000_000.0
                else:
                    p_mw = (mv * ua) / 1_000_000.0

                # interval_ms (CCS mode)
                interval_ms = None
                if 'interval_ms' in col_map and len(row) > col_map['interval_ms']:
                    try:
                        interval_ms = int(row[col_map['interval_ms']])
                    except (ValueError, IndexError):
                        pass

                samples.append(PowerSample(ms=ms, mv=mv, ua=ua, p_mw=p_mw, interval_ms=interval_ms))
            except (ValueError, IndexError):
                continue

    return samples, summary


def parse_rx_log(path: str) -> List[RxEvent]:
    """
    Parse RX log.

    Expected format: ms,event,rssi,addr,mfd
    """
    events = []

    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        reader = csv.reader(fh)
        header_seen = False

        for row in reader:
            if not row:
                continue
            if row[0].startswith('#'):
                continue
            if row[0].lower() == 'ms':
                header_seen = True
                continue

            try:
                ms = float(row[0])
                rssi = int(row[2]) if len(row) > 2 else 0
                mfd = row[4] if len(row) > 4 else ''

                # Extract seq from MFD (e.g., "MF0001" -> 1)
                seq = None
                if mfd.startswith('MF'):
                    try:
                        seq = int(mfd[2:], 16)
                    except ValueError:
                        pass

                events.append(RxEvent(ms=ms, rssi=rssi, mfd=mfd, seq=seq))
            except (ValueError, IndexError):
                continue

    return events


def load_ccs_session(session_path: str) -> List[Tuple[int, int]]:
    """
    Load CCS session definition.

    Returns:
        List of (timestamp_ms, interval_ms) tuples
    """
    intervals = []

    with open(session_path, 'r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ts_ms = int(row['timestamp_ms'])
            interval_ms = int(row['interval_ms'])
            intervals.append((ts_ms, interval_ms))

    return intervals


# =============================================================================
# Analysis Functions
# =============================================================================
def compute_power_metrics(samples: List[PowerSample], summary: Dict, p_off_mw: float = 22.1) -> Dict:
    """
    Compute power metrics from samples.
    """
    if not samples:
        return {}

    # Duration
    duration_ms = samples[-1].ms - samples[0].ms

    # Energy integration
    total_energy_mj = 0.0
    for i in range(1, len(samples)):
        dt_s = (samples[i].ms - samples[i-1].ms) / 1000.0
        if dt_s > 0:
            total_energy_mj += samples[i].p_mw * dt_s

    # Average current and power
    avg_power_mw = total_energy_mj / (duration_ms / 1000.0) if duration_ms > 0 else 0
    avg_current_ma = avg_power_mw / 3.3 if avg_power_mw > 0 else 0  # Assuming 3.3V

    # Interval distribution (CCS mode)
    interval_dist = {}
    for s in samples:
        if s.interval_ms is not None:
            interval_dist[s.interval_ms] = interval_dist.get(s.interval_ms, 0) + 1

    return {
        'duration_ms': duration_ms,
        'total_energy_mj': total_energy_mj,
        'avg_power_mw': avg_power_mw,
        'avg_current_ma': avg_current_ma,
        'interval_distribution': interval_dist,
    }


def compute_tl_and_pout(
    rx_events: List[RxEvent],
    interval_changes: List[Tuple[int, int]],  # (timestamp_ms, new_interval_ms)
    tau_values: List[float] = TAU_VALUES_S
) -> Tuple[List[float], Dict[float, float]]:
    """
    Compute TL (Time-to-first-Receive) and Pout for activity transition events.

    For CCS mode: interval changes mark potential "activity transitions"
    For FIXED mode: use synthetic events or skip TL calculation

    Returns:
        tl_values_ms: List of TL values in ms
        pout: Dict mapping tau (s) to Pout probability
    """
    tl_values = []

    if not interval_changes or not rx_events:
        # No events to analyze
        return [], {tau: 0.0 for tau in tau_values}

    # For each interval change, find time to first RX after the change
    rx_times = sorted([e.ms for e in rx_events])

    for change_ts, new_interval in interval_changes:
        # Find first RX after this change
        tl = None
        for rx_ts in rx_times:
            if rx_ts > change_ts:
                tl = rx_ts - change_ts
                break

        if tl is not None:
            tl_values.append(tl)
        else:
            # No RX found after this event - count as infinite TL
            tl_values.append(float('inf'))

    # Compute Pout for each tau
    pout = {}
    for tau in tau_values:
        tau_ms = tau * 1000.0
        violations = sum(1 for tl in tl_values if tl > tau_ms)
        pout[tau] = violations / len(tl_values) if tl_values else 0.0

    return tl_values, pout


def compute_pdr(rx_events: List[RxEvent], adv_count: int) -> Tuple[int, int, float]:
    """
    Compute PDR metrics.

    Returns:
        rx_count: Raw RX count
        rx_unique: Unique seq count
        pdr: PDR value (clipped to 1.0)
    """
    rx_count = len(rx_events)

    # Count unique sequences
    seen_seq = set()
    for e in rx_events:
        if e.seq is not None:
            seen_seq.add(e.seq)
    rx_unique = len(seen_seq) if seen_seq else rx_count

    # PDR
    pdr = min(rx_unique / adv_count, 1.0) if adv_count > 0 else 0.0

    return rx_count, rx_unique, pdr


# =============================================================================
# Trial Processing
# =============================================================================
def process_trial(
    pwr_path: str,
    rx_path: str,
    condition: str,
    environment: str,
    trial_id: str,
    ccs_session_path: Optional[str] = None,
    p_off_mw: float = 22.1
) -> TrialResult:
    """
    Process a single trial.
    """
    result = TrialResult(
        trial_id=trial_id,
        condition=condition,
        environment=environment
    )

    # Parse power log
    pwr_samples, pwr_summary = parse_power_log(pwr_path)
    power_metrics = compute_power_metrics(pwr_samples, pwr_summary, p_off_mw)

    result.duration_ms = power_metrics.get('duration_ms', 0)
    result.total_energy_mj = power_metrics.get('total_energy_mj', 0)
    result.avg_power_mw = power_metrics.get('avg_power_mw', 0)
    result.avg_current_ma = power_metrics.get('avg_current_ma', 0)
    result.interval_distribution = power_metrics.get('interval_distribution', {})
    result.adv_count = pwr_summary.get('adv_count', 0)

    # Estimate adv_count from duration if not in summary
    if result.adv_count == 0 and result.duration_ms > 0:
        if condition == 'FIXED100':
            result.adv_count = int(result.duration_ms / 100)
        elif condition == 'FIXED2000':
            result.adv_count = int(result.duration_ms / 2000)
        elif condition == 'CCS':
            # Estimate from interval distribution
            total_time = sum(result.interval_distribution.values())
            if total_time > 0:
                weighted_adv = sum(
                    count / (interval / 1000.0)  # adv per second for this interval
                    for interval, count in result.interval_distribution.items()
                )
                result.adv_count = int(weighted_adv)

    # Parse RX log
    rx_events = parse_rx_log(rx_path) if os.path.exists(rx_path) else []
    result.rx_count, result.rx_unique, result.pdr = compute_pdr(rx_events, result.adv_count)

    # Compute TL and Pout
    # For CCS mode, detect interval changes from power log
    interval_changes = []
    if condition == 'CCS' and pwr_samples:
        prev_interval = None
        for s in pwr_samples:
            if s.interval_ms is not None and s.interval_ms != prev_interval:
                if prev_interval is not None:  # Skip first
                    interval_changes.append((int(s.ms), s.interval_ms))
                prev_interval = s.interval_ms

    # For FIXED modes, create synthetic events at regular intervals for TL analysis
    elif condition in ('FIXED100', 'FIXED2000') and result.duration_ms > 0:
        # Create events every 60 seconds (simulating activity checks)
        interval = 60000  # 60s
        for t in range(int(interval), int(result.duration_ms), int(interval)):
            interval_changes.append((t, 100 if condition == 'FIXED100' else 2000))

    if interval_changes:
        tl_values, pout = compute_tl_and_pout(rx_events, interval_changes)
        result.tl_values_ms = [tl for tl in tl_values if tl != float('inf')]

        if result.tl_values_ms:
            sorted_tl = sorted(result.tl_values_ms)
            result.tl_p50_ms = sorted_tl[len(sorted_tl) // 2]
            result.tl_p95_ms = sorted_tl[int(len(sorted_tl) * 0.95)]

        result.pout = pout

    return result


def process_experiment(
    data_dir: str,
    p_off_mw: float = 22.1,
    session_manifest_path: Optional[str] = None
) -> List[TrialResult]:
    """
    Process all trials in the experiment directory.
    """
    results = []

    # Find all environments (E1, E2)
    for env_dir in sorted(glob.glob(os.path.join(data_dir, 'E*'))):
        environment = os.path.basename(env_dir)

        # Find all conditions
        for cond_dir in sorted(glob.glob(os.path.join(env_dir, '*'))):
            condition = os.path.basename(cond_dir)
            if condition not in ('FIXED100', 'FIXED2000', 'CCS'):
                continue

            # Find power logs
            for pwr_file in sorted(glob.glob(os.path.join(cond_dir, 'pwr_*.csv'))):
                trial_id = os.path.basename(pwr_file).replace('pwr_', '').replace('.csv', '')
                rx_file = os.path.join(cond_dir, f'rx_{trial_id}.csv')

                result = process_trial(
                    pwr_path=pwr_file,
                    rx_path=rx_file,
                    condition=condition,
                    environment=environment,
                    trial_id=trial_id,
                    p_off_mw=p_off_mw
                )
                results.append(result)

    return results


def summarize_by_condition(results: List[TrialResult]) -> List[ConditionSummary]:
    """
    Summarize results by condition and environment.
    """
    # Group by (condition, environment)
    groups: Dict[Tuple[str, str], List[TrialResult]] = {}
    for r in results:
        key = (r.condition, r.environment)
        groups.setdefault(key, []).append(r)

    # Compute summaries
    summaries = []
    baseline_energy = {}  # environment -> FIXED100 energy mean

    for (condition, environment), trials in sorted(groups.items()):
        summary = ConditionSummary(
            condition=condition,
            environment=environment,
            n_trials=len(trials)
        )

        # Power metrics
        currents = [t.avg_current_ma for t in trials if t.avg_current_ma > 0]
        energies = [t.total_energy_mj for t in trials if t.total_energy_mj > 0]

        if currents:
            summary.avg_current_ma_mean = stats.mean(currents)
            summary.avg_current_ma_std = stats.pstdev(currents) if len(currents) > 1 else 0

        if energies:
            summary.total_energy_mj_mean = stats.mean(energies)
            summary.total_energy_mj_std = stats.pstdev(energies) if len(energies) > 1 else 0

        # QoS metrics
        tl_p50s = [t.tl_p50_ms for t in trials if t.tl_p50_ms > 0]
        tl_p95s = [t.tl_p95_ms for t in trials if t.tl_p95_ms > 0]
        pout_1s = [t.pout.get(1.0, 0) for t in trials]
        pout_2s = [t.pout.get(2.0, 0) for t in trials]
        pout_3s = [t.pout.get(3.0, 0) for t in trials]
        pdrs = [t.pdr for t in trials if t.pdr > 0]

        if tl_p50s:
            summary.tl_p50_mean = stats.mean(tl_p50s)
        if tl_p95s:
            summary.tl_p95_mean = stats.mean(tl_p95s)
        if pout_1s:
            summary.pout_1s_mean = stats.mean(pout_1s)
        if pout_2s:
            summary.pout_2s_mean = stats.mean(pout_2s)
        if pout_3s:
            summary.pout_3s_mean = stats.mean(pout_3s)
        if pdrs:
            summary.pdr_mean = stats.mean(pdrs)

        # Store baseline for energy saving calculation
        if condition == 'FIXED100' and summary.avg_current_ma_mean > 0:
            baseline_energy[environment] = summary.avg_current_ma_mean

        summaries.append(summary)

    # Calculate energy saving vs FIXED100
    for summary in summaries:
        baseline = baseline_energy.get(summary.environment, 0)
        if baseline > 0 and summary.avg_current_ma_mean > 0:
            summary.energy_saving_pct = (1 - summary.avg_current_ma_mean / baseline) * 100

    return summaries


# =============================================================================
# Output
# =============================================================================
def generate_report(summaries: List[ConditionSummary], results: List[TrialResult]) -> str:
    """
    Generate markdown report.
    """
    lines = []
    lines.append("# CCS Experiment Results")
    lines.append("")
    lines.append(f"Total trials: {len(results)}")
    lines.append("")

    # Summary table
    lines.append("## Summary by Condition")
    lines.append("")
    lines.append("| Env | Condition | N | Avg Current (mA) | Energy Saving | TL p50 (ms) | TL p95 (ms) | Pout(2s) | PDR |")
    lines.append("|-----|-----------|---|------------------|---------------|-------------|-------------|----------|-----|")

    for s in summaries:
        lines.append(
            f"| {s.environment} | {s.condition} | {s.n_trials} | "
            f"{s.avg_current_ma_mean:.2f} ± {s.avg_current_ma_std:.2f} | "
            f"{s.energy_saving_pct:+.1f}% | "
            f"{s.tl_p50_mean:.1f} | {s.tl_p95_mean:.1f} | "
            f"{s.pout_2s_mean*100:.1f}% | {s.pdr_mean:.3f} |"
        )

    lines.append("")

    # Pout detail table
    lines.append("## Pout Detail")
    lines.append("")
    lines.append("| Env | Condition | Pout(1s) | Pout(2s) | Pout(3s) |")
    lines.append("|-----|-----------|----------|----------|----------|")

    for s in summaries:
        lines.append(
            f"| {s.environment} | {s.condition} | "
            f"{s.pout_1s_mean*100:.2f}% | {s.pout_2s_mean*100:.2f}% | {s.pout_3s_mean*100:.2f}% |"
        )

    lines.append("")

    # Per-trial detail
    lines.append("## Per-Trial Results")
    lines.append("")
    lines.append("| Trial | Env | Cond | Duration (s) | Avg mA | Energy (mJ) | RX | PDR | TL p50 | TL p95 |")
    lines.append("|-------|-----|------|--------------|--------|-------------|-----|-----|--------|--------|")

    for r in results:
        lines.append(
            f"| {r.trial_id} | {r.environment} | {r.condition} | "
            f"{r.duration_ms/1000:.1f} | {r.avg_current_ma:.2f} | "
            f"{r.total_energy_mj:.1f} | {r.rx_unique} | {r.pdr:.3f} | "
            f"{r.tl_p50_ms:.0f} | {r.tl_p95_ms:.0f} |"
        )

    return "\n".join(lines)


def generate_json(summaries: List[ConditionSummary], results: List[TrialResult]) -> str:
    """
    Generate JSON output for further processing.
    """
    output = {
        'summaries': [
            {
                'condition': s.condition,
                'environment': s.environment,
                'n_trials': s.n_trials,
                'avg_current_ma': {'mean': s.avg_current_ma_mean, 'std': s.avg_current_ma_std},
                'energy_saving_pct': s.energy_saving_pct,
                'tl_p50_ms': s.tl_p50_mean,
                'tl_p95_ms': s.tl_p95_mean,
                'pout': {'1s': s.pout_1s_mean, '2s': s.pout_2s_mean, '3s': s.pout_3s_mean},
                'pdr': s.pdr_mean,
            }
            for s in summaries
        ],
        'trials': [
            {
                'trial_id': r.trial_id,
                'condition': r.condition,
                'environment': r.environment,
                'duration_ms': r.duration_ms,
                'avg_current_ma': r.avg_current_ma,
                'total_energy_mj': r.total_energy_mj,
                'adv_count': r.adv_count,
                'rx_unique': r.rx_unique,
                'pdr': r.pdr,
                'tl_p50_ms': r.tl_p50_ms,
                'tl_p95_ms': r.tl_p95_ms,
                'pout': r.pout,
                'interval_distribution': r.interval_distribution,
            }
            for r in results
        ]
    }
    return json.dumps(output, indent=2)


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Analyze CCS experiment data")
    parser.add_argument("--data-dir", required=True, help="Experiment data directory")
    parser.add_argument("--session-manifest", help="CCS session manifest JSON")
    parser.add_argument("--baseline-p-off", type=float, default=22.1, help="Baseline P_off in mW")
    parser.add_argument("--out", help="Output markdown path")
    parser.add_argument("--json-out", help="Output JSON path")
    args = parser.parse_args()

    print(f"Processing experiment data from: {args.data_dir}")

    # Process all trials
    results = process_experiment(args.data_dir, p_off_mw=args.baseline_p_off)
    print(f"Processed {len(results)} trials")

    if not results:
        print("No trials found. Check directory structure.")
        return

    # Summarize
    summaries = summarize_by_condition(results)

    # Generate outputs
    report = generate_report(summaries, results)

    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(report + "\n")
        print(f"Report saved to: {args.out}")
    else:
        print(report)

    if args.json_out:
        json_output = generate_json(summaries, results)
        os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
        with open(args.json_out, 'w', encoding='utf-8') as fh:
            fh.write(json_output + "\n")
        print(f"JSON saved to: {args.json_out}")


if __name__ == "__main__":
    main()
