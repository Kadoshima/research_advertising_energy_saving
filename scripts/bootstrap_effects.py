#!/usr/bin/env python3
"""
Bootstrap effect sizes (difference of means) with percentile CI from per-trial CSVs.

Designed for this repo's uccs_* metrics outputs:
  - uccs_d4b_scan90/metrics/<run>/per_trial.csv
  - uccs_d4_scan90/metrics/<run>/per_trial.csv
  - uccs_d3_scan70/metrics/<run>/per_trial.csv

No external dependencies (no pandas/numpy).

Example:
  python3 scripts/bootstrap_effects.py \
    --in uccs_d4b_scan90/metrics/01/per_trial.csv \
    --out-dir uccs_d4b_scan90/metrics/01 \
    --title "D4B scan90 S4 (run01)" \
    --compare "pout_1s,S4_policy,S4_ablation_ccs_off,Δpout (U+CCS − U-only)" \
    --compare "avg_power_mW,S4_policy,S4_ablation_ccs_off,Δpower (U+CCS − U-only)" \
    --n-boot 20000 --seed 20251217
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class EffectResult:
    metric: str
    cond_a: str
    cond_b: str
    label: str
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    delta: float
    ci_low: float
    ci_high: float
    p_two_sided: float


def _mean(xs: Iterable[float]) -> float:
    xs = list(xs)
    if not xs:
        return float("nan")
    return sum(xs) / len(xs)


def _parse_float(v: str) -> Optional[float]:
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


def _percentile(sorted_xs: List[float], p: float) -> float:
    if not sorted_xs:
        return float("nan")
    if p <= 0:
        return sorted_xs[0]
    if p >= 1:
        return sorted_xs[-1]
    k = (len(sorted_xs) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_xs[int(k)]
    d0 = sorted_xs[f] * (c - k)
    d1 = sorted_xs[c] * (k - f)
    return d0 + d1


def _bootstrap_delta(
    a: List[float],
    b: List[float],
    n_boot: int,
    seed: int,
) -> List[float]:
    rnd = random.Random(seed)
    na, nb = len(a), len(b)
    if na <= 0 or nb <= 0:
        return []
    out: List[float] = []
    for _ in range(n_boot):
        sa = [a[rnd.randrange(na)] for _ in range(na)]
        sb = [b[rnd.randrange(nb)] for _ in range(nb)]
        out.append(_mean(sa) - _mean(sb))
    return out


def _two_sided_p_from_bootstrap(deltas: List[float], obs: float) -> float:
    if not deltas:
        return float("nan")
    # percentile bootstrap p-value: 2*min(P(delta>=0), P(delta<=0)) around the null 0.
    ge0 = sum(1 for d in deltas if d >= 0.0) / len(deltas)
    le0 = sum(1 for d in deltas if d <= 0.0) / len(deltas)
    p = 2.0 * min(ge0, le0)
    return min(1.0, max(0.0, p))


def _read_values_by_condition(per_trial_csv: Path, metric: str) -> Dict[str, List[float]]:
    out: Dict[str, List[float]] = {}
    with per_trial_csv.open(newline="") as f:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames:
            raise SystemExit(f"empty header: {per_trial_csv}")
        if "condition" not in rdr.fieldnames:
            raise SystemExit(f"missing column 'condition' in {per_trial_csv}")
        if metric not in rdr.fieldnames:
            raise SystemExit(f"missing metric '{metric}' in {per_trial_csv} (available: {rdr.fieldnames})")
        for row in rdr:
            cond = (row.get("condition") or "").strip()
            if not cond:
                continue
            v = _parse_float(row.get(metric) or "")
            if v is None:
                continue
            out.setdefault(cond, []).append(v)
    return out


def _parse_compare(spec: str) -> Tuple[str, str, str, str]:
    # "metric,condA,condB,label"
    parts = [p.strip() for p in (spec or "").split(",")]
    if len(parts) < 3:
        raise SystemExit(f"invalid --compare: {spec!r}")
    metric = parts[0]
    cond_a = parts[1]
    cond_b = parts[2]
    label = parts[3] if len(parts) >= 4 else f"{metric}: {cond_a} - {cond_b}"
    return metric, cond_a, cond_b, label


def _fmt(v: float, digits: int = 4) -> str:
    if math.isnan(v) or math.isinf(v):
        return "NA"
    return f"{v:.{digits}f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_csv", type=Path, required=True, help="per_trial.csv")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--title", type=str, default="")
    ap.add_argument("--compare", action="append", default=[], help="metric,condA,condB[,label]")
    ap.add_argument("--n-boot", type=int, default=20000)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if not args.compare:
        raise SystemExit("at least one --compare is required")
    if args.n_boot < 1000:
        raise SystemExit("--n-boot should be >= 1000")
    if not (0.0 < args.alpha < 1.0):
        raise SystemExit("--alpha must be in (0,1)")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = args.out_dir / "effects_ci.csv"
    out_md = args.out_dir / "effects_ci.md"

    results: List[EffectResult] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # cache by metric
    values_cache: Dict[str, Dict[str, List[float]]] = {}

    for i, spec in enumerate(args.compare):
        metric, cond_a, cond_b, label = _parse_compare(spec)
        if metric not in values_cache:
            values_cache[metric] = _read_values_by_condition(args.in_csv, metric)
        values = values_cache[metric]
        a = values.get(cond_a, [])
        b = values.get(cond_b, [])
        if len(a) < 2 or len(b) < 2:
            raise SystemExit(f"not enough samples for {metric}: {cond_a} n={len(a)}, {cond_b} n={len(b)}")
        mean_a = _mean(a)
        mean_b = _mean(b)
        obs = mean_a - mean_b
        # Use a per-compare seed so multiple compares are stable.
        deltas = _bootstrap_delta(a, b, n_boot=args.n_boot, seed=args.seed + 10007 * (i + 1))
        deltas.sort()
        ci_low = _percentile(deltas, args.alpha / 2.0)
        ci_high = _percentile(deltas, 1.0 - args.alpha / 2.0)
        p_two = _two_sided_p_from_bootstrap(deltas, obs)
        results.append(
            EffectResult(
                metric=metric,
                cond_a=cond_a,
                cond_b=cond_b,
                label=label,
                n_a=len(a),
                n_b=len(b),
                mean_a=mean_a,
                mean_b=mean_b,
                delta=obs,
                ci_low=ci_low,
                ci_high=ci_high,
                p_two_sided=p_two,
            )
        )

    # Write CSV
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "metric",
                "cond_a",
                "cond_b",
                "label",
                "n_a",
                "n_b",
                "mean_a",
                "mean_b",
                "delta_mean",
                "ci_low",
                "ci_high",
                "p_two_sided",
                "n_boot",
                "alpha",
                "seed",
                "generated_local",
                "source_csv",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r.metric,
                    r.cond_a,
                    r.cond_b,
                    r.label,
                    r.n_a,
                    r.n_b,
                    r.mean_a,
                    r.mean_b,
                    r.delta,
                    r.ci_low,
                    r.ci_high,
                    r.p_two_sided,
                    args.n_boot,
                    args.alpha,
                    args.seed,
                    now,
                    str(args.in_csv),
                ]
            )

    # Write MD (compact, letter-friendly)
    lines: List[str] = []
    if args.title:
        lines.append(f"# effects_ci: {args.title}\n")
    else:
        lines.append("# effects_ci\n")
    lines.append(f"- source: `{args.in_csv}`")
    lines.append(f"- generated: {now} (local)")
    lines.append(f"- bootstrap: percentile CI, n_boot={args.n_boot}, alpha={args.alpha}, seed={args.seed}\n")
    lines.append("| label | delta(mean) | 95% CI | p(two-sided) |")
    lines.append("|---|---:|---:|---:|")
    for r in results:
        lines.append(
            f"| {r.label} | {_fmt(r.delta)} | [{_fmt(r.ci_low)}, {_fmt(r.ci_high)}] | {_fmt(r.p_two_sided, 4)} |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

