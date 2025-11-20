#!/usr/bin/env python3
"""
Unit consistency checker for power trial logs.

Invariants:
  I1: E_total_mJ (summary) ≈ ∑ p_mW × dt_s  (±abs_tol_pct)
  I2: E_total_mJ (summary) ≈ mean_p_mW × (ms_total/1000)  (±abs_tol_pct)
  I3: mean_p_mW is in a reasonable mW range (default 1–2000 mW); else warn.

Usage:
  python scripts/check_units.py \
    --data-dir data/実験データ/研究室/1m_on_05 \
    --manifest experiments_manifest.yaml \
    --abs-tol-pct 1.0 \
    --out results/check_units_1m_on_05.md
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics as stats
from typing import Dict, List, Optional, Tuple


def load_manifest(path: Optional[str]) -> Dict[str, dict]:
    if not path:
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
    except Exception:
        return {}
    index: Dict[str, dict] = {}
    for entry in raw.get('trials', []):
        for key in (entry.get('trial_id'), entry.get('path')):
            if key:
                index[os.path.normpath(key)] = entry
    return index


def manifest_lookup(path: str, manifest_index: Dict[str, dict]) -> Optional[dict]:
    if not manifest_index:
        return None
    norm = os.path.normpath(path)
    rel = os.path.normpath(os.path.relpath(path, start=os.getcwd()))
    base = os.path.splitext(os.path.basename(path))[0]
    for key in (norm, rel, base):
        entry = manifest_index.get(key)
        if entry:
            return entry
    return None


def clean_float(token: str) -> Optional[float]:
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


def parse_int_prefix(token: str) -> Optional[int]:
    """TXSD互換: 先頭の連続する数字だけを採用する。"""
    if token is None:
        return None
    m = re.match(r'\s*(\d+)', token)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def parse_diags(path: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Extract E_total_mJ, mean_p_mW, ms_total from summary/diag lines."""
    e_total = None
    mean_p = None
    ms_total = None
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            if not line.startswith('#'):
                continue
            if 'E_total_mJ' in line:
                for chunk in line.split(','):
                    if 'E_total_mJ=' in chunk:
                        val = clean_float(chunk.split('=', 1)[1])
                        if val is not None:
                            e_total = val
                    if 'mean_p_mW=' in chunk:
                        val = clean_float(chunk.split('=', 1)[1])
                        if val is not None:
                            mean_p = val
                    if 'ms_total=' in chunk:
                        val = clean_float(chunk.split('=', 1)[1])
                        if val is not None:
                            ms_total = val
            if line.startswith('# diag') and 'mean_p_mW' in line:
                for chunk in line.split(','):
                    if 'mean_p_mW=' in chunk:
                        val = clean_float(chunk.split('=', 1)[1])
                        if val is not None:
                            mean_p = val
                    if 'ms_total=' in chunk:
                        val = clean_float(chunk.split('=', 1)[1])
                        if val is not None:
                            ms_total = val
    return e_total, mean_p, ms_total


def integrate_file(path: str) -> Tuple[int, float, float, float, float]:
    """
    Returns: samples, energy_mJ, mean_p_mW, ms_total, mean_mv
    """
    samples = 0
    energy_mJ = 0.0
    p_sum = 0.0
    mv_sum = 0.0
    last_ms: Optional[float] = None
    dt_ms_sum = 0.0
    first_ms: Optional[float] = None
    col_ms = 0
    col_mv = 1
    col_ua = 2
    col_pm = 3
    header_set = False
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row or row[0].startswith('#'):
                continue
            if not header_set and any(tok.lower() in ('ms', 'mv', 'mV', 'ua', 'µa', 'p_mw') for tok in row):
                lower = [c.lower() for c in row]
                def idx(name_variants):
                    for i,c in enumerate(lower):
                        if c in name_variants:
                            return i
                    return None
                col_ms = idx({'ms','t','time_ms'}) or col_ms
                col_mv = idx({'mv','mv ','mv'}) or col_mv
                col_ua = idx({'ua','µa','ua '}) or col_ua
                pm_idx = idx({'p_mw'})
                if pm_idx is not None:
                    col_pm = pm_idx
                header_set = True
                continue
            ms_raw = row[col_ms] if len(row) > col_ms else ''
            mv_raw = row[col_mv] if len(row) > col_mv else ''
            ua_raw = row[col_ua] if len(row) > col_ua else ''
            ms = clean_float(ms_raw)
            mv = parse_int_prefix(mv_raw)
            ua = parse_int_prefix(ua_raw)
            if ms is None or mv is None or ua is None:
                continue
            p_mW = clean_float(row[col_pm]) if len(row) > col_pm else None
            if p_mW is None:
                p_mW = (mv * ua) / 1_000_000.0
            if last_ms is not None:
                dt_ms = ms - last_ms
                if dt_ms >= 0:
                    dt_ms_sum += dt_ms
                    energy_mJ += p_mW * (dt_ms / 1000.0)
            else:
                first_ms = ms
            last_ms = ms
            samples += 1
            p_sum += p_mW
            mv_sum += mv
    mean_p_mW = (p_sum / samples) if samples else None
    ms_total = dt_ms_sum if dt_ms_sum > 0 else ((last_ms - first_ms) if (last_ms is not None and first_ms is not None) else 0.0)
    mean_mv = (mv_sum / samples) if samples else None
    return samples, energy_mJ, mean_p_mW or 0.0, ms_total, mean_mv or 0.0


