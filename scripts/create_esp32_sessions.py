#!/usr/bin/env python3
"""
ESP32再生用セッションCSV生成

生成済みCCS時系列から15分セッションを抽出し、
ESP32で再生可能なフォーマットに変換する。

Usage:
    python scripts/create_esp32_sessions.py --input data/ccs_sequences/ --output data/esp32_sessions/
"""

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd


# =============================================================================
# 定数
# =============================================================================
SESSION_DURATION_S = 10 * 60  # 10分 = 600秒（mHealthデータ制約により15分→10分に変更）
WINDOW_STRIDE_S = 1.0         # CCSデータの時間間隔


def load_ccs_data(input_dir: Path) -> dict:
    """全被験者のCCSデータを読み込み"""
    data = {}
    for i in range(1, 11):
        csv_path = input_dir / f"subject{i:02d}_ccs.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            data[i] = df
    return data


def analyze_segment(df: pd.DataFrame, start_idx: int, end_idx: int) -> dict:
    """セグメントの統計を計算"""
    seg = df.iloc[start_idx:end_idx]

    intervals = seg['interval_ms'].values
    n_trans = np.sum(intervals[1:] != intervals[:-1])

    return {
        "start_idx": start_idx,
        "end_idx": end_idx,
        "duration_s": len(seg) * WINDOW_STRIDE_S,
        "ccs_mean": seg['ccs'].mean(),
        "ccs_std": seg['ccs'].std(),
        "ccs_min": seg['ccs'].min(),
        "ccs_max": seg['ccs'].max(),
        "interval_dist": {
            "100ms": int((intervals == 100).sum()),
            "500ms": int((intervals == 500).sum()),
            "2000ms": int((intervals == 2000).sum()),
        },
        "n_transitions": int(n_trans),
    }


