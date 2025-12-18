#!/usr/bin/env python3
"""
Compare "outage TOP-k transitions" between scan90 and scan70 for D4B.

Inputs:
  - outage_ranking.csv produced by outage_story_trace.py (scan90 and scan70)

Outputs:
  - Markdown summary with TOP-k by u_minus_p_out_rate.

No external deps.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Dict, List, Optional


def _f(v: str) -> Optional[float]:
    v = (v or "").strip()
    if not v:
        return None
    try:
        x = float(v)
    except Exception:
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def top_k(rows: List[Dict[str, str]], k: int) -> List[Dict[str, str]]:
    def key(r: Dict[str, str]) -> float:
        v = _f(r.get("u_minus_p_out_rate") or "")
        return v if v is not None else -1e9

    rs = sorted(rows, key=key, reverse=True)
    return rs[:k]


def bottom_k(rows: List[Dict[str, str]], k: int) -> List[Dict[str, str]]:
    def key(r: Dict[str, str]) -> float:
        v = _f(r.get("u_minus_p_out_rate") or "")
        return v if v is not None else 1e9

    rs = sorted(rows, key=key)
    return rs[:k]


def _fmt(v: Optional[float], digits: int = 4) -> str:
    if v is None or math.isnan(v) or math.isinf(v):
        return "NA"
    return f"{v:.{digits}f}"


def summarize(path: Path, k: int) -> List[Dict[str, str]]:
    rows = read_rows(path)
    return top_k(rows, k=k)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan90", type=Path, required=True, help="outage_ranking.csv (scan90)")
    ap.add_argument("--scan70", type=Path, required=True, help="outage_ranking.csv (scan70)")
    ap.add_argument("--out", type=Path, required=True, help="markdown output")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--k-neg", type=int, default=5, help="Also show TOP-k where policy is worse (most negative u_minus_p_out_rate)")
    args = ap.parse_args()

    rows90 = read_rows(args.scan90)
    rows70 = read_rows(args.scan70)
    t90 = top_k(rows90, args.k)
    t70 = top_k(rows70, args.k)
    n90 = bottom_k(rows90, args.k_neg)
    n70 = bottom_k(rows70, args.k_neg)

    lines: List[str] = []
    lines.append("# Outage TOP-k transitions (u-only − policy)")
    lines.append("")
    lines.append("- 目的: `P_out(1s)` の差が「少数の遷移(outage)」に集中していることを、TOP-kで可視化する。")
    lines.append("- `u_minus_p_out_rate` は、各遷移における outage率の差（U-only − Policy）。")
    lines.append("")

    def block(title: str, rows: List[Dict[str, str]]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| rank | step | prev→cur | policy_out/n | u-only_out/n | u_minus_p_out_rate |")
        lines.append("|---:|---:|---:|---:|---:|---:|")
        for i, r in enumerate(rows, 1):
            step = r.get("transition_step") or ""
            prev = r.get("label_prev") or ""
            cur = r.get("label_cur") or ""
            p_out = r.get("policy_out_n") or ""
            p_n = r.get("policy_n") or ""
            u_out = r.get("u_only_out_n") or ""
            u_n = r.get("u_only_n") or ""
            d = _fmt(_f(r.get("u_minus_p_out_rate") or ""), 4)
            lines.append(f"| {i} | {step} | {prev}→{cur} | {p_out}/{p_n} | {u_out}/{u_n} | {d} |")
        lines.append("")

    block("scan90 (D4B)", t90)
    block("scan70 (D4B)", t70)

    if args.k_neg > 0:
        lines.append("## 参考: policyが悪化している遷移（policy_out_rate > u-only_out_rate）")
        lines.append("")
        block("scan90 (most negative u_minus_p_out_rate)", n90)
        block("scan70 (most negative u_minus_p_out_rate)", n70)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
