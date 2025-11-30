#!/usr/bin/env python3
"""
Baseline計測データ解析スクリプト v2

Usage:
  python scripts/analyze_baseline_v2.py \
    --on-dir "data/実験データ/研究室/row_1129_on/TX" \
    --off-dir "data/実験データ/研究室/row_1129_off/TX" \
    --rx-dir "data/実験データ/研究室/row_1129_on/RX" \
    --out results/baseline_analysis_1129.md

機能:
  - OFF計測からP_offを算出
  - ON計測をinterval別にグループ化してΔE/advを算出
  - RX計測からPDRを算出
  - 結果をMarkdown形式で出力
"""

import argparse
import glob
import os
import re
import statistics as stats
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime


@dataclass
class TrialData:
    """1トライアルのデータ"""
    filename: str
    ms_total: float = 0.0
    adv_count: int = 0
    e_total_mJ: float = 0.0
    e_per_adv_uJ: float = 0.0
    samples: int = 0
    rate_hz: float = 0.0
    mean_v: float = 0.0
    mean_i_mA: float = 0.0
    mean_p_mW: float = 0.0
    adv_interval_ms: int = 0
    parse_drop: int = 0


@dataclass
class RxTrialData:
    """RXトライアルのデータ"""
    filename: str
    ms_total: float = 0.0
    rx_count: int = 0
    rate_hz: float = 0.0
    est_pdr: float = 0.0
    adv_interval_ms: int = 0


def parse_trial_csv(path: str) -> Optional[TrialData]:
    """CSVファイルからトライアルデータを抽出"""
    data = TrialData(filename=os.path.basename(path))

    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()

                # meta行からadv_interval_msを取得
                if line.startswith('# meta'):
                    m = re.search(r'adv_interval_ms=(\d+)', line)
                    if m:
                        data.adv_interval_ms = int(m.group(1))

                # summary行
                elif line.startswith('# summary'):
                    for pattern, attr, conv in [
                        (r'ms_total=([0-9.]+)', 'ms_total', float),
                        (r'adv_count=(\d+)', 'adv_count', int),
                        (r'E_total_mJ=([0-9.]+)', 'e_total_mJ', float),
                        (r'E_per_adv_uJ=([0-9.]+)', 'e_per_adv_uJ', float),
                    ]:
                        m = re.search(pattern, line)
                        if m:
                            setattr(data, attr, conv(m.group(1)))

                # diag行 (最初のdiag行)
                elif line.startswith('# diag') and data.samples == 0:
                    for pattern, attr, conv in [
                        (r'samples=(\d+)', 'samples', int),
                        (r'rate_hz=([0-9.]+)', 'rate_hz', float),
                        (r'mean_v=([0-9.]+)', 'mean_v', float),
                        (r'mean_i=([0-9.]+)', 'mean_i_mA', float),
                        (r'mean_p_mW=([0-9.]+)', 'mean_p_mW', float),
                        (r'parse_drop=(\d+)', 'parse_drop', int),
                    ]:
                        m = re.search(pattern, line)
                        if m:
                            setattr(data, attr, conv(m.group(1)))

        return data
    except Exception as e:
        print(f"Warning: Failed to parse {path}: {e}")
        return None


def parse_rx_csv(path: str) -> Optional[RxTrialData]:
    """RX CSVファイルからデータを抽出"""
    data = RxTrialData(filename=os.path.basename(path))

    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # meta行からadv_interval_msを取得
        m = re.search(r'adv_interval_ms=(\d+)', content)
        if m:
            data.adv_interval_ms = int(m.group(1))

        # データ行をカウント（ADVイベント）
        rx_count = len(re.findall(r'^\d+,ADV,', content, re.MULTILINE))
        data.rx_count = rx_count

        # 最後のタイムスタンプを取得
        matches = re.findall(r'^(\d+),ADV,', content, re.MULTILINE)
        if matches:
            data.ms_total = float(matches[-1])

        if data.ms_total > 0:
            data.rate_hz = data.rx_count / (data.ms_total / 1000.0)
            if data.adv_interval_ms > 0:
                expected = data.ms_total / data.adv_interval_ms
                data.est_pdr = data.rx_count / expected if expected > 0 else 0.0

        return data
    except Exception as e:
        print(f"Warning: Failed to parse RX {path}: {e}")
        return None


def collect_trials(dir_path: str, pattern: str = "trial_*.csv") -> List[TrialData]:
    """ディレクトリからトライアルデータを収集"""
    trials = []
    for f in sorted(glob.glob(os.path.join(dir_path, pattern))):
        data = parse_trial_csv(f)
        if data and data.samples > 0:  # 有効なデータのみ
            trials.append(data)
    return trials


