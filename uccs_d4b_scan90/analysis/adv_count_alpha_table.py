#!/usr/bin/env python3
"""
Create a small "same-mix" evidence table for the letter.

We compute:
  - adv_count (TXSD tick_count)
  - alpha_adv = (adv_count - adv_500) / (adv_100 - adv_500) per environment
  - avg_power_mW and P_out(1s)

Inputs: per_trial.csv (scan90 and scan70 D4B runs).
Outputs: CSV + Markdown.

No external dependencies.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import dataclass
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


@dataclass(frozen=True)
class CondAgg:
    n: int
    adv_mean: float
    adv_std: float
    power_mean: float
    power_std: float
    pout_mean: float
    pout_std: float


def read_per_trial(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def agg_by_condition(per_trial: Path) -> Dict[str, CondAgg]:
    rows = read_per_trial(per_trial)
    by: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        cond = (r.get("condition") or "").strip()
        if not cond:
            continue
        by.setdefault(cond, []).append(r)

    out: Dict[str, CondAgg] = {}
    for cond, rs in by.items():
        adv = [_f(r.get("adv_count") or "") for r in rs]
        pwr = [_f(r.get("avg_power_mW") or "") for r in rs]
        pout = [_f(r.get("pout_1s") or "") for r in rs]
        adv_f = [x for x in adv if x is not None]
        pwr_f = [x for x in pwr if x is not None]
        pout_f = [x for x in pout if x is not None]
        if len(adv_f) < 1 or len(pwr_f) < 1 or len(pout_f) < 1:
            continue
        out[cond] = CondAgg(
            n=len(rs),
            adv_mean=float(statistics.mean(adv_f)),
            adv_std=float(statistics.pstdev(adv_f)) if len(adv_f) >= 2 else 0.0,
            power_mean=float(statistics.mean(pwr_f)),
            power_std=float(statistics.pstdev(pwr_f)) if len(pwr_f) >= 2 else 0.0,
            pout_mean=float(statistics.mean(pout_f)),
            pout_std=float(statistics.pstdev(pout_f)) if len(pout_f) >= 2 else 0.0,
        )
    return out


def alpha_adv(adv: float, adv100: float, adv500: float) -> float:
    denom = (adv100 - adv500)
    if denom == 0.0:
        return float("nan")
    return (adv - adv500) / denom


def _fmt(v: float, digits: int = 3) -> str:
    if math.isnan(v) or math.isinf(v):
        return "NA"
    return f"{v:.{digits}f}"


def _cond_short(cond: str) -> str:
    m = {
        "S4_fixed100": "Fixed100",
        "S4_fixed500": "Fixed500",
        "S4_policy": "Policy(U+CCS)",
        "S4_ablation_ccs_off": "U-only(CCS-off)",
    }
    return m.get(cond, cond)


def write_table(out_csv: Path, out_md: Path, scan90: Dict[str, CondAgg], scan70: Dict[str, CondAgg]) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    def rows_for_env(env: str, agg: Dict[str, CondAgg]) -> List[Dict[str, str]]:
        if "S4_fixed100" not in agg or "S4_fixed500" not in agg:
            raise SystemExit(f"{env}: missing S4_fixed100/S4_fixed500")
        adv100 = agg["S4_fixed100"].adv_mean
        adv500 = agg["S4_fixed500"].adv_mean
        out: List[Dict[str, str]] = []
        for cond in ["S4_fixed100", "S4_fixed500", "S4_policy", "S4_ablation_ccs_off"]:
            if cond not in agg:
                continue
            a = agg[cond]
            alpha = alpha_adv(a.adv_mean, adv100=adv100, adv500=adv500)
            out.append(
                {
                    "env": env,
                    "condition": cond,
                    "condition_short": _cond_short(cond),
                    "n": str(a.n),
                    "adv_count_mean": _fmt(a.adv_mean, 1),
                    "adv_count_std": _fmt(a.adv_std, 1),
                    "alpha_adv": _fmt(alpha, 4),
                    "avg_power_mW_mean": _fmt(a.power_mean, 3),
                    "avg_power_mW_std": _fmt(a.power_std, 3),
                    "pout_1s_mean": _fmt(a.pout_mean, 5),
                    "pout_1s_std": _fmt(a.pout_std, 5),
                }
            )
        return out

    rows = rows_for_env("scan90", scan90) + rows_for_env("scan70", scan70)

    # CSV
    fields = [
        "env",
        "condition",
        "condition_short",
        "n",
        "adv_count_mean",
        "adv_count_std",
        "alpha_adv",
        "avg_power_mW_mean",
        "avg_power_mW_std",
        "pout_1s_mean",
        "pout_1s_std",
    ]
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Markdown
    lines: List[str] = []
    lines.append("# adv_count / α_adv table (same-mix evidence)")
    lines.append("")
    lines.append("定義: `alpha_adv = (adv_count - adv_500) / (adv_100 - adv_500)`（同一scan環境内で固定100/固定500を基準に正規化）")
    lines.append("")
    lines.append("| env | condition | n | adv_count (mean±std) | alpha_adv | avg_power_mW (mean±std) | pout_1s (mean±std) |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r['env']} | {r['condition_short']} | {r['n']} | {r['adv_count_mean']}±{r['adv_count_std']} | {r['alpha_adv']} | {r['avg_power_mW_mean']}±{r['avg_power_mW_std']} | {r['pout_1s_mean']}±{r['pout_1s_std']} |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan90", type=Path, required=True, help="per_trial.csv (scan90)")
    ap.add_argument("--scan70", type=Path, required=True, help="per_trial.csv (scan70)")
    ap.add_argument("--out-csv", type=Path, required=True)
    ap.add_argument("--out-md", type=Path, required=True)
    args = ap.parse_args()

    scan90 = agg_by_condition(args.scan90)
    scan70 = agg_by_condition(args.scan70)
    write_table(args.out_csv, args.out_md, scan90=scan90, scan70=scan70)


if __name__ == "__main__":
    main()

