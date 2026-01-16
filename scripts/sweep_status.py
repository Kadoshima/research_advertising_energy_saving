#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TXシリアル無しで、RX/TXSD の SDログ(csv)だけから sweep 完走可否を判定する。

想定入力（コピーしてくる）:
  <run_dir>/RX/*.csv      (rx_*.csv)
  <run_dir>/TXSD/*.csv    (pwr_*_sweep.csv)

使い方:
  python scripts/sweep_status.py data/実験データ/研究室/<run_dir>
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Optional


DEBUG_LOG_PATH = Path(".cursor") / "debug.log"
RUN_ID = os.environ.get("SWEEP_RUN_ID", "rx_txsd_only")


def _ndjson(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "debug-session",
            "runId": RUN_ID,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


RX_FN_RE = re.compile(r"^rx_(\d+)_([0-9a-fA-F]+)\.csv$")
TXSD_FN_RE = re.compile(r"^pwr_(\d+)_([0-9a-fA-F]+)_sweep\.csv$")


def _extract_start_ms(name: str) -> Optional[int]:
    m = RX_FN_RE.match(name)
    if m:
        return int(m.group(1))
    m = TXSD_FN_RE.match(name)
    if m:
        return int(m.group(1))
    return None


def _read_csv_data_rows(path: Path) -> list[dict]:
    # Skip comment/meta lines that start with '#'
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        # Find header
        header = None
        for line in f:
            if line.startswith("#"):
                continue
            header = line.strip()
            break
        if not header:
            return rows
        reader = csv.DictReader(f, fieldnames=header.split(","))
        for r in reader:
            # Some rows may be blank at EOF
            if not any((v or "").strip() for v in r.values()):
                continue
            rows.append(r)
    return rows


@dataclass
class RxTrial:
    path: Path
    start_ms: int
    dur_ms: int
    rx_n: int
    median_dt_ms: Optional[float]
    inferred_mode_ms: Optional[int]  # 100/500/1000/2000 or None


@dataclass
class TxsdTrial:
    path: Path
    start_ms: int
    dur_ms: int
    adv_n: Optional[int]
    inferred_mode_ms: Optional[int]


def _infer_interval_from_dts(dts_ms: list[float]) -> Optional[int]:
    if not dts_ms:
        return None
    m = median(dts_ms)
    # nearest among supported
    candidates = [100, 500, 1000, 2000]
    best = min(candidates, key=lambda x: abs(x - m))
    # accept if within 40% (loose; RSSI/drop can stretch)
    if abs(best - m) <= max(40.0, best * 0.40):
        return int(best)
    return None


def _infer_interval_from_advcount(dur_ms: int, adv_n: int) -> Optional[int]:
    if adv_n <= 1 or dur_ms <= 0:
        return None
    est = dur_ms / float(adv_n)
    candidates = [100, 500, 1000, 2000]
    best = min(candidates, key=lambda x: abs(x - est))
    if abs(best - est) <= max(40.0, best * 0.40):
        return int(best)
    return None


def _load_rx_trials(rx_dir: Path) -> list[RxTrial]:
    trials: list[RxTrial] = []
    for p in sorted(rx_dir.glob("rx_*.csv")):
        start_ms = _extract_start_ms(p.name)
        if start_ms is None:
            continue
        rows = _read_csv_data_rows(p)
        # expected columns: prog_id,ms,event,rssi,addr,mfd
        ms_list: list[int] = []
        for r in rows:
            try:
                ms_list.append(int(float(r.get("ms", "0"))))
            except Exception:
                continue
        ms_list.sort()
        dur_ms = (ms_list[-1] if ms_list else 0)
        # dt between successive rows (roughly adv interval if PDR high-ish)
        dts = []
        for a, b in zip(ms_list, ms_list[1:]):
            if b > a:
                dts.append(float(b - a))
        inferred = _infer_interval_from_dts(dts)
        trials.append(
            RxTrial(
                path=p,
                start_ms=int(start_ms),
                dur_ms=int(dur_ms),
                rx_n=len(ms_list),
                median_dt_ms=(median(dts) if dts else None),
                inferred_mode_ms=inferred,
            )
        )
    return trials


def _load_txsd_trials(txsd_dir: Path) -> list[TxsdTrial]:
    trials: list[TxsdTrial] = []
    for p in sorted(txsd_dir.glob("pwr_*_sweep.csv")):
        start_ms = _extract_start_ms(p.name)
        if start_ms is None:
            continue
        rows = _read_csv_data_rows(p)
        ms_list: list[int] = []
        tick_last: Optional[int] = None
        tick_first: Optional[int] = None
        for r in rows:
            try:
                ms_list.append(int(float(r.get("ms", "0"))))
            except Exception:
                pass
            if "tick_raw" in r:
                try:
                    t = int(float(r.get("tick_raw", "0")))
                    if tick_first is None:
                        tick_first = t
                    tick_last = t
                except Exception:
                    pass
        ms_list.sort()
        dur_ms = (ms_list[-1] if ms_list else 0)
        adv_n = None
        if tick_first is not None and tick_last is not None and tick_last >= tick_first:
            adv_n = tick_last - tick_first
        inferred = _infer_interval_from_advcount(dur_ms, adv_n) if adv_n is not None else None
        trials.append(
            TxsdTrial(
                path=p,
                start_ms=int(start_ms),
                dur_ms=int(dur_ms),
                adv_n=adv_n,
                inferred_mode_ms=inferred,
            )
        )
    return trials


def _monotonicity(trials_start_ms: list[int]) -> dict:
    if not trials_start_ms:
        return {"n": 0, "drops": 0}
    drops = 0
    for a, b in zip(trials_start_ms, trials_start_ms[1:]):
        if b < a:
            drops += 1
    return {"n": len(trials_start_ms), "drops": drops}


def main(argv: list[str]) -> int:
    # argv:
    #   python scripts/sweep_status.py <run_dir> [run_id]
    global RUN_ID
    if len(argv) not in (2, 3):
        print("usage: python scripts/sweep_status.py <run_dir> [run_id]")
        return 2

    run_dir = Path(argv[1])
    if len(argv) == 3:
        RUN_ID = argv[2]
    rx_dir = run_dir / "RX"
    txsd_dir = run_dir / "TXSD"

    if not rx_dir.exists() or not txsd_dir.exists():
        print(f"[ERR] expected directories: {rx_dir} and {txsd_dir}")
        return 2

    rx_trials = _load_rx_trials(rx_dir)
    txsd_trials = _load_txsd_trials(txsd_dir)

    _ndjson("H1", "scripts/sweep_status.py:main", "loaded trials", {
        "rx_n": len(rx_trials),
        "txsd_n": len(txsd_trials),
        "run_dir": str(run_dir),
    })

    rx_mono = _monotonicity([t.start_ms for t in rx_trials])
    txsd_mono = _monotonicity([t.start_ms for t in txsd_trials])
    _ndjson("H2", "scripts/sweep_status.py:main", "start_ms monotonicity", {
        "rx": rx_mono,
        "txsd": txsd_mono,
    })

    # Mode inference summary
    rx_mode_hist: dict[str, int] = {}
    for t in rx_trials:
        k = str(t.inferred_mode_ms) if t.inferred_mode_ms is not None else "None"
        rx_mode_hist[k] = rx_mode_hist.get(k, 0) + 1
    txsd_mode_hist: dict[str, int] = {}
    adv_small = 0
    for t in txsd_trials:
        k = str(t.inferred_mode_ms) if t.inferred_mode_ms is not None else "None"
        txsd_mode_hist[k] = txsd_mode_hist.get(k, 0) + 1
        if t.adv_n is not None and t.adv_n <= 3:
            adv_small += 1
    _ndjson("H3", "scripts/sweep_status.py:main", "mode histogram", {
        "rx_mode_hist": rx_mode_hist,
        "txsd_mode_hist": txsd_mode_hist,
        "txsd_adv_n_le_3": adv_small,
    })

    # Extra metrics for rx=0 / too-short detection
    rx_zero = sum(1 for t in rx_trials if t.rx_n == 0)
    rx_short = sum(1 for t in rx_trials if t.dur_ms < 1000)
    txsd_short = sum(1 for t in txsd_trials if t.dur_ms < 1000)
    _ndjson("H4", "scripts/sweep_status.py:main", "trial quality counters", {
        "rx_zero_trials": rx_zero,
        "rx_short_trials_lt_1s": rx_short,
        "txsd_short_trials_lt_1s": txsd_short,
    })

    # Completion heuristic: expect 50 trials total per device
    expected_total = 5 * 10
    rx_complete = len(rx_trials) >= expected_total
    txsd_complete = len(txsd_trials) >= expected_total
    likely_loop = (rx_mono["drops"] > 0) or (txsd_mono["drops"] > 0) or (len(rx_trials) > expected_total + 5) or (len(txsd_trials) > expected_total + 5)

    _ndjson("H1", "scripts/sweep_status.py:main", "completion flags", {
        "expected_total": expected_total,
        "rx_complete_by_count": rx_complete,
        "txsd_complete_by_count": txsd_complete,
        "likely_loop_or_reset": likely_loop,
    })

    print("=== sweep status (TX serialなし / RX+TXSDのみ) ===")
    print(f"run_dir: {run_dir}")
    print(f"RX trials:   {len(rx_trials)} (expected {expected_total}) drops(start_ms): {rx_mono['drops']}")
    print(f"TXSD trials: {len(txsd_trials)} (expected {expected_total}) drops(start_ms): {txsd_mono['drops']}")
    print(f"RX inferred intervals (median dt): {rx_mode_hist}")
    print(f"TXSD inferred intervals (adv_count): {txsd_mode_hist}  adv_n<=3: {adv_small}")

    if likely_loop:
        print("[WARN] 周回/リセットの疑いあり（start_msが逆行、またはファイル数がexpectedを大きく超過）")
    if not rx_complete or not txsd_complete:
        print("[INCOMPLETE] 少なくともファイル数ベースでは未完了の可能性")
    else:
        print("[COMPLETE?] ファイル数ベースでは完了相当（ただし周回/リセットの有無に注意）")

    # Stronger signal: check presence of all inferred modes from RX side
    have = set(int(k) for k in rx_mode_hist.keys() if k.isdigit())
    if have:
        missing = [m for m in [100, 500, 1000, 2000] if m not in have]
        if missing:
            print(f"[WARN] RX側の推定intervalに欠落あり: missing={missing}（rx=0が多い/受信できていない可能性）")
    if adv_small > 0:
        print("[WARN] TXSDのadv_countが極端に小さいtrialが多い（TICK配線/割り込み/ノイズの可能性）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