def select_best_sessions(all_data: dict, n_sessions: int = 10) -> list:
    """
    最適なセッションを選定

    基準:
    1. 遷移回数が適度（5-50回）
    2. CCS範囲が広い（0.3-0.9をカバー）
    3. 3つの間隔が全て出現
    """
    candidates = []

    for subject_id, df in all_data.items():
        n_windows = len(df)
        session_windows = int(SESSION_DURATION_S / WINDOW_STRIDE_S)

        # スライディングウィンドウで候補を生成
        for start in range(0, n_windows - session_windows + 1, session_windows // 2):
            end = start + session_windows
            if end > n_windows:
                break

            stats = analyze_segment(df, start, end)
            stats["subject_id"] = subject_id

            # スコアリング
            # 遷移回数: 10-30が理想
            trans_score = 1.0 - abs(stats["n_transitions"] - 20) / 40
            trans_score = max(0, trans_score)

            # 間隔の多様性
            dist = stats["interval_dist"]
            diversity_score = (
                (1 if dist["100ms"] > 0 else 0) +
                (1 if dist["500ms"] > 0 else 0) +
                (1 if dist["2000ms"] > 0 else 0)
            ) / 3

            # CCS範囲
            range_score = min(1.0, (stats["ccs_max"] - stats["ccs_min"]) / 0.5)

            stats["score"] = 0.4 * trans_score + 0.3 * diversity_score + 0.3 * range_score
            candidates.append(stats)

    # スコア順にソート
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # 被験者の重複を避けつつ選定
    selected = []
    used_subjects = {}

    for cand in candidates:
        if len(selected) >= n_sessions:
            break
        # 同じ被験者から2つまで
        subj = cand["subject_id"]
        if used_subjects.get(subj, 0) < 2:
            selected.append(cand)
            used_subjects[subj] = used_subjects.get(subj, 0) + 1

    return selected


def create_esp32_csv(df: pd.DataFrame, start_idx: int, end_idx: int, output_path: Path):
    """ESP32再生用CSVを出力"""
    seg = df.iloc[start_idx:end_idx].copy()

    # タイムスタンプを0からリセット
    seg['timestamp_ms'] = (np.arange(len(seg)) * WINDOW_STRIDE_S * 1000).astype(int)

    # ESP32用フォーマット: timestamp_ms, interval_ms, ccs, u, s
    esp32_df = seg[['timestamp_ms', 'interval_ms', 'ccs', 'u', 's']].copy()

    esp32_df.to_csv(output_path, index=False)


def main():
    parser = argparse.ArgumentParser(description="Create ESP32 session files")
    parser.add_argument("--input", type=Path, default=Path("data/ccs_sequences"),
                        help="Input directory with CCS CSV files")
    parser.add_argument("--output", type=Path, default=Path("data/esp32_sessions"),
                        help="Output directory for ESP32 session files")
    parser.add_argument("--n-sessions", type=int, default=10,
                        help="Number of sessions to create")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    # データ読み込み
    print("Loading CCS data...")
    all_data = load_ccs_data(args.input)
    print(f"Loaded {len(all_data)} subjects")

    # セッション選定
    print(f"\nSelecting {args.n_sessions} best sessions...")
    selected = select_best_sessions(all_data, args.n_sessions)

    # セッション出力
    print("\nCreating ESP32 session files:")
    session_info = []

    for i, sess in enumerate(selected, 1):
        subject_id = sess["subject_id"]
        df = all_data[subject_id]

        output_path = args.output / f"session_{i:02d}.csv"
        create_esp32_csv(df, sess["start_idx"], sess["end_idx"], output_path)

        info = {
            "session_id": i,
            "source_subject": subject_id,
            "start_idx": sess["start_idx"],
            "end_idx": sess["end_idx"],
            "duration_s": sess["duration_s"],
            "ccs_mean": round(sess["ccs_mean"], 3),
            "ccs_range": f"{sess['ccs_min']:.2f}-{sess['ccs_max']:.2f}",
            "n_transitions": sess["n_transitions"],
            "interval_dist": sess["interval_dist"],
            "score": round(sess["score"], 3),
            "output_path": str(output_path),
        }
        session_info.append(info)

        print(f"  Session {i:02d}: Subject {subject_id:02d}, "
              f"CCS={sess['ccs_mean']:.2f}, trans={sess['n_transitions']}, "
              f"score={sess['score']:.2f}")

    # サマリ保存
    summary_path = args.output / "session_manifest.json"
    with open(summary_path, 'w') as f:
        json.dump(session_info, f, indent=2)
    print(f"\nManifest saved to {summary_path}")

    # レポート生成
    report_path = args.output / "session_selection_report.md"
    with open(report_path, 'w') as f:
        f.write("# ESP32セッション選定レポート\n\n")
        f.write(f"生成日: 2025-11-27\n\n")
        f.write("## 選定基準\n\n")
        f.write("1. 遷移回数が適度（10-30回が理想）\n")
        f.write("2. 間隔の多様性（100/500/2000msが全て出現）\n")
        f.write("3. CCS範囲が広い\n\n")
        f.write("## 選定結果\n\n")
        f.write("| Session | Subject | Duration | CCS Mean | CCS Range | Transitions | Score |\n")
        f.write("|---------|---------|----------|----------|-----------|-------------|-------|\n")
        for info in session_info:
            f.write(f"| {info['session_id']:02d} | {info['source_subject']:02d} | "
                    f"{info['duration_s']:.0f}s | {info['ccs_mean']:.3f} | "
                    f"{info['ccs_range']} | {info['n_transitions']} | {info['score']:.3f} |\n")
        f.write("\n## 間隔分布\n\n")
        for info in session_info:
            dist = info['interval_dist']
            total = sum(dist.values())
            f.write(f"- Session {info['session_id']:02d}: "
                    f"100ms={dist['100ms']} ({100*dist['100ms']/total:.1f}%), "
                    f"500ms={dist['500ms']} ({100*dist['500ms']/total:.1f}%), "
                    f"2000ms={dist['2000ms']} ({100*dist['2000ms']/total:.1f}%)\n")

    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    main()
