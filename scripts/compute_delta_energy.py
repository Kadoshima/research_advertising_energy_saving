#!/usr/bin/env python3
"""
Compute ΔE/adv for ON vs OFF datasets using manifest-backed inclusion.

Usage:
  python scripts/compute_delta_energy.py \
    --on-dir data/実験データ/研究室/1m_on_05 \
    --off-dir data/実験データ/研究室/1m_off_05 \
    --expected-adv-per-trial 600 \
    --manifest experiments_manifest.yaml \
    --out results/delta_energy_1m_on05_off05.md

Notes:
  - Uses #summary lines when available (E_total_mJ, adv_count). Falls back to integrating p_mW if needed.
  - Manifest (JSON/YAML) is used to skip include=false trials.
  - ΔE/adv は (E_on_mean − E_off_mean) / adv_ref 。adv_ref は adv_count の平均が非ゼロならそれを使用、無ければ expected-adv-per-trial。
"""
from __future__ import annotations

import argparse
import csv
import glob
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


def parse_summary_line(path: str) -> Tuple[Optional[float], Optional[int]]:
    """Return (E_total_mJ, adv_count) from #summary if present."""
    e_total = None
    adv_count = None
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                if line.startswith('# summary'):
                    m = re.search(r'E_total_mJ=([0-9.]+)', line)
                    n = re.search(r'adv_count=([0-9]+)', line)
                    if m:
                        try:
                            e_total = float(m.group(1))
                        except ValueError:
                            pass
                    if n:
                        try:
                            adv_count = int(n.group(1))
                        except ValueError:
                            pass
                    break
    except FileNotFoundError:
        pass
    return e_total, adv_count


def integrate_energy(path: str) -> float:
    """Integrate p_mW if available; otherwise compute from mv/uA. Header aliases handled."""
    energy_mJ = 0.0
    last_ms: Optional[float] = None
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
                # header row detected
                lower = [c.lower() for c in row]
                def idx(name_variants):
                    for i,c in enumerate(lower):
                        if c in name_variants:
                            return i
                    return None
                col_ms = idx({'ms','t','time_ms'}) or col_ms
                col_mv = idx({'mv','mv ','mV'.lower()}) or col_mv
                col_ua = idx({'ua','µa','ua '}) or col_ua
                col_pm = idx({'p_mw'}) if idx({'p_mw'}) is not None else col_pm
                header_set = True
                continue
            try:
                ms = float(re.sub(r'[^0-9.+-eE]', '', row[col_ms]))
            except Exception:
                continue
            p_mW = None
            if len(row) > col_pm:
                try:
                    p_mW = float(re.sub(r'[^0-9.+-eE]', '', row[col_pm]))
                except Exception:
                    p_mW = None
            if p_mW is None:
                try:
                    mv = float(re.sub(r'[^0-9.+-eE]', '', row[col_mv]))
                    ua = float(re.sub(r'[^0-9.+-eE]', '', row[col_ua]))
                    p_mW = (mv * ua) / 1_000_000.0
                except Exception:
                    continue
            if last_ms is not None:
                dt_s = (ms - last_ms) / 1000.0
                if dt_s >= 0:
                    energy_mJ += p_mW * dt_s
            last_ms = ms
    return energy_mJ


def collect_trials(dir_path: str, manifest_index: Dict[str, dict]) -> Tuple[List[float], List[int], List[str]]:
    e_totals: List[float] = []
    adv_counts: List[int] = []
    used: List[str] = []
    for f in sorted(glob.glob(os.path.join(dir_path, 'trial_*.csv'))):
        entry = manifest_lookup(f, manifest_index)
        if entry and not entry.get('include', True):
            continue
        _, adv = parse_summary_line(f)
        e_total = integrate_energy(f)
        adv = adv or 0
        e_totals.append(e_total)
        adv_counts.append(adv)
        used.append(os.path.basename(f))
    return e_totals, adv_counts, used


def mean_std(vals: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if not vals:
        return None, None
    if len(vals) == 1:
        return float(vals[0]), 0.0
    return float(stats.mean(vals)), float(stats.pstdev(vals))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--on-dir', action='append', required=True, help='ON dataset directory (repeatable)')
    ap.add_argument('--off-dir', required=True, help='OFF baseline directory')
    ap.add_argument('--expected-adv-per-trial', type=int, default=600, help='Fallback N_adv when adv_count is missing')
    ap.add_argument('--manifest', help='Optional manifest JSON/YAML for inclusion/exclusion')
    ap.add_argument('--out', help='Markdown output path (stdout if omitted)')
    args = ap.parse_args()

    manifest_index = load_manifest(args.manifest)

    lines: List[str] = []
    lines.append('# ΔE/adv Summary')
    lines.append('')
    lines.append(f'- OFF dir: `{args.off_dir}`')
    lines.append(f'- ON dirs: {", ".join(f"`{d}`" for d in args.on_dir)}')
    lines.append('')

    off_e, off_adv, off_used = collect_trials(args.off_dir, manifest_index)
    off_mean, off_std = mean_std(off_e)
    lines.append(f'- OFF trials used: {len(off_used)} ({", ".join(off_used)})')
    if off_mean is not None:
        lines.append(f'- OFF E_total_mJ mean {off_mean:.3f} (±{(off_std or 0):.3f})')
    lines.append('')

    def fmt(val: Optional[float], digits: int = 3) -> str:
        if val is None:
            return ""
        return f"{val:.{digits}f}"

    table = [
        "|set_id|on_trials|E_on_mJ_mean|E_off_mJ_mean|ΔE_mJ|adv_ref|ΔE_per_adv_mJ|ΔE_per_adv_µJ|",
        "|---|---|---|---|---|---|---|---|",
    ]
    for on_dir in args.on_dir:
        set_id = os.path.basename(on_dir.rstrip('/'))
        on_e, on_adv, on_used = collect_trials(on_dir, manifest_index)
        on_mean, on_std = mean_std(on_e)
        adv_ref = (stats.mean([a for a in on_adv if a > 0]) if any(a > 0 for a in on_adv)
                   else args.expected_adv_per_trial)
        delta = None
        delta_per = None
        delta_per_uJ = None
        if on_mean is not None and off_mean is not None:
            delta = on_mean - off_mean
            if adv_ref:
                delta_per = delta / adv_ref
                delta_per_uJ = delta_per * 1000.0
        table.append(
            f"|{set_id}|{len(on_used)}|"
            f"{fmt(on_mean)}|{fmt(off_mean)}|{fmt(delta)}|"
            f"{adv_ref if adv_ref else ''}|"
            f"{fmt(delta_per,6)}|{fmt(delta_per_uJ,2)}|"
        )

    lines.extend(table)
    lines.append('')

    output = '\n'.join(lines)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(output + '\n')
    else:
        print(output)


if __name__ == '__main__':
    main()
