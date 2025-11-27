#!/usr/bin/env python3
"""
CCS時系列生成パイプライン

mHealthの前処理済みデータからTFLite推論を行い、
U, S, CCS時系列を生成してESP32再生用CSVを出力する。

Usage:
    python scripts/generate_ccs_sequences.py --subject 1 --output data/ccs_sequences/
    python scripts/generate_ccs_sequences.py --all --output data/ccs_sequences/
"""

import argparse
import json
from pathlib import Path
import numpy as np

# TFLite推論用
try:
    import tensorflow as tf
except ImportError:
    tf = None
    print("Warning: TensorFlow not available. Install with: pip install tensorflow")


# =============================================================================
# 定数
# =============================================================================
TFLITE_MODEL_PATH = Path("har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite")
DATA_PROCESSED_DIR = Path("har/001/data_processed")
WINDOW_DURATION_S = 2.0  # 100サンプル @ 50Hz = 2秒
WINDOW_STRIDE_S = 1.0    # 50%オーバーラップ = 1秒ストライド
N_CLASSES = 12           # 12クラス出力（4クラスに集約）
STABILITY_WINDOW = 5     # 安定度計算用の窓数（W=5）

# CCS閾値（2025-11-27 変更: 0.70/0.40 → 0.90/0.80）
# 理由: CCS分布が高め(0.84-0.93)で2000ms優位になりすぎるため、閾値を上げて間隔の多様性を確保
# 写像: CCS < 0.80 → 100ms, 0.80-0.90 → 500ms, CCS ≥ 0.90 → 2000ms
THETA_HIGH = 0.90
THETA_LOW = 0.80
HYSTERESIS = 0.05
MIN_STAY_S = 2.0

# 12クラス→4クラスマッピング
# 0: Stationary (L1, L2, L3)
# 1: Locomotion (L4, L5, L9, L10, L11)
# 2: Transition (L6, L7, L8, L12)
# 3: Unknown (label 0 in mHealth)
CLASS_12_TO_4 = {
    0: 3,   # null -> Unknown
    1: 0,   # Standing still -> Stationary
    2: 0,   # Sitting -> Stationary
    3: 0,   # Lying down -> Stationary
    4: 1,   # Walking -> Locomotion
    5: 1,   # Climbing stairs -> Locomotion
    6: 2,   # Waist bends -> Transition
    7: 2,   # Frontal elevation -> Transition
    8: 2,   # Knees bending -> Transition
    9: 1,   # Cycling -> Locomotion
    10: 1,  # Jogging -> Locomotion
    11: 1,  # Running -> Locomotion
}


# =============================================================================
# TFLite推論
# =============================================================================
class TFLiteInferencer:
    """TFLite int8モデルの推論クラス"""

    def __init__(self, model_path: Path):
        if tf is None:
            raise ImportError("TensorFlow is required for inference")

        self.interpreter = tf.lite.Interpreter(model_path=str(model_path))
        self.interpreter.allocate_tensors()

        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        # 入力の量子化パラメータ
        self.input_scale = self.input_details[0]['quantization'][0]
        self.input_zero_point = self.input_details[0]['quantization'][1]

        # 出力の量子化パラメータ
        self.output_scale = self.output_details[0]['quantization'][0]
        self.output_zero_point = self.output_details[0]['quantization'][1]

    def infer(self, windows: np.ndarray) -> np.ndarray:
        """
        バッチ推論を実行

        Args:
            windows: [N, 100, 3] float32 入力データ

        Returns:
            probs: [N, 12] float32 クラス確率（softmax後）
        """
        results = []

        for i in range(len(windows)):
            # 入力を量子化
            x = windows[i:i+1]  # [1, 100, 3]
            x_quant = np.round(x / self.input_scale + self.input_zero_point).astype(np.int8)

            # 推論
            self.interpreter.set_tensor(self.input_details[0]['index'], x_quant)
            self.interpreter.invoke()

            # 出力を逆量子化
            y_quant = self.interpreter.get_tensor(self.output_details[0]['index'])
            y = (y_quant.astype(np.float32) - self.output_zero_point) * self.output_scale

            # Softmax
            y_exp = np.exp(y - np.max(y))
            probs = y_exp / np.sum(y_exp)

            results.append(probs[0])

        return np.array(results)


