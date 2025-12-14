#!/usr/bin/env python3
"""
Summarize Step D1 run logs for uccs_d1_scan90.

Inputs:
- uccs_d1_scan90/data/<run>/RX/rx_trial_*.csv
- uccs_d1_scan90/data/<run>/TX/trial_*.csv   (TXSD logs)

Filtering:
- By default, only keep trials with ms_total >= 50000 (≈50s) to drop aborted runs.

Outputs (per-run):
- uccs_d1_scan90/metrics/<run>/txsd_power_trials.csv
- uccs_d1_scan90/metrics/<run>/txsd_power_summary.csv
- uccs_d1_scan90/metrics/<run>/rx_trials.csv
- uccs_d1_scan90/metrics/<run>/rx_rate_summary.csv
- uccs_d1_scan90/metrics/<run>/summary.md
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class TxsdTrial:
    run: str
    rel_path: str
    path: str
    cond_id: Optional[int]
    interval_ms: Optional[int]
    tag: Optional[str]
    ms_total: Optional[int]
    mean_p_mw: Optional[float]
    mean_v: Optional[float]
    mean_i: Optional[float]
    samples: Optional[int]
    ok: bool


@dataclass(frozen=True)
class RxTrial:
    run: str
    rel_path: str
    path: str
    condition_label: Optional[str]
    ms_total: Optional[int]
    rx: int
    rate_hz: Optional[float]
    n_p100: int
    n_p500: int
    ok: bool


def infer_run(fp: Path) -> str:
    parts = list(fp.parts)
    if "data" in parts:
        i = parts.index("data")
        if i + 1 < len(parts):
            return parts[i + 1]
    return "unknown_run"


def infer_rel_path(fp: Path) -> str:
    parts = list(fp.parts)
    if "data" in parts:
        i = parts.index("data")
        if i + 2 < len(parts):
            return str(Path(*parts[i + 2 :]))
    return fp.name


def parse_txsd_meta(fp: Path) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Parse TXSD meta line (uccs_d1_scan90 format):
      # meta, firmware=..., cond_id=1, interval_ms=100, tag=fixed100, subject=...
    """
    try:
        with fp.open("r", encoding="utf-8", errors="ignore") as f:
            for _ in range(20):
                line = f.readline()
                if not line:
                    break
                if line.startswith("# meta,"):
                    cond_id = None
                    interval_ms = None
                    tag = None
                    m = re.search(r"cond_id=(\d+)", line)
                    if m:
                        cond_id = int(m.group(1))
                    m = re.search(r"interval_ms=(\d+)", line)
                    if m:
                        interval_ms = int(m.group(1))
                    m = re.search(r"tag=([^,\s]+)", line)
                    if m:
                        tag = m.group(1)
                    return cond_id, interval_ms, tag
    except OSError:
        pass
    return None, None, None


def parse_txsd_footer(fp: Path) -> Tuple[Optional[int], Optional[float], Optional[float], Optional[float], Optional[int]]:
    lines = fp.read_text(errors="ignore").splitlines()
    summary = next((l for l in reversed(lines) if l.startswith("# summary,")), None)
    diag = next((l for l in reversed(lines) if l.startswith("# diag,")), None)

    ms_total = None
    mean_p = None
    mean_v = None
    mean_i = None
    samples = None

    if summary:
        m = re.search(r"ms_total=(\d+)", summary)
        if m:
            ms_total = int(m.group(1))

    if diag:
        m = re.search(r"samples=(\d+)", diag)
        if m:
            samples = int(m.group(1))
        m = re.search(r"mean_v=([-0-9.]+)", diag)
        if m:
            mean_v = float(m.group(1))
        m = re.search(r"mean_i=([-0-9.]+)", diag)
        if m:
            mean_i = float(m.group(1))
        m = re.search(r"mean_p_mW=([-0-9.]+)", diag)
        if m:
            mean_p = float(m.group(1))

    return ms_total, mean_p, mean_v, mean_i, samples


def parse_txsd_trial(fp: Path, min_ms_total: int) -> TxsdTrial:
    cond_id, interval_ms, tag = parse_txsd_meta(fp)
    ms_total, mean_p, mean_v, mean_i, samples = parse_txsd_footer(fp)
    ok = bool(ms_total is not None and mean_p is not None and ms_total >= min_ms_total and (cond_id in {1, 2, 3}))
    return TxsdTrial(
        run=infer_run(fp),
        rel_path=infer_rel_path(fp),
        path=str(fp),
        cond_id=cond_id,
        interval_ms=interval_ms,
        tag=tag,
        ms_total=ms_total,
        mean_p_mw=mean_p,
        mean_v=mean_v,
        mean_i=mean_i,
        samples=samples,
        ok=ok,
    )


