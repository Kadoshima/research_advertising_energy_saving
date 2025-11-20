#!/usr/bin/env python3
"""
Cluster 500ms trial sets by mean_i / E_total_mJ and update manifest.

Rule:
  - Compute median and MAD of mean_i (from #diag mean_i=...).
  - High cluster = mean_i > median + 3*MAD.
  - High cluster trials are marked include=false, cluster_id=500ms_high_current, exclude_reason=high_current_outlier.
  - Others get cluster_id=500ms_nominal.

Usage:
  python scripts/cluster_500ms.py \
    --set-dir data/実験データ/研究室/1m_on_500_03 \
    --manifest experiments_manifest.yaml \
    --out-manifest experiments_manifest.yaml
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics as stats
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def load_manifest(path: str) -> Dict[str, dict]:
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def save_manifest(path: str, data: Dict[str, dict]) -> None:
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def manifest_lookup(manifest: Dict[str, dict], trial_path: str) -> Optional[dict]:
    idx = {os.path.normpath(e['path']): e for e in manifest.get('trials', [])}
    return idx.get(os.path.normpath(trial_path))


def parse_mean_i(path: Path) -> Tuple[Optional[float], Optional[float]]:
    mean_i = None
    e_total = None
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            if line.startswith('# diag') and 'mean_i' in line:
                m = re.search(r'mean_i=([0-9.]+)', line)
                if m:
                    mean_i = float(m.group(1))
            if line.startswith('# summary') and 'E_total_mJ' in line:
                m = re.search(r'E_total_mJ=([0-9.]+)', line)
                if m:
                    e_total = float(m.group(1))
            if mean_i is not None and e_total is not None:
                break
    return mean_i, e_total


def high_cluster_flags(values: List[float]) -> List[bool]:
    if not values:
        return []
    med = stats.median(values)
    mad = stats.median([abs(v - med) for v in values])
    threshold = med + 3 * mad if mad > 0 else med * 1.2
    return [v > threshold for v in values]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--set-dir', action='append', required=True, help='Directory containing 500ms trial_*.csv')
    ap.add_argument('--manifest', required=True, help='Input manifest (JSON/YAML-like with JSON syntax)')
    ap.add_argument('--out-manifest', required=True, help='Output manifest path (can overwrite input)')
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)
    trials = manifest.get('trials', [])
    path_index = {os.path.normpath(e['path']): e for e in trials}

    for set_dir in args.set_dir:
        set_path = Path(set_dir)
        trial_files = sorted(set_path.glob('trial_*.csv'))
        mean_is: List[float] = []
        trial_paths: List[Path] = []
        for f in trial_files:
            m_i, _ = parse_mean_i(f)
            if m_i is None:
                continue
            mean_is.append(m_i)
            trial_paths.append(f)
        flags = high_cluster_flags(mean_is)
        for f, is_high in zip(trial_paths, flags):
            entry = path_index.get(os.path.normpath(str(f)))
            if entry is None:
                # add new entry if missing
                entry = {
                    'trial_id': f"{set_path.name}/{f.name}",
                    'path': str(f),
                    'interval_ms': 500,
                    'set_id': set_path.name,
                    'include': True,
                    'exclude_reason': [],
                    'notes': '',
                    'cluster_id': '500ms_nominal',
                }
                manifest['trials'].append(entry)
                path_index[os.path.normpath(str(f))] = entry
            if is_high:
                entry['include'] = False
                entry['exclude_reason'] = ['high_current_outlier']
                entry['cluster_id'] = '500ms_high_current'
            else:
                if entry.get('cluster_id') in ('500ms_high_current', None):
                    entry['cluster_id'] = '500ms_nominal'
                if entry.get('exclude_reason') == ['high_current_outlier']:
                    entry['exclude_reason'] = []
                if entry.get('include') is False and entry['cluster_id'] == '500ms_nominal':
                    entry['include'] = True

    save_manifest(args.out_manifest, manifest)


if __name__ == '__main__':
    main()