# =============================================================================
# U, S, CCS計算
# =============================================================================
def compute_uncertainty(probs: np.ndarray) -> np.ndarray:
    """
    不確実度 U を計算

    U = -Σ p_k log(p_k) / log(K)  ∈ [0, 1]

    Args:
        probs: [N, K] クラス確率

    Returns:
        U: [N] 正規化エントロピー
    """
    K = probs.shape[1]
    # 数値安定性のため小さな値をクリップ
    probs_clipped = np.clip(probs, 1e-10, 1.0)
    entropy = -np.sum(probs_clipped * np.log(probs_clipped), axis=1)
    U = entropy / np.log(K)
    return U


def compute_stability(pred_labels: np.ndarray, W: int = STABILITY_WINDOW) -> np.ndarray:
    """
    安定度 S を計算

    S = 1 - min(1, n_trans / W)  ∈ [0, 1]

    Args:
        pred_labels: [N] 予測ラベル
        W: 窓数

    Returns:
        S: [N] 安定度
    """
    N = len(pred_labels)
    S = np.zeros(N)

    for i in range(N):
        # 過去W窓を取得
        start = max(0, i - W + 1)
        window_labels = pred_labels[start:i+1]

        # 遷移回数をカウント
        n_trans = np.sum(window_labels[1:] != window_labels[:-1])

        S[i] = 1 - min(1, n_trans / W)

    return S


def compute_ccs(U: np.ndarray, S: np.ndarray) -> np.ndarray:
    """
    複合信頼度スコア CCS を計算

    CCS = 0.7 * (1 - U) + 0.3 * S  ∈ [0, 1]

    Args:
        U: [N] 不確実度
        S: [N] 安定度

    Returns:
        CCS: [N] 複合信頼度スコア
    """
    confidence = 1 - U
    CCS = 0.7 * confidence + 0.3 * S
    return CCS


# =============================================================================
# CCS→T_adv写像
# =============================================================================
def ccs_to_interval(
    ccs_series: np.ndarray,
    timestamps_s: np.ndarray,
    theta_high: float = THETA_HIGH,
    theta_low: float = THETA_LOW,
    hysteresis: float = HYSTERESIS,
    min_stay_s: float = MIN_STAY_S
) -> np.ndarray:
    """
    ヒステリシス付きCCS→T_adv写像

    Args:
        ccs_series: [N] CCS時系列
        timestamps_s: [N] タイムスタンプ（秒）
        theta_high: 高閾値
        theta_low: 低閾値
        hysteresis: ヒステリシス幅
        min_stay_s: 最小滞在時間（秒）

    Returns:
        intervals_ms: [N] 広告間隔時系列（ms）
    """
    N = len(ccs_series)
    intervals = np.zeros(N, dtype=np.int32)

    # 初期状態: CCSに基づいて決定
    if ccs_series[0] >= theta_high:
        intervals[0] = 2000
    elif ccs_series[0] >= theta_low:
        intervals[0] = 500
    else:
        intervals[0] = 100

    last_change_time = timestamps_s[0]

    for i in range(1, N):
        ccs = ccs_series[i]
        t = timestamps_s[i]
        prev_interval = intervals[i-1]

        # 最小滞在時間チェック
        if t - last_change_time < min_stay_s:
            intervals[i] = prev_interval
            continue

        # ヒステリシス付き閾値
        theta_high_up = theta_high
        theta_high_down = theta_high - hysteresis
        theta_low_up = theta_low
        theta_low_down = theta_low - hysteresis

        # 状態遷移ロジック
        new_interval = prev_interval

        if prev_interval == 2000:  # QUIET状態
            if ccs < theta_low_down:
                new_interval = 100  # → ACTIVE
            elif ccs < theta_high_down:
                new_interval = 500  # → UNCERTAIN
        elif prev_interval == 500:  # UNCERTAIN状態
            if ccs >= theta_high_up:
                new_interval = 2000  # → QUIET
            elif ccs < theta_low_down:
                new_interval = 100  # → ACTIVE
        else:  # prev_interval == 100, ACTIVE状態
            if ccs >= theta_high_up:
                new_interval = 2000  # → QUIET
            elif ccs >= theta_low_up:
                new_interval = 500  # → UNCERTAIN

        if new_interval != prev_interval:
            last_change_time = t

        intervals[i] = new_interval

    return intervals


