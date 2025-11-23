#!/usr/bin/env python3
"""
Join TXSD (ON) logs with RX logs to compute PDR. Provides:
- PDR_raw = rx_count_raw / adv_count
- PDR_unique = rx_count_unique / adv_count (seq去重)
- PDR_ms = rx_count_unique / (ms_rx / interval_ms)  # 正式指標、<=1想定
- オプション: それぞれを max=1.0 で clip した値を出力

Assumptions:
  - TXSD files: 1m_on_*_*.csv with #summary (adv_count, ms_total).
  - RX files: same basename under rx-dir; data rows are counted for rx_count.
  - manifest (JSON/YAML) is optional; include=false trials are skipped.

Usage:
  python scripts/compute_pdr_join.py \
    --txsd-dir data/実験データ/研究室/row_1120/TX \
    --rx-dir data/実験データ/研究室/row_1120/RX \
    --manifest experiments_manifest.yaml \
    [--dedup-seq]
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


def parse_tx_summary(path: str) -> Tuple[int, int]:
    adv = 0
    ms = 0
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.startswith("# summary"):
                continue
            m = re.search(r"adv_count=([0-9]+)", line)
            if m:
                adv = int(m.group(1))
            m = re.search(r"ms_total=([0-9]+)", line)
            if m:
                ms = int(m.group(1))
            break
    return adv, ms


def parse_rx(path: str, dedup_seq: bool = False) -> Tuple[int, int, int]:
    """Count data rows (rx_count_raw), optional seq-deduped rows (rx_unique), and ms_total_rx."""
    rx_count = 0
    rx_unique = 0
    seen_seq = set()
    last_ms = 0.0
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            if row[0].startswith("#"):
                continue
            if row[0].lower() == "ms":
                continue
            try:
                ms = float(row[0])
                last_ms = ms
            except Exception:
                continue
            rx_count += 1
            if dedup_seq and len(row) > 4:
                seq = row[4]
                if seq.startswith("MF"):
                    key = seq
                    if key not in seen_seq:
                        seen_seq.add(key)
                        rx_unique += 1
            elif dedup_seq:
                # No seq info; fall back to raw
                rx_unique = rx_count
            else:
                rx_unique = rx_count
    return rx_count, rx_unique, int(last_ms)


def interval_from_name(path: str) -> Optional[int]:
    m = re.search(r"1m_on_(\d+)_", os.path.basename(path))
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--txsd-dir", required=True, help="Directory with TXSD ON logs (1m_on_*_*.csv)")
    ap.add_argument("--rx-dir", required=True, help="Directory with RX logs (matching basenames)")
    ap.add_argument("--manifest", help="Optional manifest JSON/YAML path")
    ap.add_argument("--dedup-seq", action="store_true", help="Count RX by unique seq (mfd) for PDR_unique / PDR_ms")
    ap.add_argument("--clip-pdr", action="store_true", default=True, help="Clip PDR values at 1.0 (applies to PDR_raw/unique/ms)")
    ap.add_argument("--expected-adv-per-trial", type=int, default=300, help="Fallback adv_count if missing")
    ap.add_argument("--out", help="Optional Markdown output path")
    args = ap.parse_args()

    manifest_index = load_manifest(args.manifest)

    tx_files = sorted(glob.glob(os.path.join(args.txsd_dir, "1m_on_*_*.csv")))
    rx_files = {os.path.basename(p): p for p in glob.glob(os.path.join(args.rx_dir, "*"))}

    rows = []
    missing_rx: List[str] = []
    for tx in tx_files:
        entry = manifest_lookup(tx, manifest_index)
        if entry and not entry.get("include", True):
            continue
        base = os.path.basename(tx)
        rx = rx_files.get(base)
        if not rx:
            missing_rx.append(base)
            continue
        adv, ms_on = parse_tx_summary(tx)
        rx_count_raw, rx_count_unique, ms_rx = parse_rx(rx, dedup_seq=args.dedup_seq)
        interval = interval_from_name(tx) or 0
        adv_ref = adv if adv > 0 else args.expected_adv_per_trial
        pdr_raw = (rx_count_raw / adv_ref) if adv_ref > 0 else 0.0
        pdr_unique = (rx_count_unique / adv_ref) if adv_ref > 0 else 0.0
        denom_ms = (ms_rx / interval) if interval > 0 else 0.0
        pdr_ms = (rx_count_unique / denom_ms) if denom_ms > 0 else 0.0
        if args.clip_pdr:
            pdr_raw_clip = min(pdr_raw, 1.0)
            pdr_unique_clip = min(pdr_unique, 1.0)
            pdr_ms_clip = min(pdr_ms, 1.0)
        else:
            pdr_raw_clip = pdr_raw
            pdr_unique_clip = pdr_unique
            pdr_ms_clip = pdr_ms
        rows.append(
            (
                interval,
                base,
                adv_ref,
                rx_count_raw,
                rx_count_unique,
                pdr_raw,
                pdr_unique,
                pdr_ms,
                pdr_raw_clip,
                pdr_unique_clip,
                pdr_ms_clip,
                ms_on,
                ms_rx,
            )
        )

    rows.sort(key=lambda x: (x[0], x[1]))

    lines: List[str] = []
    lines.append("# PDR (TXSD + RX join)")
    lines.append("")
    lines.append(f"- TXSD dir: `{args.txsd_dir}`")
    lines.append(f"- RX dir: `{args.rx_dir}`")
    if args.manifest:
        lines.append(f"- manifest: `{args.manifest}` (include=false skipped)")
    if missing_rx:
        lines.append(f"- missing RX files for {len(missing_rx)} trials: {', '.join(missing_rx)}")
    lines.append("")
    lines.append("|interval_ms|file|adv_count|rx_count_raw|rx_count_unique|PDR_raw|PDR_unique|PDR_ms|PDR_raw_clip|PDR_unique_clip|PDR_ms_clip|ms_on|ms_rx|")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"|{r[0]}|{r[1]}|{r[2]}|{r[3]}|{r[4]}|"
            f"{r[5]:.3f}|{r[6]:.3f}|{r[7]:.3f}|"
            f"{r[8]:.3f}|{r[9]:.3f}|{r[10]:.3f}|{r[11]}|{r[12]}|"
        )

    # interval summary
    lines.append("")
    lines.append("## Interval summary")
    lines.append("|interval_ms|trials|PDR_raw_mean|PDR_raw_std|PDR_unique_mean|PDR_unique_std|PDR_ms_mean|PDR_ms_std|PDR_raw_clip_mean|PDR_unique_clip_mean|PDR_ms_clip_mean|adv_mean|rx_raw_mean|rx_unique_mean|")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    by_interval: Dict[int, List[Tuple[float, float, float, float, float, int, int]]] = {}
    for interval, _, adv_ref, rx_raw, rx_unique, pdr_raw, pdr_unique, pdr_ms, pdr_raw_clip, pdr_unique_clip, pdr_ms_clip, ms_on, ms_rx in rows:
        by_interval.setdefault(interval, []).append((pdr_raw, pdr_unique, pdr_ms, pdr_raw_clip, pdr_unique_clip, pdr_ms_clip, adv_ref, rx_raw, rx_unique))
    for interval in sorted(by_interval):
        vals = by_interval[interval]
        pdr_raws = [v[0] for v in vals]
        pdr_uniques = [v[1] for v in vals]
        pdr_ms_vals = [v[2] for v in vals]
        pdr_raw_clips = [v[3] for v in vals]
        pdr_unique_clips = [v[4] for v in vals]
        pdr_ms_clips = [v[5] for v in vals]
        mean_raw = float(stats.mean(pdr_raws)) if pdr_raws else 0.0
        std_raw = float(stats.pstdev(pdr_raws)) if len(pdr_raws) > 1 else 0.0
        mean_unique = float(stats.mean(pdr_uniques)) if pdr_uniques else 0.0
        std_unique = float(stats.pstdev(pdr_uniques)) if len(pdr_uniques) > 1 else 0.0
        mean_ms = float(stats.mean(pdr_ms_vals)) if pdr_ms_vals else 0.0
        std_ms = float(stats.pstdev(pdr_ms_vals)) if len(pdr_ms_vals) > 1 else 0.0
        mean_raw_clip = float(stats.mean(pdr_raw_clips)) if pdr_raw_clips else 0.0
        mean_unique_clip = float(stats.mean(pdr_unique_clips)) if pdr_unique_clips else 0.0
        mean_ms_clip = float(stats.mean(pdr_ms_clips)) if pdr_ms_clips else 0.0
        adv_mean = float(stats.mean([v[6] for v in vals])) if vals else 0.0
        rx_raw_mean = float(stats.mean([v[7] for v in vals])) if vals else 0.0
        rx_unique_mean = float(stats.mean([v[8] for v in vals])) if vals else 0.0
        lines.append(
            f"|{interval}|{len(vals)}|{mean_raw:.3f}|{std_raw:.3f}|"
            f"{mean_unique:.3f}|{std_unique:.3f}|{mean_ms:.3f}|{std_ms:.3f}|"
            f"{mean_raw_clip:.3f}|{mean_unique_clip:.3f}|{mean_ms_clip:.3f}|"
            f"{adv_mean:.1f}|{rx_raw_mean:.1f}|{rx_unique_mean:.1f}|"
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
