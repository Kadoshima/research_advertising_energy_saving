#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Summarize DeltaE v3rig sweep RX/TXSD logs.

Usage:
  python scripts/analyze_deltae_v3rig_sweep.py --run-dir <run-dir> --out-dir results
"""
from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, median, pstdev, stdev
from typing import Iterable, Optional

import matplotlib
from scipy import stats

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


RX_RE = re.compile(r"^rx_(\d+)_([0-9a-fA-F]+)\.csv$")
TXSD_RE = re.compile(r"^pwr_(\d+)_([0-9a-fA-F]+)_sweep\.csv$")


@dataclass
class RxTrial:
    path: Path
    start_ms: int
    trial_index: Optional[int]
    rx_count: int
    rssi_values: list[int]


@dataclass
class TxsdTrial:
    path: Path
    start_ms: int
    ms_total: Optional[int]
    adv_count: Optional[int]
    e_total_mj: Optional[float]
    e_per_adv_uj: Optional[float]


def _safe_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_start_ms(name: str) -> Optional[int]:
    match = RX_RE.match(name)
    if match:
        return int(match.group(1))
    match = TXSD_RE.match(name)
    if match:
        return int(match.group(1))
    return None


def _read_rx_trial(path: Path) -> RxTrial:
    start_ms = _extract_start_ms(path.name) or -1
    trial_index = None
    rx_count = 0
    rssi_values: list[int] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("# meta"):
                for part in line.split(","):
                    part = part.strip()
                    if part.startswith("trial_index="):
                        trial_index = _safe_int(part.split("=", 1)[1])
            if line.startswith("#") or line.startswith("prog_id"):
                continue
            if not line.strip():
                continue
            rx_count += 1
            parts = line.strip().split(",")
            if len(parts) >= 4:
                rssi = _safe_int(parts[3])
                if rssi is not None:
                    rssi_values.append(rssi)
    return RxTrial(
        path=path,
        start_ms=start_ms,
        trial_index=trial_index,
        rx_count=rx_count,
        rssi_values=rssi_values,
    )


def _read_txsd_trial(path: Path) -> TxsdTrial:
    start_ms = _extract_start_ms(path.name) or -1
    ms_total = None
    adv_count = None
    e_total_mj = None
    e_per_adv_uj = None
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("# summary"):
                for part in line.split(","):
                    part = part.strip()
                    if part.startswith("ms_total="):
                        ms_total = _safe_int(part.split("=", 1)[1])
                    elif part.startswith("adv_count="):
                        adv_count = _safe_int(part.split("=", 1)[1])
                    elif part.startswith("E_total_mJ="):
                        e_total_mj = _safe_float(part.split("=", 1)[1])
                    elif part.startswith("E_per_adv_uJ="):
                        e_per_adv_uj = _safe_float(part.split("=", 1)[1])
    return TxsdTrial(
        path=path,
        start_ms=start_ms,
        ms_total=ms_total,
        adv_count=adv_count,
        e_total_mj=e_total_mj,
        e_per_adv_uj=e_per_adv_uj,
    )


def _infer_mode_ms(ms_total: Optional[int], adv_count: Optional[int]) -> Optional[int]:
    if adv_count is None or ms_total is None:
        return None
    if adv_count == 0:
        return 0
    ratio = ms_total / max(adv_count, 1)
    candidates = [100, 500, 1000, 2000]
    best = min(candidates, key=lambda x: abs(x - ratio))
    if abs(best - ratio) <= max(40.0, best * 0.4):
        return int(best)
    return None


def _pair_trials(
    rx_trials: list[RxTrial],
    txsd_trials: list[TxsdTrial],
) -> list[tuple[RxTrial, TxsdTrial]]:
    rx_sorted = sorted(rx_trials, key=lambda t: t.start_ms)
    tx_sorted = sorted(txsd_trials, key=lambda t: t.start_ms)
    if len(rx_sorted) != len(tx_sorted):
        raise ValueError(f"trial count mismatch: RX={len(rx_sorted)} TXSD={len(tx_sorted)}")
    return list(zip(rx_sorted, tx_sorted))


def _fmt(value: Optional[float], digits: int = 3) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def _stats(values: Iterable[float]) -> tuple[Optional[float], Optional[float]]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None, None
    if len(vals) == 1:
        return vals[0], None
    return mean(vals), pstdev(vals)


def _ci95(values: list[float]) -> tuple[Optional[float], Optional[float]]:
    if len(values) < 2:
        return None, None
    avg = mean(values)
    sd = stdev(values)
    se = sd / (len(values) ** 0.5)
    tcrit = stats.t.ppf(0.975, df=len(values) - 1)
    return avg - tcrit * se, avg + tcrit * se


def _welch_ci_diff(a: list[float], b: list[float]) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    if len(a) < 2 or len(b) < 2:
        return None, None, None, None
    mean_a = mean(a)
    mean_b = mean(b)
    var_a = stdev(a) ** 2
    var_b = stdev(b) ** 2
    diff = mean_a - mean_b
    se = (var_a / len(a) + var_b / len(b)) ** 0.5
    df_num = (var_a / len(a) + var_b / len(b)) ** 2
    df_den = (var_a ** 2) / ((len(a) ** 2) * (len(a) - 1)) + (var_b ** 2) / ((len(b) ** 2) * (len(b) - 1))
    df = df_num / df_den if df_den else None
    if df is None:
        return diff, None, None, None
    tcrit = stats.t.ppf(0.975, df=df)
    return diff, diff - tcrit * se, diff + tcrit * se, df


def _cohens_d(a: list[float], b: list[float]) -> Optional[float]:
    if len(a) < 2 or len(b) < 2:
        return None
    var_a = stdev(a) ** 2
    var_b = stdev(b) ** 2
    pooled = (((len(a) - 1) * var_a) + ((len(b) - 1) * var_b)) / (len(a) + len(b) - 2)
    if pooled <= 0:
        return None
    return (mean(a) - mean(b)) / (pooled ** 0.5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    rx_dir = run_dir / "RX"
    txsd_dir = run_dir / "TXSD"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rx_trials = [_read_rx_trial(p) for p in sorted(rx_dir.glob("rx_*.csv"))]
    txsd_trials = [_read_txsd_trial(p) for p in sorted(txsd_dir.glob("pwr_*_sweep.csv"))]
    paired = _pair_trials(rx_trials, txsd_trials)

    trial_rows: list[dict[str, object]] = []
    for idx, (rx, tx) in enumerate(paired, start=1):
        mode_ms = _infer_mode_ms(tx.ms_total, tx.adv_count)
        pdr = None
        if tx.adv_count and tx.adv_count > 0:
            pdr = rx.rx_count / tx.adv_count
        rssi_med = median(rx.rssi_values) if rx.rssi_values else None
        rssi_mean = mean(rx.rssi_values) if rx.rssi_values else None
        trial_rows.append({
            "trial_index": idx,
            "start_ms_rx": rx.start_ms,
            "start_ms_txsd": tx.start_ms,
            "start_ms_delta": tx.start_ms - rx.start_ms,
            "mode_ms": mode_ms,
            "adv_count": tx.adv_count,
            "rx_count": rx.rx_count,
            "pdr": pdr,
            "rssi_median": rssi_med,
            "rssi_mean": rssi_mean,
            "ms_total": tx.ms_total,
            "e_total_mj": tx.e_total_mj,
            "e_per_adv_uj": tx.e_per_adv_uj,
            "rx_zero": rx.rx_count == 0,
        })

    trials_csv = out_dir / f"{run_dir.name}_trials.csv"
    with trials_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(trial_rows[0].keys()))
        writer.writeheader()
        writer.writerows(trial_rows)

    mode_groups: dict[str, list[dict[str, object]]] = {}
    for row in trial_rows:
        mode_ms = row["mode_ms"]
        mode_key = "OFF" if mode_ms == 0 else str(mode_ms) if mode_ms is not None else "None"
        mode_groups.setdefault(mode_key, []).append(row)

    summary_csv = out_dir / f"{run_dir.name}_mode_summary.csv"
    with summary_csv.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = [
            "mode",
            "n_trials",
            "rx_zero_trials",
            "e_total_mj_mean",
            "e_total_mj_std",
            "e_per_adv_uj_mean",
            "e_per_adv_uj_std",
            "pdr_mean",
            "pdr_std",
            "rssi_median_mean",
            "rssi_median_std",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for mode, rows in sorted(mode_groups.items(), key=lambda x: x[0]):
            e_total = [r["e_total_mj"] for r in rows if r["e_total_mj"] is not None]
            e_per_adv = [r["e_per_adv_uj"] for r in rows if r["e_per_adv_uj"] is not None and r["adv_count"]]
            pdrs = [r["pdr"] for r in rows if r["pdr"] is not None]
            rssi_meds = [r["rssi_median"] for r in rows if r["rssi_median"] is not None]
            e_total_mean, e_total_std = _stats(e_total)
            e_per_mean, e_per_std = _stats(e_per_adv)
            pdr_mean, pdr_std = _stats(pdrs)
            rssi_mean, rssi_std = _stats(rssi_meds)
            writer.writerow({
                "mode": mode,
                "n_trials": len(rows),
                "rx_zero_trials": sum(1 for r in rows if r["rx_zero"]),
                "e_total_mj_mean": _fmt(e_total_mean),
                "e_total_mj_std": _fmt(e_total_std),
                "e_per_adv_uj_mean": _fmt(e_per_mean),
                "e_per_adv_uj_std": _fmt(e_per_std),
                "pdr_mean": _fmt(pdr_mean),
                "pdr_std": _fmt(pdr_std),
                "rssi_median_mean": _fmt(rssi_mean, 2),
                "rssi_median_std": _fmt(rssi_std, 2),
            })

    stats_csv = out_dir / f"{run_dir.name}_stats_ci.csv"
    with stats_csv.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = [
            "metric",
            "mode",
            "n",
            "mean",
            "std",
            "ci95_low",
            "ci95_high",
            "note",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for mode, rows in sorted(mode_groups.items(), key=lambda x: x[0]):
            e_total = [r["e_total_mj"] for r in rows if r["e_total_mj"] is not None]
            pdrs = [r["pdr"] for r in rows if r["pdr"] is not None]
            rssi_meds = [r["rssi_median"] for r in rows if r["rssi_median"] is not None]
            if e_total:
                ci_low, ci_high = _ci95(e_total)
                writer.writerow({
                    "metric": "e_total_mj",
                    "mode": mode,
                    "n": len(e_total),
                    "mean": _fmt(mean(e_total)),
                    "std": _fmt(stdev(e_total) if len(e_total) > 1 else None),
                    "ci95_low": _fmt(ci_low),
                    "ci95_high": _fmt(ci_high),
                    "note": "t CI (assumes normal)",
                })
            if pdrs:
                ci_low, ci_high = _ci95(pdrs)
                writer.writerow({
                    "metric": "pdr",
                    "mode": mode,
                    "n": len(pdrs),
                    "mean": _fmt(mean(pdrs), 3),
                    "std": _fmt(stdev(pdrs) if len(pdrs) > 1 else None, 3),
                    "ci95_low": _fmt(ci_low, 3),
                    "ci95_high": _fmt(ci_high, 3),
                    "note": "t CI (assumes normal)",
                })
            if rssi_meds:
                ci_low, ci_high = _ci95(rssi_meds)
                writer.writerow({
                    "metric": "rssi_median",
                    "mode": mode,
                    "n": len(rssi_meds),
                    "mean": _fmt(mean(rssi_meds), 2),
                    "std": _fmt(stdev(rssi_meds) if len(rssi_meds) > 1 else None, 2),
                    "ci95_low": _fmt(ci_low, 2),
                    "ci95_high": _fmt(ci_high, 2),
                    "note": "t CI (assumes normal)",
                })

        off_e = [r["e_total_mj"] for r in mode_groups.get("OFF", []) if r["e_total_mj"] is not None]
        for mode in ["100", "500", "1000", "2000"]:
            e_vals = [r["e_total_mj"] for r in mode_groups.get(mode, []) if r["e_total_mj"] is not None]
            if not e_vals or not off_e:
                continue
            diff, ci_low, ci_high, df = _welch_ci_diff(e_vals, off_e)
            d = _cohens_d(e_vals, off_e)
            writer.writerow({
                "metric": "delta_e_total_mj_vs_off",
                "mode": mode,
                "n": len(e_vals),
                "mean": _fmt(diff),
                "std": "",
                "ci95_low": _fmt(ci_low),
                "ci95_high": _fmt(ci_high),
                "note": f"Welch CI, df={_fmt(df, 1)}, Cohen_d={_fmt(d, 3)}",
            })

    # RX zero-row check table
    zero_check_csv = out_dir / f"{run_dir.name}_rx_zero_check.csv"
    with zero_check_csv.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = [
            "trial_index",
            "mode_ms",
            "adv_count",
            "rx_count",
            "rx_zero",
            "start_ms_rx",
            "start_ms_txsd",
            "start_ms_delta",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in trial_rows:
            writer.writerow({k: row[k] for k in fieldnames})

    zero_summary_csv = out_dir / f"{run_dir.name}_rx_zero_by_mode.csv"
    with zero_summary_csv.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = ["mode", "n_trials", "rx_zero_trials", "rx_zero_pct", "adv_zero_trials"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for mode, rows in sorted(mode_groups.items(), key=lambda x: x[0]):
            rx_zero_trials = sum(1 for r in rows if r["rx_zero"])
            adv_zero_trials = sum(1 for r in rows if (r["adv_count"] or 0) == 0)
            rx_zero_pct = rx_zero_trials / len(rows) if rows else 0
            writer.writerow({
                "mode": mode,
                "n_trials": len(rows),
                "rx_zero_trials": rx_zero_trials,
                "rx_zero_pct": _fmt(rx_zero_pct, 3),
                "adv_zero_trials": adv_zero_trials,
            })

    now = datetime.now().strftime("%Y-%m-%d")
    rx_zero = sum(1 for r in trial_rows if r["rx_zero"])
    off_trials = mode_groups.get("OFF", [])
    off_e = [r["e_total_mj"] for r in off_trials if r["e_total_mj"] is not None]
    off_mean = mean(off_e) if off_e else None

    md_path = out_dir / f"{run_dir.name}_summary.md"
    with md_path.open("w", encoding="utf-8-sig") as fh:
        fh.write(f"# ΔE v3rig sweep まとめ ({run_dir.name})\n\n")
        fh.write("## 生成情報\n")
        fh.write(f"- 生成日: {now}\n")
        fh.write("- 生成スクリプト: `scripts/analyze_deltae_v3rig_sweep.py`\n")
        fh.write(f"- 参照データ: `{run_dir}`\n")
        fh.write("\n## 収集状況\n")
        fh.write(f"- RX: 50 files (0行={rx_zero})\n")
        fh.write("- TXSD: 50 files\n")
        fh.write("\n## モード別サマリ（mean±std）\n")
        fh.write("- 詳細: `")
        fh.write(str(summary_csv).replace("\\", "/"))
        fh.write("`\n")
        fh.write("\n## ΔE（E_on − E_off）\n")
        fh.write("- OFF平均E_total_mJ: ")
        fh.write(_fmt(off_mean) if off_mean is not None else "n/a")
        fh.write("\n")
        for mode in ["100", "500", "1000", "2000"]:
            rows = mode_groups.get(mode, [])
            e_vals = [r["e_total_mj"] for r in rows if r["e_total_mj"] is not None]
            if not e_vals or off_mean is None:
                delta = None
            else:
                delta = mean(e_vals) - off_mean
            fh.write(f"- {mode}ms: ΔE_mJ={_fmt(delta)} (n={len(rows)})\n")
        fh.write("\n## PDR/RSSI\n")
        fh.write("- PDR/RSSIのモード別集計は `")
        fh.write(str(summary_csv).replace("\\", "/"))
        fh.write("` を参照\n")
        fh.write("\n## 備考\n")
        fh.write("- RX 0行ファイルは主にOFFモードと一致する可能性が高い（trial一覧で要確認）\n")
        fh.write("- 95% CIは `")
        fh.write(str(stats_csv).replace("\\", "/"))
        fh.write("` を参照（t分布/正規性仮定）\n")

    # Plots
    def _plot_bar(
        labels: list[str],
        values: list[float],
        errors: Optional[list[float]],
        title: str,
        ylabel: str,
        out_path: Path,
    ) -> None:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(labels, values, yerr=errors, capsize=4, color="#4C78A8")
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)

    mode_order = ["OFF", "100", "500", "1000", "2000"]
    energy_means = []
    energy_stds = []
    labels = []
    for mode in mode_order:
        rows = mode_groups.get(mode, [])
        e_vals = [r["e_total_mj"] for r in rows if r["e_total_mj"] is not None]
        if not e_vals:
            continue
        labels.append(mode)
        energy_means.append(mean(e_vals))
        energy_stds.append(pstdev(e_vals) if len(e_vals) > 1 else 0.0)
    _plot_bar(
        labels,
        energy_means,
        energy_stds,
        "E_total per mode",
        "E_total_mJ",
        out_dir / f"{run_dir.name}_plot_e_total_mJ.png",
    )

    delta_labels = []
    delta_vals = []
    for mode in ["100", "500", "1000", "2000"]:
        rows = mode_groups.get(mode, [])
        e_vals = [r["e_total_mj"] for r in rows if r["e_total_mj"] is not None]
        if not e_vals or off_mean is None:
            continue
        delta_labels.append(mode)
        delta_vals.append(mean(e_vals) - off_mean)
    _plot_bar(
        delta_labels,
        delta_vals,
        None,
        "DeltaE (E_on - E_off)",
        "DeltaE_mJ",
        out_dir / f"{run_dir.name}_plot_deltaE_mJ.png",
    )

    pdr_labels = []
    pdr_means = []
    pdr_stds = []
    for mode in ["100", "500", "1000", "2000"]:
        rows = mode_groups.get(mode, [])
        pdrs = [r["pdr"] for r in rows if r["pdr"] is not None]
        if not pdrs:
            continue
        pdr_labels.append(mode)
        pdr_means.append(mean(pdrs))
        pdr_stds.append(pstdev(pdrs) if len(pdrs) > 1 else 0.0)
    _plot_bar(
        pdr_labels,
        pdr_means,
        pdr_stds,
        "PDR per mode",
        "PDR",
        out_dir / f"{run_dir.name}_plot_pdr.png",
    )

    rssi_labels = []
    rssi_means = []
    rssi_stds = []
    for mode in ["100", "500", "1000", "2000"]:
        rows = mode_groups.get(mode, [])
        medians = [r["rssi_median"] for r in rows if r["rssi_median"] is not None]
        if not medians:
            continue
        rssi_labels.append(mode)
        rssi_means.append(mean(medians))
        rssi_stds.append(pstdev(medians) if len(medians) > 1 else 0.0)
    _plot_bar(
        rssi_labels,
        rssi_means,
        rssi_stds,
        "RSSI median per mode",
        "RSSI (dBm)",
        out_dir / f"{run_dir.name}_plot_rssi_median.png",
    )


if __name__ == "__main__":
    main()
