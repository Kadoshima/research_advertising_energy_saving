#!/usr/bin/env python3
"""
Compute power and PDR summaries from trial logs.

Usage (from repo root):
  python scripts/compute_power_and_pdr.py \
    --data-dir data/実験データ/研究室/1m_ad \
    --expected-adv-per-trial 600 \
    --out results/summary_1m_E2_100ms.md

Optional ΔE (when OFF dataset is available):
  python scripts/compute_power_and_pdr.py \
    --data-dir data/実験データ/研究室/1m_ad_on \
    --off-dir  data/実験データ/研究室/1m_ad_off \
    --expected-adv-per-trial 600 \
    --out results/summary_1m_E2_100ms_deltaE.md

Notes:
- Expects power files like trial_XXX.csv that include a '# summary' line with
  ms_total, adv_count, E_total_mJ, E_per_adv_uJ. If the summary is missing,
  will attempt to integrate V×I in the file body (mW × s → mJ).
- Expects RX files like rx_trial_XXX.csv with header 'ms,event,rssi,addr,mfd'.
- Stdlib only; Python 3.8+.
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import statistics as stats
from typing import List, Tuple, Optional


def read_power_summaries(dir_path: str) -> Tuple[List[float], List[float], List[int]]:
    pattern = os.path.join(dir_path, 'trial_*.csv')
    e_totals: List[float] = []
    e_per_adv: List[float] = []
    adv_counts: List[int] = []
    for f in sorted(glob.glob(pattern)):
        E_total_mJ = None
        E_per_adv_uJ = None
        adv_count = None
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                for line in fh:
                    if line.startswith('# summary'):
                        m = re.search(r'E_total_mJ=([0-9.]+)', line)
                        u = re.search(r'E_per_adv_uJ=([0-9.]+)', line)
                        n = re.search(r'adv_count=([0-9]+)', line)
                        if m:
                            E_total_mJ = float(m.group(1))
                        if u:
                            E_per_adv_uJ = float(u.group(1))
                        if n:
                            adv_count = int(n.group(1))
                        break
        except FileNotFoundError:
            continue

        # Fallback: integrate V×I if no summary found
        if E_total_mJ is None or E_per_adv_uJ is None:
            try:
                with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                    r = csv.reader(fh)
                    header = next(r, None)
                    last_ms = None
                    acc_mJ = 0.0
                    for row in r:
                        if not row or row[0].startswith('#'):
                            continue
                        try:
                            ms = int(float(row[0]))
                            v = float(row[1])
                            i = float(row[2])  # mA
                        except Exception:
                            continue
                        if last_ms is not None:
                            dt = (ms - last_ms) / 1000.0
                            p_mW = v * i
                            acc_mJ += p_mW * dt
                        last_ms = ms
                    E_total_mJ = acc_mJ
                    adv_count = adv_count or 0
                    E_per_adv_uJ = (acc_mJ * 1000.0 / adv_count) if adv_count else 0.0
            except Exception:
                pass

        if E_total_mJ is not None:
            e_totals.append(E_total_mJ)
        if E_per_adv_uJ is not None:
            e_per_adv.append(E_per_adv_uJ)
        if adv_count is not None:
            adv_counts.append(adv_count)
    return e_totals, e_per_adv, adv_counts


def read_rx_pdr(dir_path: str, expected_adv_per_trial: int) -> Tuple[List[int], List[float], List[int]]:
    pattern = os.path.join(dir_path, 'rx_trial_*.csv')
    recv_counts: List[int] = []
    pdrs: List[float] = []
    rssis_all: List[int] = []
    for f in sorted(glob.glob(pattern)):
        recv = 0
        rssis: List[int] = []
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                r = csv.reader(fh)
                header = next(r, None)
                for row in r:
                    if not row:
                        continue
                    recv += 1
                    try:
                        rssis.append(int(float(row[2])))
                    except Exception:
                        pass
        except FileNotFoundError:
            continue
        recv_counts.append(recv)
        pdrs.append((recv / expected_adv_per_trial) if expected_adv_per_trial else 0.0)
        rssis_all.extend(rssis)
    return recv_counts, pdrs, rssis_all


def fmt_mean_std(vals: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if not vals:
        return None, None
    return float(stats.mean(vals)), float(stats.pstdev(vals))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True, help='Directory with trial_*.csv and rx_trial_*.csv')
    ap.add_argument('--off-dir', help='OFF dataset directory for ΔE computation (trial_*.csv)')
    ap.add_argument('--expected-adv-per-trial', type=int, default=600, help='Expected advertisements per 60s trial (default: 600)')
    ap.add_argument('--out', help='Write Markdown summary to this path (prints to stdout if omitted)')
    args = ap.parse_args()

    e_totals, e_per_adv, adv_counts = read_power_summaries(args.data_dir)
    recv_counts, pdrs, rssis_all = read_rx_pdr(args.data_dir, args.expected_adv_per_trial)

    e_mean, e_std = fmt_mean_std(e_totals)
    u_mean, u_std = fmt_mean_std(e_per_adv)
    pdr_mean, pdr_std = fmt_mean_std(pdrs)
    rssi_median = int(stats.median(rssis_all)) if rssis_all else None

    off_mean = None
    if args.off_dir:
        off_e, _, _ = read_power_summaries(args.off_dir)
        off_mean, _ = fmt_mean_std(off_e)

    lines = []
    lines.append('# Summary')
    lines.append('')
    lines.append(f'- Data dir: `{args.data_dir}`')
    if args.off_dir:
        lines.append(f'- OFF dir: `{args.off_dir}`')
    lines.append('- Trials:')
    lines.append(f'  - power files: {len(e_totals)}')
    lines.append(f'  - rx files: {len(recv_counts)}')
    lines.append('')
    if e_mean is not None:
        lines.append(f'- E_total_mJ mean {e_mean:.3f} (±{(e_std or 0):.3f})')
    if u_mean is not None:
        lines.append(f'- E_per_adv_uJ mean {u_mean:.2f} (±{(u_std or 0):.2f})')
    if pdr_mean is not None:
        lines.append(f'- PDR mean {pdr_mean:.3f} (±{(pdr_std or 0):.3f})')
    if rssi_median is not None:
        lines.append(f'- RSSI median {rssi_median} dBm')
    if off_mean is not None and e_mean is not None:
        delta = e_mean - off_mean
        lines.append(f'- ΔE (mean on − mean off) {delta:.3f} mJ (on={e_mean:.3f}, off={off_mean:.3f})')
    lines.append('')

    out_txt = '\n'.join(lines)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(out_txt + '\n')
    else:
        print(out_txt)


if __name__ == '__main__':
    main()

