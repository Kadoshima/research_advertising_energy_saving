#!/usr/bin/env python3
"""
Unit check for OFF logs with flexible filename pattern (1m_off_*_.csv).
Parses #summary lines to extract E_total_mJ / ms_total, computes P_off_trial,
and reports stats with manifest-based inclusion and optional MAD outlier表示。
"""
from __future__ import annotations

import argparse
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
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception:
        return {}
    idx: Dict[str, dict] = {}
    for entry in raw.get("trials", []):
        for key in (entry.get("trial_id"), entry.get("path")):
            if not key:
                continue
            idx[os.path.normpath(key)] = entry
    return idx


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


def parse_summary(path: str) -> Tuple[float, int]:
    E = None
    ms = None
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.startswith("# summary"):
                m = re.search(r"E_total_mJ=([0-9.]+)", line)
                if m:
                    E = float(m.group(1))
                m = re.search(r"ms_total=([0-9]+)", line)
                if m:
                    ms = int(m.group(1))
                break
    return E or 0.0, ms or 0


def mad(vals: List[float]) -> float:
    if not vals:
        return 0.0
    med = stats.median(vals)
    return float(stats.median([abs(v - med) for v in vals]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--pattern", default="1m_off_*_*.csv", help="Glob pattern under data-dir")
    ap.add_argument("--manifest", help="Optional manifest JSON/YAML path")
    ap.add_argument(
        "--mad-multiplier",
        type=float,
        default=3.0,
        help="Outlier threshold = median + k*MAD on P_off_trial (set 0/neg to disable)",
    )
    ap.add_argument("--out", help="Optional Markdown output path")
    args = ap.parse_args()

    manifest_index = load_manifest(args.manifest)
    paths_all = sorted(glob.glob(os.path.join(args.data_dir, args.pattern)))

    rows = []
    for p in paths_all:
        entry = manifest_lookup(p, manifest_index)
        if entry and not entry.get("include", True):
            continue
        E, ms = parse_summary(p)
        P = E / (ms / 1000.0) if ms > 0 else 0.0
        rows.append((os.path.basename(p), E, ms, P))

    lines: List[str] = []
    lines.append(f"# OFF check for `{args.data_dir}` (pattern `{args.pattern}`)")
    if args.manifest:
        lines.append(f"- manifest: `{args.manifest}` (include=false skipped)")
    lines.append("")
    if not rows:
        lines.append("_no files matched_")
    else:
        P_vals = [r[3] for r in rows if r[3] > 0]
        med_P = stats.median(P_vals) if P_vals else 0.0
        mad_P = mad(P_vals) if P_vals else 0.0
        upper = med_P + args.mad_multiplier * mad_P if args.mad_multiplier and args.mad_multiplier > 0 else None

        lines.append("|file|E_total_mJ|ms_total|P_off_mW|outlier|")
        lines.append("|---|---|---|---|---|")
        for r in rows:
            is_out = upper is not None and r[3] > upper
            flag = "high_baseline_outlier" if is_out else ""
            lines.append(f"|{r[0]}|{r[1]:.3f}|{r[2]}|{r[3]:.3f}|{flag}|")

        if rows:
            E_vals = [r[1] for r in rows]
            lines.append("")
            lines.append(f"- mean E_total_mJ {stats.mean(E_vals):.3f} (min {min(E_vals):.3f}, max {max(E_vals):.3f})")
            if P_vals:
                lines.append(f"- P_off_mW median {med_P:.3f}, MAD {mad_P:.3f}" + (f", upper={upper:.3f}" if upper is not None else ""))

    output = "\n".join(lines)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(output + "\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
