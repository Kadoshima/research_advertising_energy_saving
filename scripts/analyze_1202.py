#!/usr/bin/env python3
"""
TICK+seq方式のログ解析スクリプト.
- TXSD: trial_*.csv を読み、summary/diagから ms_total, adv_count, E_total_mJ, mean_p_mW を取得。
- RX: seqロガー (rx_trial_*.csv) を読み、seqの巻き戻りで trial を分割し rx_count を算出。
- interval推定: ms_total/adv_count を 100/500/1000/2000 の中で最も近いものに割付。
- optional: P_off[mW] を指定すると ΔE/adv を計算。

使い方:
  python scripts/analyze_1202.py --txsd-dir data/1202配線変更後/1m_on_test1/TX \
                                 --rx-file data/1202配線変更後/1m_on_test1/RX/rx_trial_005.csv \
                                 --p-off 180
"""
import argparse
import csv
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

CANDIDATES = [100, 500, 1000, 2000]


def infer_interval(ms_total: float, adv_count: int) -> Optional[int]:
    if adv_count <= 0 or ms_total <= 0:
        return None
    est = ms_total / adv_count
    return min(CANDIDATES, key=lambda c: abs(c - est))


def parse_txsd_trial(path: Path) -> Dict[str, Any]:
    ms_total = adv_count = None
    e_total = mean_p = mean_v = mean_i = None
    with path.open(errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("# summary"):
                m = re.search(r"ms_total=([0-9.]+)", line); ms_total = float(m.group(1)) if m else ms_total
                m = re.search(r"adv_count=([0-9.]+)", line); adv_count = int(float(m.group(1))) if m else adv_count
                m = re.search(r"E_total_mJ=([0-9.]+)", line); e_total = float(m.group(1)) if m else e_total
            elif line.startswith("# diag") and mean_p is None:
                m = re.search(r"mean_p_mW=([0-9.]+)", line); mean_p = float(m.group(1)) if m else mean_p
                m = re.search(r"mean_v=([0-9.]+)", line); mean_v = float(m.group(1)) if m else mean_v
                m = re.search(r"mean_i=([0-9.]+)", line); mean_i = float(m.group(1)) if m else mean_i
    return {
        "file": path.name,
        "ms_total": ms_total or 0.0,
        "adv_count": adv_count or 0,
        "E_total_mJ": e_total or 0.0,
        "mean_p_mW": mean_p,
        "mean_v": mean_v,
        "mean_i": mean_i,
        "interval": infer_interval(ms_total or 0.0, adv_count or 0),
    }


def parse_txsd_dir(txsd_dir: Path) -> List[Dict[str, Any]]:
    trials = []
    for path in sorted(txsd_dir.glob("trial_*_on.csv")):
        trials.append(parse_txsd_trial(path))
    return trials


def parse_rx_seq(rx_file: Path) -> List[Dict[str, Any]]:
    trials = []
    current = None
    prev_seq = None
    with rx_file.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith('#') or row[0].startswith('ms'):
                continue
            try:
                ms = int(row[0])
                seq = int(row[3], 0)  # seqは十進と仮定、念のため0で解釈
            except Exception:
                continue
            if prev_seq is None:
                current = {"rx_count": 0, "first_ms": ms, "last_ms": ms}
            elif seq < prev_seq:
                # 巻き戻り → trial区切り
                trials.append(current)
                current = {"rx_count": 0, "first_ms": ms, "last_ms": ms}
            # accumulate
            current["rx_count"] += 1
            current["last_ms"] = ms
            prev_seq = seq
    if current:
        trials.append(current)
    # interval推定（粗いが目安）
    for t in trials:
        span = t["last_ms"] - t["first_ms"]
        t["interval"] = infer_interval(span, max(t["rx_count"], 1))
    return trials


def main():
    ap = argparse.ArgumentParser(description="Analyze TXSD (TICK-based) and RX seq logs")
    ap.add_argument("--txsd-dir", required=True, type=Path)
    ap.add_argument("--rx-file", required=True, type=Path)
    ap.add_argument("--p-off", type=float, default=None, help="P_off [mW] (optional). If given, computes ΔE/adv.")
    args = ap.parse_args()

    txsd_trials = parse_txsd_dir(args.txsd_dir)
    rx_trials = parse_rx_seq(args.rx_file)

    print(f"TXSD trials: {len(txsd_trials)}, RX trials: {len(rx_trials)}")
    n = min(len(txsd_trials), len(rx_trials))
    print("idx,interval_ms,ms_total,adv_count,E_total_mJ,mean_p_mW,rx_count,PDR,DeltaE_per_adv_uJ(if P_off)")
    for i in range(n):
        tx = txsd_trials[i]
        rx = rx_trials[i]
        ms_total = tx["ms_total"]
        adv = tx["adv_count"] or 1
        pdr = rx["rx_count"] / adv if adv else 0.0
        delta_uJ = None
        if args.p_off is not None:
            delta_mJ = tx["E_total_mJ"] - args.p_off * (ms_total/1000.0)
            delta_uJ = delta_mJ * 1000.0 / adv
        print(f"{i+1},{tx['interval']},{ms_total:.0f},{adv},{tx['E_total_mJ']:.1f},{(tx['mean_p_mW'] or 0):.1f},{rx['rx_count']},{pdr:.3f},{'' if delta_uJ is None else f'{delta_uJ:.1f}'}")

    # 集計: intervalごとに平均
    from collections import defaultdict
    buckets = defaultdict(list)
    for i in range(n):
        tx = txsd_trials[i]; rx = rx_trials[i]
        key = tx['interval']
        if key is None: continue
        adv = tx['adv_count'] or 1
        pdr = rx['rx_count']/adv if adv else 0.0
        delta_uJ = None
        if args.p_off is not None:
            delta_mJ = tx['E_total_mJ'] - args.p_off * (tx['ms_total']/1000.0)
            delta_uJ = delta_mJ * 1000.0 / adv
        buckets[key].append((tx['E_total_mJ']/adv, pdr, delta_uJ))
    if buckets:
        print("\nInterval-wise mean (E_per_adv_mJ, PDR, DeltaE_per_adv_uJ if P_off)")
        for key in sorted(buckets):
            e_adv = [x[0] for x in buckets[key]]
            pdrs = [x[1] for x in buckets[key]]
            deltas = [x[2] for x in buckets[key] if x[2] is not None]
            import statistics as stats
            print(f"{key}ms: E/adv={stats.mean(e_adv):.3f} mJ, PDR={stats.mean(pdrs):.3f}" + (f", DeltaE/adv={stats.mean(deltas):.1f} µJ" if deltas else ""))

if __name__ == "__main__":
    main()
