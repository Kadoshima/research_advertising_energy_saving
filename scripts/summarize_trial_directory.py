#!/usr/bin/env python3
"""Summarize power + RX trials in a directory.

Usage example:
  python scripts/summarize_trial_directory.py \
      --data-dir data/実験データ/研究室/1m_on_03 \
      --expected-adv-per-trial 600 \
      --out results/summary_1m_on_03.md
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import statistics as stats
from typing import Dict, Iterable, List, Optional, Tuple

Number = Optional[float]

def parse_kv_pairs(line: str) -> Dict[str, float]:
    """Extract key=value pairs from lines like '# diag, foo=1.23, bar=4'."""
    pairs: Dict[str, float] = {}
    for chunk in line.split(','):
        if '=' not in chunk:
            continue
        key, raw = chunk.split('=', 1)
        key = key.strip('# ').strip()
        raw = raw.strip()
        try:
            if raw.startswith('0x'):
                pairs[key] = float(int(raw, 16))
            else:
                pairs[key] = float(raw)
        except ValueError:
            continue
    return pairs

def clean_numeric(token: str) -> Optional[float]:
    token = token.strip()
    if not token:
        return None
    cleaned = re.sub(r'[^0-9.+\-eE]', '', token)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None

def integrate_power_rows(path: str) -> Tuple[int, float, float, float]:
    samples = 0
    energy_mJ = 0.0
    last_ms: Optional[float] = None
    mv_sum = 0.0
    uA_sum = 0.0
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            if row[0].startswith('#'):
                continue
            try:
                ms = clean_numeric(row[0])
                mv = clean_numeric(row[1])
                uA = clean_numeric(row[2])
            except IndexError:
                continue
            if ms is None or mv is None or uA is None:
                continue
            p_mW = None
            if len(row) >= 4:
                p_mW = clean_numeric(row[3])
            if p_mW is None:
                p_mW = (mv * uA) / 1_000_000.0  # mv*uA → mW
            if last_ms is not None:
                dt_s = (ms - last_ms) / 1000.0
                if dt_s >= 0:
                    energy_mJ += p_mW * dt_s
            last_ms = ms
            samples += 1
            mv_sum += mv
            uA_sum += uA
    mean_mv = (mv_sum / samples) if samples else 0.0
    mean_uA = (uA_sum / samples) if samples else 0.0
    return samples, energy_mJ, mean_mv, mean_uA

def summarize_power_file(path: str) -> Dict[str, Number]:
    summary: Dict[str, Number] = {'file': os.path.basename(path)}
    diag = {}
    diag_timing = {}
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            line = line.strip()
            if line.startswith('# summary'):
                diag.update(parse_kv_pairs(line))
            elif line.startswith('# diag') and 'samples=' in line:
                diag.update(parse_kv_pairs(line))
            elif line.startswith('# diag') and 'dt_ms_mean' in line:
                diag_timing.update(parse_kv_pairs(line))
            elif line.startswith('# sys'):
                summary['cpu_mhz'] = parse_kv_pairs(line).get('cpu_mhz')
                summary['wifi_mode'] = parse_kv_pairs(line).get('wifi_mode')
    samples, energy_mJ, mean_mv, mean_uA = integrate_power_rows(path)
    summary['samples'] = diag.get('samples') or samples
    summary['rate_hz'] = diag.get('rate_hz')
    summary['mean_v'] = diag.get('mean_v') or (mean_mv / 1000.0)
    summary['mean_i_mA'] = diag.get('mean_i') or (mean_uA / 1000.0)
    summary['mean_p_mW'] = diag.get('mean_p_mW')
    summary['dt_ms_mean'] = diag_timing.get('dt_ms_mean')
    summary['dt_ms_std'] = diag_timing.get('dt_ms_std')
    summary['parse_drop'] = diag_timing.get('parse_drop')
    summary['ms_total'] = diag.get('ms_total')
    summary['adv_count'] = diag.get('adv_count')
    if energy_mJ <= 0 and diag.get('E_total_mJ'):
        energy_mJ = diag['E_total_mJ']
    summary['E_total_mJ'] = energy_mJ
    adv = summary.get('adv_count') or 0
    summary['E_per_adv_uJ'] = (energy_mJ * 1000.0 / adv) if adv else None
    summary['warnings'] = []
    if samples == 0:
        summary['warnings'].append('no_samples')
    if summary.get('parse_drop'):
        summary['warnings'].append('parse_drop>0')
    return summary

def summarize_rx_file(path: str, expected_adv: int) -> Dict[str, Number]:
    recv = 0
    rssis: List[int] = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        for row in reader:
            if not row:
                continue
            recv += 1
            try:
                rssis.append(int(float(row[2])))
            except (ValueError, IndexError):
                continue
    median_rssi = stats.median(rssis) if rssis else None
    pdr = (recv / expected_adv) if expected_adv else None
    return {
        'file': os.path.basename(path),
        'rx_count': recv,
        'pdr': pdr,
        'median_rssi': median_rssi,
    }

def mean_std(values: Iterable[float]) -> Tuple[Optional[float], Optional[float]]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None, None
    if len(vals) == 1:
        return vals[0], 0.0
    return float(stats.mean(vals)), float(stats.pstdev(vals))

def render_table(rows: List[Dict[str, Number]]) -> str:
    if not rows:
        return '_no files found_'
    header = "|file|samples|rate_hz|adv_count|E_total_mJ|E/adv_uJ|parse_drop|warnings|"
    sep = "|---|---|---|---|---|---|---|---|"
    lines = [header, sep]
    for row in rows:
        warnings = ','.join(row.get('warnings', [])) if row.get('warnings') else ''
        lines.append(
            f"|{row['file']}|{row.get('samples','')}|{row.get('rate_hz','')}|"
            f"{row.get('adv_count','')}|{row.get('E_total_mJ','')}|{row.get('E_per_adv_uJ','')}|"
            f"{row.get('parse_drop','')}|{warnings}|")
    return '\n'.join(lines)

def render_rx_table(rows: List[Dict[str, Number]]) -> str:
    if not rows:
        return '_no RX files found_'
    header = "|file|rx_count|PDR|median RSSI|"
    sep = "|---|---|---|---|"
    lines = [header, sep]
    for row in rows:
        lines.append(
            f"|{row['file']}|{row['rx_count']}|"
            f"{row.get('pdr','')}|{row.get('median_rssi','')}|")
    return '\n'.join(lines)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--expected-adv-per-trial', type=int, default=600)
    ap.add_argument('--out', help='Optional Markdown output path (defaults to <data-dir>/summary.md)')
    args = ap.parse_args()

    power_files = sorted(glob.glob(os.path.join(args.data_dir, 'trial_*.csv')))
    rx_files = sorted(glob.glob(os.path.join(args.data_dir, 'rx_trial_*.csv')))

    power_rows = [summarize_power_file(p) for p in power_files]
    rx_rows = [summarize_rx_file(p, args.expected_adv_per_trial) for p in rx_files]

    def collect(key: str) -> List[float]:
        vals = []
        for row in power_rows:
            val = row.get(key)
            if isinstance(val, (int, float)):
                vals.append(float(val))
        return vals

    e_mean, e_std = mean_std(collect('E_total_mJ'))
    adv_mean, adv_std = mean_std([row.get('adv_count') for row in power_rows if row.get('adv_count')])
    pdr_mean, pdr_std = mean_std([row.get('pdr') for row in rx_rows if row.get('pdr')])

    lines: List[str] = []
    lines.append(f"# Summary for `{args.data_dir}`")
    lines.append('')
    lines.append('## Power trials')
    lines.append(render_table(power_rows))
    lines.append('')
    if e_mean is not None:
        lines.append(f"- E_total_mJ mean {e_mean:.3f} (±{(e_std or 0):.3f})")
    if adv_mean is not None:
        lines.append(f"- adv_count mean {adv_mean:.1f}")
    lines.append('')
    lines.append('## RX trials')
    lines.append(render_rx_table(rx_rows))
    lines.append('')
    if pdr_mean is not None:
        lines.append(f"- PDR mean {pdr_mean:.3f} (±{(pdr_std or 0):.3f})")
    lines.append('')

    output = '\n'.join(lines)
    out_path = args.out or os.path.join(args.data_dir, 'summary.md')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(output)
    if not args.out:
        print(output)

if __name__ == '__main__':
    main()