def collect_rx_trials(dir_path: str, pattern: str = "rx_trial_*.csv") -> List[RxTrialData]:
    """RXディレクトリからデータを収集"""
    trials = []
    for f in sorted(glob.glob(os.path.join(dir_path, pattern))):
        data = parse_rx_csv(f)
        if data and data.rx_count > 0:
            trials.append(data)
    return trials


def group_by_interval(trials: List[TrialData]) -> Dict[int, List[TrialData]]:
    """interval別にグループ化"""
    groups: Dict[int, List[TrialData]] = {}
    for t in trials:
        interval = t.adv_interval_ms
        if interval not in groups:
            groups[interval] = []
        groups[interval].append(t)
    return groups


def mean_std(values: List[float]) -> Tuple[float, float]:
    """平均と標準偏差を計算"""
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return stats.mean(values), stats.pstdev(values)


def generate_report(
    off_trials: List[TrialData],
    on_trials: List[TrialData],
    rx_trials: List[RxTrialData],
    off_dir: str,
    on_dir: str,
    rx_dir: Optional[str]
) -> str:
    """Markdownレポートを生成"""
    lines = []

    # ヘッダー
    lines.append("# Baseline計測 解析結果")
    lines.append("")
    lines.append(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # データソース
    lines.append("## 1. データソース")
    lines.append("")
    lines.append(f"- OFF計測: `{off_dir}`")
    lines.append(f"- ON計測: `{on_dir}`")
    if rx_dir:
        lines.append(f"- RX計測: `{rx_dir}`")
    lines.append("")

    # OFF計測結果
    lines.append("## 2. OFF計測結果 (P_off)")
    lines.append("")
    if off_trials:
        p_off_values = [t.mean_p_mW for t in off_trials]
        e_off_values = [t.e_total_mJ for t in off_trials]
        i_off_values = [t.mean_i_mA for t in off_trials]

        p_mean, p_std = mean_std(p_off_values)
        e_mean, e_std = mean_std(e_off_values)
        i_mean, i_std = mean_std(i_off_values)

        lines.append(f"- トライアル数: {len(off_trials)}")
        lines.append(f"- **P_off (平均)**: {p_mean:.2f} ± {p_std:.2f} mW")
        lines.append(f"- 平均電流: {i_mean:.2f} ± {i_std:.2f} mA")
        lines.append(f"- E_total (平均): {e_mean:.2f} ± {e_std:.2f} mJ")
        lines.append("")

        # 詳細テーブル
        lines.append("### OFF詳細")
        lines.append("")
        lines.append("| Trial | ms_total | samples | mean_i [mA] | mean_p [mW] | E_total [mJ] | parse_drop |")
        lines.append("|-------|----------|---------|-------------|-------------|--------------|------------|")
        for t in off_trials:
            lines.append(f"| {t.filename} | {t.ms_total:.0f} | {t.samples} | {t.mean_i_mA:.2f} | {t.mean_p_mW:.2f} | {t.e_total_mJ:.2f} | {t.parse_drop} |")
        lines.append("")
    else:
        lines.append("OFF計測データがありません。")
        lines.append("")
        p_mean = 0.0

    # ON計測結果 (interval別)
    lines.append("## 3. ON計測結果 (interval別)")
    lines.append("")

    on_groups = group_by_interval(on_trials)

    if on_groups:
        # サマリーテーブル
        lines.append("### ΔE/adv サマリー")
        lines.append("")
        lines.append("| Interval [ms] | Trials | E_on [mJ] | E_off [mJ] | ΔE [mJ] | N_adv | ΔE/adv [µJ] | mean_i [mA] |")
        lines.append("|---------------|--------|-----------|------------|---------|-------|-------------|-------------|")

        summary_data = []
        for interval in sorted(on_groups.keys()):
            trials = on_groups[interval]
            e_on_values = [t.e_total_mJ for t in trials]
            adv_values = [t.adv_count for t in trials]
            i_values = [t.mean_i_mA for t in trials]
            ms_values = [t.ms_total for t in trials]

            e_on_mean, _ = mean_std(e_on_values)
            adv_mean = stats.mean(adv_values) if adv_values else 0
            i_mean, _ = mean_std(i_values)
            ms_mean = stats.mean(ms_values) if ms_values else 0

            # P_off × T で補正
            t_sec = ms_mean / 1000.0
            e_off_adjusted = p_mean * t_sec / 1000.0  # mW * s / 1000 = mJ

            delta_e = e_on_mean - e_off_adjusted
            delta_e_per_adv = (delta_e * 1000.0 / adv_mean) if adv_mean > 0 else 0.0  # µJ

            lines.append(f"| {interval} | {len(trials)} | {e_on_mean:.2f} | {e_off_adjusted:.2f} | {delta_e:.2f} | {adv_mean:.0f} | {delta_e_per_adv:.2f} | {i_mean:.2f} |")

            summary_data.append({
                'interval': interval,
                'trials': len(trials),
                'delta_e_per_adv_uJ': delta_e_per_adv,
                'mean_i_mA': i_mean,
            })

        lines.append("")

        # interval別詳細
        for interval in sorted(on_groups.keys()):
            trials = on_groups[interval]
            lines.append(f"### ON {interval}ms 詳細")
            lines.append("")
            lines.append("| Trial | ms_total | adv_count | E_total [mJ] | E/adv [µJ] | mean_i [mA] | parse_drop |")
            lines.append("|-------|----------|-----------|--------------|------------|-------------|------------|")
            for t in trials:
                lines.append(f"| {t.filename} | {t.ms_total:.0f} | {t.adv_count} | {t.e_total_mJ:.2f} | {t.e_per_adv_uJ:.2f} | {t.mean_i_mA:.2f} | {t.parse_drop} |")
            lines.append("")
    else:
        lines.append("ON計測データがありません。")
        lines.append("")

    # RX計測結果 (PDR)
    if rx_trials:
        lines.append("## 4. RX計測結果 (PDR)")
        lines.append("")

        rx_groups: Dict[int, List[RxTrialData]] = {}
        for t in rx_trials:
            interval = t.adv_interval_ms
            if interval not in rx_groups:
                rx_groups[interval] = []
            rx_groups[interval].append(t)

        lines.append("### PDR サマリー")
        lines.append("")
        lines.append("| Interval [ms] | Trials | RX count (avg) | Rate [Hz] | PDR (est) |")
        lines.append("|---------------|--------|----------------|-----------|-----------|")

        for interval in sorted(rx_groups.keys()):
            trials = rx_groups[interval]
            rx_counts = [t.rx_count for t in trials]
            rates = [t.rate_hz for t in trials]
            pdrs = [t.est_pdr for t in trials]

            rx_mean, _ = mean_std([float(x) for x in rx_counts])
            rate_mean, _ = mean_std(rates)
            pdr_mean, _ = mean_std(pdrs)

            lines.append(f"| {interval} | {len(trials)} | {rx_mean:.1f} | {rate_mean:.2f} | {pdr_mean:.3f} |")

        lines.append("")

    # 計算式の説明
    lines.append("## 5. 計算式")
    lines.append("")
    lines.append("```")
    lines.append("ΔE/adv = (E_total_ON - P_off × T) / N_adv")
    lines.append("")
    lines.append("E_total_ON : ON計測の総エネルギー [mJ]")
    lines.append("P_off      : OFF計測の平均電力 [mW]")
    lines.append("T          : ON計測の時間 [s]")
    lines.append("N_adv      : 広告送信回数 (TICK計測)")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Baseline計測データ解析")
    parser.add_argument("--on-dir", required=True, help="ON計測データディレクトリ")
    parser.add_argument("--off-dir", required=True, help="OFF計測データディレクトリ")
    parser.add_argument("--rx-dir", help="RX計測データディレクトリ (オプション)")
    parser.add_argument("--out", help="出力ファイルパス (省略時は標準出力)")
    args = parser.parse_args()

    print(f"Loading OFF data from: {args.off_dir}")
    off_trials = collect_trials(args.off_dir, "trial_*_off.csv")
    if not off_trials:
        off_trials = collect_trials(args.off_dir, "trial_*.csv")
    print(f"  Found {len(off_trials)} OFF trials")

    print(f"Loading ON data from: {args.on_dir}")
    on_trials = collect_trials(args.on_dir, "trial_*_on.csv")
    if not on_trials:
        on_trials = collect_trials(args.on_dir, "trial_*.csv")
    print(f"  Found {len(on_trials)} ON trials")

    rx_trials = []
    if args.rx_dir:
        print(f"Loading RX data from: {args.rx_dir}")
        rx_trials = collect_rx_trials(args.rx_dir)
        print(f"  Found {len(rx_trials)} RX trials")

    report = generate_report(
        off_trials, on_trials, rx_trials,
        args.off_dir, args.on_dir, args.rx_dir
    )

    if args.out:
        os.makedirs(os.path.dirname(args.out) if os.path.dirname(args.out) else ".", exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Report saved to: {args.out}")
    else:
        print("")
        print(report)


if __name__ == "__main__":
    main()