# =============================================================================
# メインパイプライン
# =============================================================================
def process_subject(
    subject_id: int,
    inferencer: TFLiteInferencer,
    output_dir: Path
) -> dict:
    """
    1被験者分の処理を実行

    Args:
        subject_id: 被験者ID (1-10)
        inferencer: TFLite推論器
        output_dir: 出力ディレクトリ

    Returns:
        summary: 処理結果のサマリ
    """
    # データ読み込み
    npz_path = DATA_PROCESSED_DIR / f"subject{subject_id:02d}.npz"
    data = np.load(npz_path)
    X = data['X']  # [N, 100, 3]
    y12 = data['y12']  # [N] 12クラスラベル
    y4 = data['y4']    # [N] 4クラスラベル

    N = len(X)
    print(f"Subject {subject_id:02d}: {N} windows")

    # TFLite推論
    print("  Running TFLite inference...")
    probs = inferencer.infer(X)  # [N, 12]

    # 4クラス確率に集約
    probs_4 = np.zeros((N, 4))
    for c12, c4 in CLASS_12_TO_4.items():
        probs_4[:, c4] += probs[:, c12]

    # 予測ラベル
    pred_labels = np.argmax(probs_4, axis=1)

    # U, S, CCS計算
    print("  Computing U, S, CCS...")
    U = compute_uncertainty(probs_4)
    S = compute_stability(pred_labels)
    CCS = compute_ccs(U, S)

    # タイムスタンプ生成（窓ストライド1秒と仮定）
    timestamps_s = np.arange(N) * WINDOW_STRIDE_S
    timestamps_ms = (timestamps_s * 1000).astype(np.int64)

    # CCS→T_adv変換
    print("  Mapping CCS to T_adv...")
    intervals_ms = ccs_to_interval(CCS, timestamps_s)

    # CSV出力
    output_path = output_dir / f"subject{subject_id:02d}_ccs.csv"
    print(f"  Saving to {output_path}")

    with open(output_path, 'w') as f:
        f.write("timestamp_ms,u,s,ccs,interval_ms,pred_label,true_label_4\n")
        for i in range(N):
            f.write(f"{timestamps_ms[i]},{U[i]:.4f},{S[i]:.4f},{CCS[i]:.4f},"
                    f"{intervals_ms[i]},{pred_labels[i]},{y4[i]}\n")

    # サマリ統計
    summary = {
        "subject_id": subject_id,
        "n_windows": N,
        "duration_s": N * WINDOW_STRIDE_S,
        "u_mean": float(np.mean(U)),
        "u_std": float(np.std(U)),
        "s_mean": float(np.mean(S)),
        "s_std": float(np.std(S)),
        "ccs_mean": float(np.mean(CCS)),
        "ccs_std": float(np.std(CCS)),
        "interval_distribution": {
            "100ms": int(np.sum(intervals_ms == 100)),
            "500ms": int(np.sum(intervals_ms == 500)),
            "2000ms": int(np.sum(intervals_ms == 2000)),
        },
        "n_transitions": int(np.sum(intervals_ms[1:] != intervals_ms[:-1])),
        "output_path": str(output_path),
    }

    return summary


def main():
    parser = argparse.ArgumentParser(description="Generate CCS time series from mHealth data")
    parser.add_argument("--subject", type=int, help="Subject ID (1-10)")
    parser.add_argument("--all", action="store_true", help="Process all subjects")
    parser.add_argument("--output", type=Path, default=Path("data/ccs_sequences"),
                        help="Output directory")
    args = parser.parse_args()

    if not args.subject and not args.all:
        parser.error("Specify --subject N or --all")

    # 出力ディレクトリ作成
    args.output.mkdir(parents=True, exist_ok=True)

    # TFLiteモデル読み込み
    print(f"Loading TFLite model: {TFLITE_MODEL_PATH}")
    inferencer = TFLiteInferencer(TFLITE_MODEL_PATH)

    # 処理実行
    summaries = []

    if args.all:
        subjects = range(1, 11)
    else:
        subjects = [args.subject]

    for sid in subjects:
        summary = process_subject(sid, inferencer, args.output)
        summaries.append(summary)
        print(f"  CCS mean={summary['ccs_mean']:.3f}, transitions={summary['n_transitions']}")
        print()

    # サマリ保存
    summary_path = args.output / "generation_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summaries, f, indent=2)
    print(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    main()
