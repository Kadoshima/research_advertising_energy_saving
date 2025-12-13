#!/usr/bin/env python3
"""
Compare scan50 vs scan90 aggregated metrics for stress_fixed (S1/S4 × interval).

Inputs:
  - scan50 agg_enriched (v5): results/stress_fixed/scan50/*_agg_enriched_*_v5.csv
  - scan90 agg_enriched (v5): results/stress_fixed/scan90/*_agg_enriched_*_v5.csv

Outputs:
  - CSV with scan50/scan90/delta columns
  - Optional text bar for pdr_unique at 100ms
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def to_float(x: str) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def to_int(x: str) -> int:
    try:
        return int(float(x))
    except Exception:
        return 0


def base_session(session: str) -> Optional[str]:
    m = re.search(r"(S\d+)", session)
    return m.group(1) if m else None


def load_agg(path: Path) -> Dict[Tuple[str, int], Dict[str, str]]:
    out: Dict[Tuple[str, int], Dict[str, str]] = {}
    with path.open() as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            sess = (row.get("session") or "").strip()
            interval = to_int(row.get("interval_ms", "0"))
            if not sess or interval <= 0:
                continue
            out[(sess, interval)] = row
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare scan50 vs scan90 stress_fixed metrics (v5).")
    ap.add_argument("--scan50", required=True, type=Path)
    ap.add_argument("--scan90", required=True, type=Path)
    ap.add_argument("--out-csv", required=True, type=Path)
    ap.add_argument("--out-pdr-txt", type=Path, default=None)
    args = ap.parse_args()

    scan50 = load_agg(args.scan50)
    scan90 = load_agg(args.scan90)

    scan90_by_base: Dict[Tuple[str, int], Dict[str, str]] = {}
    for (sess90, interval), row90 in scan90.items():
        b = base_session(sess90) or sess90
        scan90_by_base[(b, interval)] = row90

    metrics = [
        "pdr_unique_mean",
        "pout_1s_mean",
        "tl_mean_s_mean",
        "tl_p95_s_mean",
        "E_per_adv_uJ_mean",
        "avg_power_mW_mean",
    ]

    out_rows: List[Dict[str, object]] = []
    for (sess50, interval), row50 in sorted(scan50.items(), key=lambda x: (x[0][0], x[0][1])):
        b = base_session(sess50)
        if not b:
            continue
        row90 = scan90_by_base.get((b, interval))
        if not row90:
            continue

        out_row: Dict[str, object] = {"session": sess50, "interval_ms": interval}
        for m in metrics:
            v50 = to_float(row50.get(m, "0"))
            v90 = to_float(row90.get(m, "0"))
            out_row[f"{m}_scan50"] = v50
            out_row[f"{m}_scan90"] = v90
            out_row[f"{m}_delta"] = v90 - v50
        out_rows.append(out_row)

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: List[str] = ["session", "interval_ms"]
    for m in metrics:
        fieldnames.extend([f"{m}_scan50", f"{m}_scan90", f"{m}_delta"])
    with args.out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    if args.out_pdr_txt:
        lines: List[str] = []
        lines.append("# pdr_unique (scan50 vs scan90, v5)")
        for r in out_rows:
            if int(r["interval_ms"]) != 100:
                continue
            p50 = float(r["pdr_unique_mean_scan50"])
            p90 = float(r["pdr_unique_mean_scan90"])
            bar50 = "█" * int(round(p50 * 20))
            bar90 = "█" * int(round(p90 * 20))
            lines.append(f"{r['session']} @100ms  scan50 {p50:.3f} {bar50}")
            lines.append(f"{r['session']} @100ms  scan90 {p90:.3f} {bar90}")
            lines.append("")
        args.out_pdr_txt.parent.mkdir(parents=True, exist_ok=True)
        args.out_pdr_txt.write_text("\n".join(lines), encoding="utf-8")

    print(f"[INFO] wrote compare CSV: {args.out_csv}")
    if args.out_pdr_txt:
        print(f"[INFO] wrote pdr text: {args.out_pdr_txt}")


if __name__ == "__main__":
    main()