def parse_rx_trial(fp: Path, min_ms_total: int) -> RxTrial:
    condition_label: Optional[str] = None
    ms_total: Optional[int] = None
    rx = 0
    n_p100 = 0
    n_p500 = 0

    try:
        with fp.open("r", newline="", errors="ignore") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                if row[0].startswith("# condition_label="):
                    condition_label = row[0].split("=", 1)[1].strip()
                    continue
                if row[0].startswith("#") or row[0] == "ms":
                    continue
                try:
                    ms = int(row[0])
                except ValueError:
                    continue
                ms_total = ms if ms_total is None else max(ms_total, ms)
                if len(row) >= 5 and row[1] == "ADV":
                    rx += 1
                    if row[4] == "P100":
                        n_p100 += 1
                    elif row[4] == "P500":
                        n_p500 += 1
    except OSError:
        return RxTrial(
            run=infer_run(fp),
            rel_path=infer_rel_path(fp),
            path=str(fp),
            condition_label=None,
            ms_total=None,
            rx=0,
            rate_hz=None,
            n_p100=0,
            n_p500=0,
            ok=False,
        )

    rate_hz = (rx * 1000.0 / ms_total) if (ms_total and ms_total > 0) else None
    ok = bool(condition_label and ms_total is not None and ms_total >= min_ms_total and rate_hz is not None)
    return RxTrial(
        run=infer_run(fp),
        rel_path=infer_rel_path(fp),
        path=str(fp),
        condition_label=condition_label,
        ms_total=ms_total,
        rx=rx,
        rate_hz=rate_hz,
        n_p100=n_p100,
        n_p500=n_p500,
        ok=ok,
    )


def mean_std(vals: List[float]) -> Tuple[float, float]:
    if not vals:
        return float("nan"), float("nan")
    if len(vals) == 1:
        return vals[0], 0.0
    return statistics.mean(vals), statistics.stdev(vals)


