#!/usr/bin/env python3
"""
Compute ΔE/adv for ON/OFF datasets with flexible filename patterns (1m_on_* and 1m_off_*),
with manifest-based inclusion and optional MAD外れ値除外。OFFは平均電力P_offを計算し、
ON試行の時間長に合わせてスケーリングして差し引く。

Usage:
  python scripts/compute_delta_energy_off.py \
    --on-dir data/実験データ/研究室/row_1120/TX \
    --off-dir data/実験データ/研究室/row_1123_off/TX \
    --expected-adv-per-trial 300
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import statistics as stats
from typing import Dict, Iterable, List, Optional, Tuple


def load_manifest(path: Optional[str]) -> Dict[str, dict]:
    """Load manifest (JSON/YAML compatible). Keys are normpath/relpath/basename for lookup."""
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception:
        return {}

    index: Dict[str, dict] = {}
    for entry in raw.get("trials", []):
        for key in (entry.get("trial_id"), entry.get("path")):
            if not key:
                continue
            norm = os.path.normpath(key)
            index[norm] = entry
    return index


def manifest_lookup(path: str, manifest_index: Dict[str, dict]) -> Optional[dict]:
    """Find manifest entry for a given file path."""
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


def parse_summary(path: str) -> Tuple[float, int, int]:
    """Return (E_total_mJ, adv_count, ms_total) from #summary."""
    E = None
    N = None
    ms = None
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.startswith("# summary"):
                continue
            m = re.search(r"E_total_mJ=([0-9.]+)", line)
            if m:
                E = float(m.group(1))
            m = re.search(r"adv_count=([0-9]+)", line)
            if m:
                N = int(m.group(1))
            m = re.search(r"ms_total=([0-9]+)", line)
            if m:
                ms = int(m.group(1))
            break
    return E or 0.0, N or 0, ms or 0


def load_trials(
    dir_path: str,
    pattern: str,
    manifest_index: Dict[str, dict],
) -> Dict[int, List[Tuple[str, float, int, int]]]:
    """Load trials grouped by interval. Returns {interval_ms: [(path, E_mJ, N_adv, ms_total), ...]}."""
    data: Dict[int, List[Tuple[str, float, int, int]]] = {}
    for f in glob.glob(os.path.join(dir_path, pattern)):
        entry = manifest_lookup(f, manifest_index)
        if entry and not entry.get("include", True):
            continue
        m = re.search(r"1m_(on|off)_(\d+)_", f)
        if not m:
            continue
        interval = int(m.group(2))
        E, N, ms = parse_summary(f)
        data.setdefault(interval, []).append((f, E, N, ms))
    return data


def mean(vals: Iterable[float]) -> float:
    vals = list(vals)
    return float(stats.mean(vals)) if vals else 0.0


def mad(vals: List[float]) -> float:
    """Median absolute deviation."""
    if not vals:
        return 0.0
    med = stats.median(vals)
    return float(stats.median([abs(v - med) for v in vals]))


def filter_by_mad(
    vals: List[float],
    paths: List[str],
    k: Optional[float],
) -> Tuple[List[float], List[str], List[str]]:
    """Return (kept_vals, kept_paths, rejected_paths) applying median±k*MAD if k given."""
    if not vals or k is None or k <= 0:
        return vals, paths, []
    med = stats.median(vals)
    dev = mad(vals)
    if dev == 0:
        return vals, paths, []
    upper = med + k * dev
    kept_vals: List[float] = []
    kept_paths: List[str] = []
    rejected: List[str] = []
    for v, p in zip(vals, paths):
        if v <= upper:
            kept_vals.append(v)
            kept_paths.append(p)
        else:
            rejected.append(p)
    return kept_vals, kept_paths, rejected


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--on-dir", required=True, help="Directory with 1m_on_*_*.csv")
    ap.add_argument("--off-dir", required=True, help="Directory with 1m_off_*_*.csv")
    ap.add_argument("--manifest", help="Optional manifest JSON/YAML path")
    ap.add_argument("--expected-adv-per-trial", type=int, default=300)
    ap.add_argument(
        "--mad-multiplier",
        type=float,
        default=None,
        help="If set, apply median+k*MAD (upper) to P_off_trial for auto exclusion",
    )
    ap.add_argument("--out", help="Optional Markdown output path")
    args = ap.parse_args()

    manifest_index = load_manifest(args.manifest)

    on = load_trials(args.on_dir, "1m_on_*_*.csv", manifest_index)
    off = load_trials(args.off_dir, "1m_off_*_*.csv", manifest_index)

    off_entries = [(p, e, ms) for v in off.values() for (p, e, _, ms) in v if ms > 0]
    off_paths_all = [p for p, _, _ in off_entries]
    off_P = [e / (ms / 1000.0) for _, e, ms in off_entries] if off_entries else []

    off_P_kept, off_paths_kept, off_paths_rejected = filter_by_mad(
        off_P, off_paths_all, args.mad_multiplier
    )
    off_mean_P = mean(off_P_kept) if off_P_kept else 0.0
    off_mean_E = mean([e for _, e, _ in off_entries]) if off_entries else 0.0

    lines: List[str] = []
    lines.append("# ΔE/adv (flex patterns, time-scaled OFF)")
    lines.append("")
    lines.append(f"- ON dir: `{args.on_dir}`")
    lines.append(f"- OFF dir: `{args.off_dir}`")
    if args.manifest:
        lines.append(f"- manifest: `{args.manifest}` (include=false skipped)")
    if args.mad_multiplier:
        lines.append(f"- MAD filter: upper = median + {args.mad_multiplier} * MAD on P_off_trial")
    lines.append(f"- OFF trials kept: {len(off_paths_kept)}/{len(off_paths_all)}")
    if off_paths_rejected:
        lines.append(f"  - rejected (MAD): {', '.join(os.path.basename(p) for p in off_paths_rejected)}")
    lines.append(f"- OFF mean E_total_mJ (raw, pre-MAD): {off_mean_E:.3f}")
    lines.append(f"- OFF mean P_mW (after filters): {off_mean_P:.3f}")
    lines.append("")
    lines.append("|interval_ms|on_trials|P_off_mW|ΔE_per_adv_mJ_mean|ΔE_per_adv_mJ_std|ΔE_per_adv_µJ_mean|")
    lines.append("|---|---|---|---|---|---|")

    for interval in sorted(on):
        trials = on[interval]
        delta_trials: List[float] = []
        for _, E_on, N_adv, ms_on in trials:
            N_ref = N_adv if N_adv > 0 else args.expected_adv_per_trial
            if N_ref <= 0:
                continue
            T_on_s = ms_on / 1000.0
            E_off_same = off_mean_P * T_on_s
            delta_per = (E_on - E_off_same) / N_ref
            if math.isfinite(delta_per):
                delta_trials.append(delta_per)
        if not delta_trials:
            continue
        mean_delta = mean(delta_trials)
        std_delta = float(stats.pstdev(delta_trials)) if len(delta_trials) > 1 else 0.0
        lines.append(
            f"|{interval}|{len(trials)}|{off_mean_P:.3f}|"
            f"{mean_delta:.6f}|{std_delta:.6f}|{mean_delta*1000.0:.2f}|"
        )

    output = "\n".join(lines)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(output + "\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
