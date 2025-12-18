#!/usr/bin/env python3
"""
Tune U-only thresholds (U_MID/U_HIGH) so that its effective power-mix alpha matches Policy.

This is an *offline* tuning helper: it replays the frozen stress_causal S4 U-series
used by the TX firmware and simulates the U-only controller (100<->500).

It does NOT predict radio QoS; it only matches alpha (=power-mix / share100_power_mix).
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import List, Tuple


DEFAULT_HYST = 0.02
DEFAULT_EMA_ALPHA = 0.20
DEFAULT_DT_MS = 100
DEFAULT_N_STEPS = 1800


def parse_u_series_from_header(path: Path, array_name: str = "S4_U_Q") -> List[float]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    # Match: static const uint8_t <array>[] PROGMEM = { ... };
    pat = (
        r"static\s+const\s+uint8_t\s+"
        + re.escape(array_name)
        + r"\[\]\s+PROGMEM\s*=\s*\{(.*?)\};"
    )
    m = re.search(pat, text, flags=re.DOTALL)
    if not m:
        raise SystemExit(f"array not found: {array_name} in {path}")
    nums = [int(x) for x in re.findall(r"\d+", m.group(1))]
    return [n / 255.0 for n in nums]


def simulate_u_only(
    u_series: List[float],
    u_mid: float,
    u_high: float,
    hyst: float,
    ema_alpha: float,
    dt_ms: int = 100,
    start_itv: int = 500,
) -> Tuple[float, int, int]:
    itv = start_itv
    u_ema = 0.0
    switch_count = 0

    t100_ms = 0
    total_ms = 0
    adv_count = 0

    for step_idx, u in enumerate(u_series):
        u_ema = ema_alpha * u + (1.0 - ema_alpha) * u_ema

        next_itv = itv
        if itv == 500:
            if u_ema >= u_high:
                next_itv = 100
        else:
            if u_ema < (u_mid - hyst):
                next_itv = 500
        if next_itv != itv:
            switch_count += 1
            itv = next_itv

        total_ms += dt_ms
        if itv == 100:
            t100_ms += dt_ms

        t_ms = step_idx * dt_ms
        if (t_ms % itv) == 0:
            adv_count += 1

    share100_time = (t100_ms / total_ms) if total_ms > 0 else 0.0
    return share100_time, adv_count, switch_count


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--header",
        type=Path,
        default=Path("uccs_d2_scan90/src/tx/stress_causal_s1_s4_180s.h"),
    )
    ap.add_argument("--n-steps", type=int, default=DEFAULT_N_STEPS)
    ap.add_argument("--dt-ms", type=int, default=DEFAULT_DT_MS)
    ap.add_argument("--ema-alpha", type=float, default=DEFAULT_EMA_ALPHA)
    ap.add_argument("--hyst", type=float, default=DEFAULT_HYST)
    ap.add_argument("--target-alpha", type=float, required=True)
    ap.add_argument("--p100", type=float, required=True)
    ap.add_argument("--p500", type=float, required=True)
    ap.add_argument("--out-csv", type=Path, required=True)

    ap.add_argument("--u-mid-min", type=float, default=0.18)
    ap.add_argument("--u-mid-max", type=float, default=0.30)
    ap.add_argument("--u-mid-step", type=float, default=0.01)
    ap.add_argument("--u-high-min", type=float, default=0.32)
    ap.add_argument("--u-high-max", type=float, default=0.55)
    ap.add_argument("--u-high-step", type=float, default=0.01)
    args = ap.parse_args()

    u_series = parse_u_series_from_header(args.header, "S4_U_Q")[: args.n_steps]
    if len(u_series) < args.n_steps:
        raise SystemExit(f"u_series too short: {len(u_series)} < {args.n_steps}")

    denom = args.p100 - args.p500
    if denom <= 0:
        raise SystemExit(f"invalid p100/p500: p100={args.p100} p500={args.p500}")

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "u_mid",
                "u_high",
                "share100_time",
                "adv_count_est",
                "switch_count",
                "alpha_est",
                "avg_power_est_mW",
                "alpha_err",
            ],
        )
        w.writeheader()

        best = None

        u_mid = args.u_mid_min
        while u_mid <= args.u_mid_max + 1e-9:
            u_high = args.u_high_min
            while u_high <= args.u_high_max + 1e-9:
                share100, adv_count, sw = simulate_u_only(
                    u_series=u_series,
                    u_mid=u_mid,
                    u_high=u_high,
                    hyst=args.hyst,
                    ema_alpha=args.ema_alpha,
                    dt_ms=args.dt_ms,
                    start_itv=500,
                )
                avg_p = args.p500 + share100 * (args.p100 - args.p500)
                alpha_est = (avg_p - args.p500) / denom
                alpha_err = abs(alpha_est - args.target_alpha)

                row = {
                    "u_mid": round(u_mid, 4),
                    "u_high": round(u_high, 4),
                    "share100_time": round(share100, 6),
                    "adv_count_est": adv_count,
                    "switch_count": sw,
                    "alpha_est": round(alpha_est, 6),
                    "avg_power_est_mW": round(avg_p, 3),
                    "alpha_err": round(alpha_err, 6),
                }
                w.writerow(row)

                key = (alpha_err, sw)
                if best is None or key < best[0]:
                    best = (key, row)

                u_high = round(u_high + args.u_high_step, 10)
            u_mid = round(u_mid + args.u_mid_step, 10)

    if best:
        print("best:", best[1])


if __name__ == "__main__":
    main()
