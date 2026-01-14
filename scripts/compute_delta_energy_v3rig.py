#!/usr/bin/env python3
"""
Compute DeltaE per adv for the v3 rig recheck dataset.

Usage:
  python3 scripts/compute_delta_energy_v3rig.py \
    --root data/実験データ/研究室/phase0-0_deltae_v3rig_20260114 \
    --out results/phase0-0/phase0-0_deltae_v3rig_2026-01-14.md

Expected layout:
  root/ON_100ms/trial_001_on.csv
  root/ON_500ms/trial_001_on.csv
  root/ON_1000ms/trial_001_on.csv
  root/ON_2000ms/trial_001_on.csv
  root/OFF/trial_001_off.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import statistics as stats
from typing import Dict, List, Optional, Tuple


SUMMARY_RE = re.compile(
    r"ms_total=(?P<ms>[0-9.]+).*?adv_count=(?P<adv>[0-9]+).*?E_total_mJ=(?P<e>[0-9.]+)"
)


def parse_summary_line(path: str) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {"ms_total": None, "adv_count": None, "E_total_mJ": None}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if line.startswith("# summary"):
                    m = SUMMARY_RE.search(line)
                    if m:
                        out["ms_total"] = float(m.group("ms"))
                        out["adv_count"] = float(m.group("adv"))
                        out["E_total_mJ"] = float(m.group("e"))
                    break
    except FileNotFoundError:
        pass
    return out


def _pick_idx(cols: List[str], names: Tuple[str, ...], fallback: int) -> int:
    for name in names:
        if name in cols:
            return cols.index(name)
    return fallback


def integrate_energy(path: str) -> Tuple[Optional[float], Optional[float]]:
    last_ms: Optional[float] = None
    energy_mJ = 0.0
    ms_total: Optional[float] = None

    col_ms = 0
    col_mv = 1
    col_ua = 2
    col_pm = 3
    header_set = False

    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if not header_set and any(tok.lower() in ("ms", "mv", "ua", "p_mw") for tok in row):
                cols = [c.strip().lower() for c in row]
                col_ms = _pick_idx(cols, ("ms", "t", "time_ms"), col_ms)
                col_mv = _pick_idx(cols, ("mv",), col_mv)
                col_ua = _pick_idx(cols, ("ua",), col_ua)
                col_pm = _pick_idx(cols, ("p_mw",), col_pm)
                header_set = True
                continue
            try:
                ms = float(re.sub(r"[^0-9.+-eE]", "", row[col_ms]))
            except Exception:
                continue
            p_mW: Optional[float] = None
            if len(row) > col_pm:
                try:
                    p_mW = float(re.sub(r"[^0-9.+-eE]", "", row[col_pm]))
                except Exception:
                    p_mW = None
            if p_mW is None:
                try:
                    mv = float(re.sub(r"[^0-9.+-eE]", "", row[col_mv]))
                    ua = float(re.sub(r"[^0-9.+-eE]", "", row[col_ua]))
                    p_mW = (mv * ua) / 1_000_000.0
                except Exception:
                    continue
            if last_ms is not None:
                dt_s = (ms - last_ms) / 1000.0
                if dt_s >= 0:
                    energy_mJ += p_mW * dt_s
            last_ms = ms
            ms_total = ms

    return (energy_mJ if ms_total is not None else None), ms_total


def load_trial(path: str) -> Optional[Dict[str, float]]:
    summary = parse_summary_line(path)
    ms_total = summary.get("ms_total")
    adv_count = summary.get("adv_count") or 0.0
    e_total = summary.get("E_total_mJ")

    if ms_total is None or e_total is None:
        e_fallback, ms_fallback = integrate_energy(path)
        if ms_total is None:
            ms_total = ms_fallback
        if e_total is None:
            e_total = e_fallback

    if ms_total is None or e_total is None:
        return None

    return {
        "path": path,
        "ms_total": float(ms_total),
        "adv_count": float(adv_count),
        "E_total_mJ": float(e_total),
    }


def collect_trials(dir_path: str) -> List[Dict[str, float]]:
    trials: List[Dict[str, float]] = []
    for path in sorted(glob.glob(os.path.join(dir_path, "trial_*.csv"))):
        t = load_trial(path)
        if t:
            trials.append(t)
    return trials


def mean_std(vals: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if not vals:
        return None, None
    if len(vals) == 1:
        return float(vals[0]), 0.0
    return float(stats.mean(vals)), float(stats.pstdev(vals))


def fmt(val: Optional[float], digits: int = 3) -> str:
    if val is None:
        return ""
    return f"{val:.{digits}f}"


def parse_intervals(raw: str) -> List[int]:
    vals = []
    for tok in raw.split(","):
        tok = tok.strip()
        if tok:
            vals.append(int(tok))
    return vals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Dataset root (contains ON_* and OFF)")
    ap.add_argument("--intervals", default="100,500,1000,2000", help="Comma-separated intervals")
    ap.add_argument("--out", help="Markdown output path")
    args = ap.parse_args()

    intervals = parse_intervals(args.intervals)
    root = args.root
    off_dir = os.path.join(root, "OFF")

    lines: List[str] = []
    lines.append("# Phase0-0 DeltaE recheck (v3 rig)")
    lines.append("")
    lines.append(f"- root: `{root}`")
    lines.append(f"- off_dir: `{off_dir}`")
    lines.append(f"- intervals: {', '.join(str(i) for i in intervals)}")
    lines.append("")

    off_trials = collect_trials(off_dir)
    off_powers: List[float] = []
    off_energies: List[float] = []
    off_ms: List[float] = []
    for t in off_trials:
        ms_total = t["ms_total"]
        e_total = t["E_total_mJ"]
        if ms_total > 0:
            off_powers.append(e_total / (ms_total / 1000.0))
        off_energies.append(e_total)
        off_ms.append(ms_total)

    off_p_mean, off_p_std = mean_std(off_powers)
    off_e_mean, off_e_std = mean_std(off_energies)
    off_ms_mean, _ = mean_std(off_ms)

    lines.append(f"- OFF trials: {len(off_trials)}")
    if off_p_mean is not None:
        lines.append(
            f"- OFF mean: P_off_mW={fmt(off_p_mean,2)} +/- {fmt(off_p_std,2)}, "
            f"E_total_mJ={fmt(off_e_mean,2)} +/- {fmt(off_e_std,2)}, ms={fmt(off_ms_mean,0)}"
        )
    lines.append("")

    table = [
        "|interval_ms|on_trials|E_on_mJ_mean|E_on_mJ_std|P_off_mW_mean|DeltaE_mJ_mean|DeltaE_mJ_std|adv_mean|DeltaE_per_adv_uJ_mean|DeltaE_per_adv_uJ_std|",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for interval_ms in intervals:
        on_dir = os.path.join(root, f"ON_{interval_ms}ms")
        on_trials = collect_trials(on_dir)
        on_energies: List[float] = []
        on_ms: List[float] = []
        advs: List[float] = []
        deltas: List[float] = []
        delta_per_uJ: List[float] = []

        for t in on_trials:
            ms_total = t["ms_total"]
            e_total = t["E_total_mJ"]
            adv = t["adv_count"]
            if adv <= 0 and interval_ms > 0:
                adv = round(ms_total / interval_ms)
            if adv > 0:
                advs.append(adv)

            on_energies.append(e_total)
            on_ms.append(ms_total)

            if off_p_mean is not None:
                delta_mJ = e_total - off_p_mean * (ms_total / 1000.0)
                deltas.append(delta_mJ)
                if adv > 0:
                    delta_per_uJ.append(delta_mJ * 1000.0 / adv)

        on_mean, on_std = mean_std(on_energies)
        delta_mean, delta_std = mean_std(deltas)
        delta_u_mean, delta_u_std = mean_std(delta_per_uJ)
        adv_mean, _ = mean_std(advs)

        table.append(
            f"|{interval_ms}|{len(on_trials)}|{fmt(on_mean)}|{fmt(on_std)}|"
            f"{fmt(off_p_mean,2)}|{fmt(delta_mean)}|{fmt(delta_std)}|"
            f"{fmt(adv_mean,1)}|{fmt(delta_u_mean,2)}|{fmt(delta_u_std,2)}|"
        )

    lines.extend(table)
    lines.append("")

    output = "\n".join(lines)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(output + "\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