def analyze_trial(path: str, manifest_index: Dict[str, dict], abs_tol_pct: float) -> Optional[dict]:
    entry = manifest_lookup(path, manifest_index)
    if entry and not entry.get('include', True):
        return None
    e_summary, mean_p_summary, ms_total_summary = parse_diags(path)
    samples, e_calc, mean_p_calc, ms_total_calc, mean_mv = integrate_file(path)

    target_e = e_summary if e_summary is not None else e_calc
    target_ms_total = ms_total_summary if ms_total_summary is not None else ms_total_calc
    mean_p_used = mean_p_summary if mean_p_summary is not None else mean_p_calc

    warnings: List[str] = []
    i1_diff_pct = None
    if target_e:
        i1_diff_pct = ((e_calc - target_e) / target_e) * 100.0
        if abs(i1_diff_pct) > abs_tol_pct:
            warnings.append('I1_out_of_range')
    i2_diff_pct = None
    if mean_p_used and target_ms_total:
        # diag の mean_p は µW スケールで記録されている想定（ラベルmWだが値は÷1000する）
        mean_p_effective_mW = mean_p_used / 1000.0
        est_e = mean_p_effective_mW * (target_ms_total / 1000.0)
        if target_e:
            i2_diff_pct = ((est_e - target_e) / target_e) * 100.0
            if abs(i2_diff_pct) > abs_tol_pct:
                warnings.append('I2_out_of_range')
    if mean_p_used < 1.0 or mean_p_used > 2_000_000.0:
        warnings.append('I3_mean_p_range')

    return {
        'file': os.path.basename(path),
        'samples': samples,
        'mean_mv': mean_mv,
        'mean_p_mW': mean_p_used,
        'ms_total_calc': ms_total_calc,
        'ms_total_summary': ms_total_summary,
        'e_calc': e_calc,
        'e_summary': e_summary,
        'i1_diff_pct': i1_diff_pct,
        'i2_diff_pct': i2_diff_pct,
        'warnings': warnings,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True, help='Directory containing trial_*.csv')
    ap.add_argument('--manifest', help='Optional manifest JSON/YAML to include/exclude trials')
    ap.add_argument('--abs-tol-pct', type=float, default=1.0, help='Allowed absolute percent error for I1/I2 (default 1%%)')
    ap.add_argument('--out', help='Optional Markdown output path (prints to stdout if omitted)')
    args = ap.parse_args()

    manifest_index = load_manifest(args.manifest)
    trial_files = sorted([p for p in glob.glob(os.path.join(args.data_dir, 'trial_*.csv'))])
    rows: List[dict] = []
    skipped: List[str] = []
    for path in trial_files:
        entry = manifest_lookup(path, manifest_index)
        if entry and not entry.get('include', True):
            reason = ','.join(entry.get('exclude_reason', [])) or 'manifest_exclude'
            skipped.append(f"{os.path.basename(path)} ({reason})")
            continue
        result = analyze_trial(path, manifest_index, args.abs_tol_pct)
        if result:
            rows.append(result)

    def fmt(v: Optional[float], digits: int = 3) -> str:
        if v is None:
            return ''
        return f"{v:.{digits}f}"

    lines: List[str] = []
    lines.append(f"# Unit check for `{args.data_dir}`")
    lines.append('')
    if skipped:
        lines.append(f"*Skipped by manifest: {', '.join(skipped)}*")
        lines.append('')
    if not rows:
        lines.append('_no trials analyzed_')
    else:
        lines.append("|file|I1 diff %|I2 diff %|mean_p_mW|E_mJ(calc/summary)|ms_total_ms(calc/summary)|warnings|")
        lines.append("|---|---|---|---|---|---|---|")
        for row in rows:
            lines.append(
                f"|{row['file']}|{fmt(row['i1_diff_pct'])}|{fmt(row['i2_diff_pct'])}|"
                f"{fmt(row['mean_p_mW'])}|"
                f"{fmt(row['e_calc'])}/{fmt(row['e_summary'])}|"
                f"{fmt(row['ms_total_calc'])}/{fmt(row['ms_total_summary'])}|"
                f"{','.join(row['warnings'])}|"
            )

        # Aggregate view
        diffs_i1 = [r['i1_diff_pct'] for r in rows if r['i1_diff_pct'] is not None]
        diffs_i2 = [r['i2_diff_pct'] for r in rows if r['i2_diff_pct'] is not None]
        lines.append('')
        if diffs_i1:
            lines.append(f"- I1 diff pct mean {fmt(stats.mean(diffs_i1))} (±{fmt(stats.pstdev(diffs_i1))})")
        if diffs_i2:
            lines.append(f"- I2 diff pct mean {fmt(stats.mean(diffs_i2))} (±{fmt(stats.pstdev(diffs_i2))})")

    output = '\n'.join(lines)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(output + '\n')
    else:
        print(output)


if __name__ == '__main__':
    import glob  # delayed import to keep top import list short
    main()