def write_csv(path: Path, header: List[str], rows: List[List[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    base = repo / "uccs_d1_scan90"

    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=base / "data")
    ap.add_argument("--run", type=str, required=True, help="Run directory under data/ (e.g. 01)")
    ap.add_argument("--min-ms-total", type=int, default=50000, help="Filter out too-short trials (default 50s)")
    args = ap.parse_args()

    run_dir = args.data_root / args.run
    if not run_dir.exists():
        raise SystemExit(f"run not found: {run_dir}")

    # --- TXSD ---
    tx_dir = run_dir / "TX"
    tx_trials_all = [parse_txsd_trial(fp, args.min_ms_total) for fp in sorted(tx_dir.glob("trial_*.csv"))]
    tx_trials = [t for t in tx_trials_all if t.ok]

    # per-trial
    tx_trials_csv = base / "metrics" / args.run / "txsd_power_trials.csv"
    write_csv(
        tx_trials_csv,
        header=[
            "run",
            "rel_path",
            "cond_id",
            "interval_ms",
            "tag",
            "ms_total",
            "mean_p_mW",
            "mean_v",
            "mean_i",
            "samples",
            "ok",
        ],
        rows=[
            [
                t.run,
                t.rel_path,
                t.cond_id,
                t.interval_ms,
                t.tag,
                t.ms_total,
                t.mean_p_mw,
                t.mean_v,
                t.mean_i,
                t.samples,
                int(t.ok),
            ]
            for t in tx_trials_all
        ],
    )

    # summary per tag
    by_tag: Dict[str, List[TxsdTrial]] = {}
    for t in tx_trials:
        by_tag.setdefault(t.tag or "unknown", []).append(t)

    tx_summary_rows: List[List[object]] = []
    for tag, ts in sorted(by_tag.items()):
        ps = [t.mean_p_mw for t in ts if t.mean_p_mw is not None]
        ms = [float(t.ms_total or 0) for t in ts]
        mean_p, std_p = mean_std(ps)
        tx_summary_rows.append(
            [
                args.run,
                tag,
                len(ps),
                round(mean_p, 3),
                round(std_p, 3),
                round(statistics.mean(ms) if ms else float("nan"), 1),
            ]
        )

    tx_summary_csv = base / "metrics" / args.run / "txsd_power_summary.csv"
    write_csv(
        tx_summary_csv,
        header=["run", "tag", "n", "mean_p_mW", "std_p_mW", "ms_total_mean"],
        rows=tx_summary_rows,
    )

    # --- RX ---
    rx_dir = run_dir / "RX"
    rx_trials_all = [parse_rx_trial(fp, args.min_ms_total) for fp in sorted(rx_dir.glob("rx_trial_*.csv"))]
    rx_trials = [t for t in rx_trials_all if t.ok]

    rx_trials_csv = base / "metrics" / args.run / "rx_trials.csv"
    write_csv(
        rx_trials_csv,
        header=["run", "rel_path", "condition_label", "ms_total", "rx", "rate_hz", "n_p100", "n_p500", "ok"],
        rows=[
            [
                t.run,
                t.rel_path,
                t.condition_label,
                t.ms_total,
                t.rx,
                round(t.rate_hz, 4) if t.rate_hz is not None else None,
                t.n_p100,
                t.n_p500,
                int(t.ok),
            ]
            for t in rx_trials_all
        ],
    )

    by_cond: Dict[str, List[RxTrial]] = {}
    for t in rx_trials:
        by_cond.setdefault(t.condition_label or "unknown", []).append(t)

    rx_summary_rows: List[List[object]] = []
    for cond, ts in sorted(by_cond.items()):
        rates = [t.rate_hz for t in ts if t.rate_hz is not None]
        mean_r, std_r = mean_std([float(x) for x in rates])
        rx_summary_rows.append([args.run, cond, len(rates), round(mean_r, 3), round(std_r, 3)])

    rx_summary_csv = base / "metrics" / args.run / "rx_rate_summary.csv"
    write_csv(rx_summary_csv, header=["run", "condition_label", "n", "rate_hz_mean", "rate_hz_std"], rows=rx_summary_rows)

    # --- combined summary.md ---
    out_md = base / "metrics" / args.run / "summary.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)

    def find_mean(tag: str) -> Optional[float]:
        r = next((row for row in tx_summary_rows if row[1] == tag), None)
        return float(r[3]) if r else None

    p100 = find_mean("fixed100")
    p500 = find_mean("fixed500")
    ppol = find_mean("policy")

    share100_power = None
    if p100 is not None and p500 is not None and ppol is not None and (p100 - p500) != 0:
        share100_power = (ppol - p500) / (p100 - p500)

    policy_trials = [t for t in rx_trials if (t.condition_label or "").startswith("P")]
    share100_rx_list: List[float] = []
    for t in policy_trials:
        denom = t.n_p100 * 100 + t.n_p500 * 500
        if denom > 0:
            share100_rx_list.append((t.n_p100 * 100) / denom)
    share100_rx_mean = statistics.mean(share100_rx_list) if share100_rx_list else None
    share100_rx_std = statistics.stdev(share100_rx_list) if len(share100_rx_list) > 1 else 0.0 if share100_rx_list else None

    with out_md.open("w") as f:
        f.write(f"# uccs_d1_scan90 metrics ({args.run})\n\n")
        f.write("## Input\n\n")
        f.write(f"- RX: `{rx_dir}`\n")
        f.write(f"- TXSD: `{tx_dir}`\n")
        f.write(f"- Filter: `ms_total >= {args.min_ms_total}`\n\n")

        f.write("## Power (TXSD)\n\n")
        f.write("| tag | n | mean_p_mW | std_p_mW |\n")
        f.write("| --- | ---: | ---: | ---: |\n")
        for row in tx_summary_rows:
            _, tag, n, mean_p, std_p, _ms_mean = row
            f.write(f"| {tag} | {n} | {mean_p:.2f} | {std_p:.2f} |\n")
        f.write("\n")

        if p100 is not None and p500 is not None and ppol is not None:
            f.write(f"- ΔP (fixed100 - fixed500) = **{(p100 - p500):.2f} mW**\n")
            f.write(f"- ΔP (policy - fixed100) = **{(ppol - p100):.2f} mW**\n")
            f.write(f"- ΔP (policy - fixed500) = **{(ppol - p500):.2f} mW**\n")
        if share100_power is not None:
            f.write(f"- share100 (time-weight, from power mix) ≈ **{share100_power:.3f}**\n")
        f.write("\n")

        f.write("## RX rate\n\n")
        f.write("| condition_label | n | rate_hz_mean | rate_hz_std |\n")
        f.write("| --- | ---: | ---: | ---: |\n")
        for row in rx_summary_rows:
            _, cond, n, mean_r, std_r = row
            f.write(f"| {cond} | {n} | {mean_r:.2f} | {std_r:.2f} |\n")
        f.write("\n")

        f.write("## Policy mix (from RX labels)\n\n")
        f.write("- Policy RX files are labeled `P100`/`P500` (current interval).\n")
        if share100_rx_mean is not None:
            f.write(f"- share100 (time-weight, from RX counts) ≈ **{share100_rx_mean:.3f} ± {share100_rx_std:.3f}**\n")
        f.write("\n")

    print(f"Wrote:\n- {tx_trials_csv}\n- {tx_summary_csv}\n- {rx_trials_csv}\n- {rx_summary_csv}\n- {out_md}")


if __name__ == "__main__":
    main()

