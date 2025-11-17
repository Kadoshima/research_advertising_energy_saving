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

def summarize_rx_file(path: str, expected_adv: int, adv_interval_ms: int) -> Dict[str, Number]:
    recv = 0
    rssis: List[int] = []
    # TL/Pout用: seqごとの最初の到達時刻
    seq_first_ms: Dict[int, int] = {}
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        for row in reader:
            if not row:
                continue
            recv += 1
            try:
                ms = int(float(row[0]))
            except (ValueError, IndexError):
                ms = None
            # RSSIは全ADVで集計
            try:
                rssis.append(int(float(row[2])))
            except (ValueError, IndexError):
                pass
            # TL/Poutは ADV イベントのみを対象にする
            try:
                event = row[1]
                mfd = row[4]
            except IndexError:
                continue
            if event != 'ADV':
                continue
            if not (mfd.startswith('MF') and len(mfd) >= 6):
                continue
            try:
                seq = int(mfd[2:6], 16)
            except ValueError:
                continue
            if ms is None:
                continue
            prev = seq_first_ms.get(seq)
            if prev is None or ms < prev:
                seq_first_ms[seq] = ms
    median_rssi = stats.median(rssis) if rssis else None
    pdr = (recv / expected_adv) if expected_adv else None
    uniq_adv = len(seq_first_ms)

    # TL / Pout(τ)計算
    tl_vals: List[float] = []
    pout_1s = pout_2s = pout_3s = None
    tl_p95 = None
    if uniq_adv > 0 and adv_interval_ms > 0:
        min_seq = min(seq_first_ms.keys())
        for seq, ms in seq_first_ms.items():
            k = seq - min_seq
            if k < 0:
                continue
            expected_ms = k * adv_interval_ms
            tl = ms - expected_ms
            if tl >= 0:
                tl_vals.append(float(tl))
        if tl_vals:
            tl_vals.sort()
            idx = int(0.95 * (len(tl_vals) - 1))
            tl_p95 = tl_vals[idx]
            def frac_over(th_ms: float) -> float:
                over = sum(1 for v in tl_vals if v > th_ms)
                return over / len(tl_vals)
            pout_1s = frac_over(1000.0)
            pout_2s = frac_over(2000.0)
            pout_3s = frac_over(3000.0)

    return {
        'file': os.path.basename(path),
        'rx_count': recv,
        'pdr': pdr,
        'median_rssi': median_rssi,
        'uniq_adv': uniq_adv,
        'tl_p95_ms': tl_p95,
        'pout_1s': pout_1s,
        'pout_2s': pout_2s,
        'pout_3s': pout_3s,
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
    header = "|file|rx_count|PDR|median RSSI|uniq_adv|TL_p95_ms|Pout(1s)|Pout(2s)|Pout(3s)|"
    sep = "|---|---|---|---|---|---|---|---|---|"
    lines = [header, sep]
    for row in rows:
        lines.append(
            f"|{row['file']}|{row['rx_count']}|"
            f"{row.get('pdr','')}|{row.get('median_rssi','')}|"
            f"{row.get('uniq_adv','')}|{row.get('tl_p95_ms','')}|"
            f"{row.get('pout_1s','')}|{row.get('pout_2s','')}|{row.get('pout_3s','')}|")
    return '\n'.join(lines)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--expected-adv-per-trial', type=int, default=600)
    ap.add_argument('--out', help='Optional Markdown output path (defaults to <data-dir>/summary.md)')
    ap.add_argument('--adv-interval-ms', type=int, default=100, help='Expected advertisement interval in milliseconds (for TL/Pout).')
    args = ap.parse_args()

    power_files = sorted(glob.glob(os.path.join(args.data_dir, 'trial_*.csv')))
    rx_files = sorted(glob.glob(os.path.join(args.data_dir, 'rx_trial_*.csv')))

    power_rows = [summarize_power_file(p) for p in power_files]
    rx_rows = [summarize_rx_file(p, args.expected_adv_per_trial, args.adv_interval_ms) for p in rx_files]

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
    pout1_mean, pout1_std = mean_std([row.get('pout_1s') for row in rx_rows if row.get('pout_1s') is not None])
    pout2_mean, pout2_std = mean_std([row.get('pout_2s') for row in rx_rows if row.get('pout_2s') is not None])
    pout3_mean, pout3_std = mean_std([row.get('pout_3s') for row in rx_rows if row.get('pout_3s') is not None])

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
    if pout1_mean is not None:
        lines.append(f"- Pout(1s) mean {pout1_mean:.3f} (±{(pout1_std or 0):.3f})")
    if pout2_mean is not None:
        lines.append(f"- Pout(2s) mean {pout2_mean:.3f} (±{(pout2_std or 0):.3f})")
    if pout3_mean is not None:
        lines.append(f"- Pout(3s) mean {pout3_mean:.3f} (±{(pout3_std or 0):.3f})")
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
