#!/usr/bin/env python3
"""
Merge summarized runs (per_trial.csv) and regenerate summary_by_condition.csv / summary.md.

Purpose
  - Increase n (repeats) without re-parsing raw RX/TXSD logs.
  - Keep the exact metric definitions used by summarize_d2_run.py.

Inputs
  - One or more directories that contain per_trial.csv (and optionally summary.md).

Outputs (out_dir)
  - per_trial.csv (concatenated, sorted by rx_trial_id)
  - summary_by_condition.csv (mean/std by condition)
  - summary.md (human-readable summary + provenance)
"""

from __future__ import annotations

import argparse
import csv
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


SUMMARY_FIELDS = [
    "condition",
    "n_trials",
    "pout_1s_mean",
    "pout_1s_std",
    "tl_mean_s_mean",
    "tl_mean_s_std",
    "pdr_unique_mean",
    "pdr_unique_std",
    "rx_tag_share100_time_est_mean",
    "rx_tag_share100_time_est_std",
    "avg_power_mW_mean",
    "avg_power_mW_std",
    "adv_count_mean",
    "adv_count_std",
]


def mean_std(xs: List[float]) -> Tuple[float, float]:
    if not xs:
        return 0.0, 0.0
    if len(xs) == 1:
        return xs[0], 0.0
    return statistics.mean(xs), statistics.stdev(xs)


def read_per_trial(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="") as f:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames:
            raise SystemExit(f"empty header: {path}")
        rows = [dict(r) for r in rdr]
        return list(rdr.fieldnames), rows


def f_or_empty(v: str) -> List[float]:
    v = (v or "").strip()
    if not v:
        return []
    return [float(v)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument(
        "--input-dir",
        type=Path,
        action="append",
        required=True,
        help="metrics/* directory that contains per_trial.csv (repeatable)",
    )
    args = ap.parse_args()

    input_dirs: List[Path] = args.input_dir
    per_paths = [d / "per_trial.csv" for d in input_dirs]
    for p in per_paths:
        if not p.exists():
            raise SystemExit(f"missing per_trial.csv: {p}")

    header_ref: List[str] = []
    all_rows: List[Dict[str, str]] = []
    for p in per_paths:
        header, rows = read_per_trial(p)
        if not header_ref:
            header_ref = header
        elif header != header_ref:
            raise SystemExit(f"header mismatch: {p}")
        all_rows.extend(rows)

    # Sort by rx_trial_id if present.
    if "rx_trial_id" in header_ref:
        all_rows.sort(key=lambda r: int((r.get("rx_trial_id") or "0").strip() or "0"))

    args.out_dir.mkdir(parents=True, exist_ok=True)

    per_out = args.out_dir / "per_trial.csv"
    with per_out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header_ref)
        w.writeheader()
        w.writerows(all_rows)

    # Summary by condition (compatible with plot_power_vs_pout.py / thesis tables).
    by_cond: Dict[str, List[Dict[str, str]]] = {}
    for r in all_rows:
        cond = (r.get("condition") or "").strip()
        if not cond:
            continue
        by_cond.setdefault(cond, []).append(r)

    summary_rows: List[Dict[str, object]] = []
    for cond, rows in sorted(by_cond.items()):
        pout_1s_list: List[float] = []
        tl_list: List[float] = []
        pdr_list: List[float] = []
        share100_list: List[float] = []
        pwr_list: List[float] = []
        adv_list: List[float] = []

        for r in rows:
            pout_1s_list.extend(f_or_empty(r.get("pout_1s") or ""))
            tl_list.extend(f_or_empty(r.get("tl_mean_s") or ""))
            pdr_list.extend(f_or_empty(r.get("pdr_unique") or ""))
            share100_list.extend(f_or_empty(r.get("rx_tag_share100_time_est") or ""))
            pwr_list.extend(f_or_empty(r.get("avg_power_mW") or ""))
            adv_list.extend(f_or_empty(r.get("adv_count") or ""))

        pout_m, pout_s = mean_std(pout_1s_list)
        tl_m, tl_s = mean_std(tl_list)
        pdr_m, pdr_s = mean_std(pdr_list)
        sh_m, sh_s = mean_std(share100_list)
        pwr_m, pwr_s = mean_std(pwr_list)
        adv_m, adv_s = mean_std(adv_list)

        summary_rows.append(
            {
                "condition": cond,
                "n_trials": len(rows),
                "pout_1s_mean": round(pout_m, 6),
                "pout_1s_std": round(pout_s, 6),
                "tl_mean_s_mean": round(tl_m, 6),
                "tl_mean_s_std": round(tl_s, 6),
                "pdr_unique_mean": round(pdr_m, 6) if pdr_list else "",
                "pdr_unique_std": round(pdr_s, 6) if pdr_list else "",
                "rx_tag_share100_time_est_mean": round(sh_m, 6) if share100_list else "",
                "rx_tag_share100_time_est_std": round(sh_s, 6) if share100_list else "",
                "avg_power_mW_mean": round(pwr_m, 3) if pwr_list else "",
                "avg_power_mW_std": round(pwr_s, 3) if pwr_list else "",
                "adv_count_mean": round(adv_m, 3) if adv_list else "",
                "adv_count_std": round(adv_s, 3) if adv_list else "",
            }
        )

    sum_out = args.out_dir / "summary_by_condition.csv"
    with sum_out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        w.writerows(summary_rows)

    md_out = args.out_dir / "summary.md"
    lines: List[str] = []
    lines.append("# uccs_d2_scan90 merged metrics summary\n\n")
    lines.append("- purpose: merge summarized runs (per_trial.csv) and increase n without re-parsing raw logs.\n")
    for d in input_dirs:
        lines.append(f"- source: `{d}`\n")
    lines.append(f"- generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} (local)\n")
    lines.append(
        "- command: "
        f"`python3 uccs_d2_scan90/analysis/merge_metrics_runs.py --out-dir {args.out_dir} "
        + " ".join([f'--input-dir {d}' for d in input_dirs])
        + "`\n"
    )

    lines.append("\n## Summary (mean ± std)\n")
    lines.append("| condition | n | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|\n")
    for r in summary_rows:
        cond = str(r["condition"])
        n = int(r["n_trials"])
        pout = f"{r['pout_1s_mean']:.4f}±{r['pout_1s_std']:.4f}"
        tl = f"{r['tl_mean_s_mean']:.3f}±{r['tl_mean_s_std']:.3f}"
        pdr = (
            f"{r['pdr_unique_mean']:.3f}±{r['pdr_unique_std']:.3f}"
            if r["pdr_unique_mean"] != ""
            else ""
        )
        pwr = (
            f"{r['avg_power_mW_mean']:.1f}±{r['avg_power_mW_std']:.1f}"
            if r["avg_power_mW_mean"] != ""
            else ""
        )
        adv = (
            f"{r['adv_count_mean']:.1f}±{r['adv_count_std']:.1f}"
            if r["adv_count_mean"] != ""
            else ""
        )
        sh = (
            f"{r['rx_tag_share100_time_est_mean']:.3f}±{r['rx_tag_share100_time_est_std']:.3f}"
            if r["rx_tag_share100_time_est_mean"] != ""
            else ""
        )
        lines.append(f"| {cond} | {n} | {pout} | {tl} | {pdr} | {pwr} | {adv} | {sh} |\n")

    lines.append("\n## Notes\n")
    lines.append("- This script does not recompute TL/Pout; it re-aggregates existing per-trial metrics.\n")
    lines.append("- Rounding follows summarize_d2_run.py (pout/TL/PDR/share: 6 decimals, power/adv: 3 decimals).\n")
    md_out.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

