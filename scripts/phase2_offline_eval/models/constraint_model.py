"""
Constraint Model for Phase 2 Safe-UCB
制約モデル: Pout(τ|a) = Pr[TL > τ | interval = a]

データソース: phase1_e2_ccs + phase1_e2_fixed_sweep
方法: RXログから TL (Time-to-first-Receive) を計算し、Pout(τ)を推定

注意: E2データの解析が必要。現時点では簡易推定を使用。
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List


class ConstraintModel:
    """制約モデル: 広告間隔ごとの遅延確率 Pout(τ|a)"""

    def __init__(self, data_paths: List[str], tau: float = 1.0):
        """
        Args:
            data_paths: E2データのパスリスト
            tau: 許容遅延 [s]
        """
        self.data_paths = [Path(p) for p in data_paths]
        self.tau = tau
        self.pout = {}  # Pout(τ|a)
        self.pout_std = {}  # 標準偏差（推定）
        self.n_samples = {}  # サンプル数

        # 実データから読み込み
        self._load_from_real_data()

    def _load_from_real_data(self):
        """E2データからPout(τ|a)を計算"""
        # 簡易実装: 広告間隔から理論的なPout(τ)を推定
        # TODO: RXログから実際のTLを計算して正確なPout値を求める

        # E2 FIXED sweep データから推定
        # manifestから間隔情報を取得
        for data_path in self.data_paths:
            if not data_path.exists():
                print(f"Warning: Data path not found: {data_path}")
                continue

            # E2 FIXEDの場合、ファイル名から間隔を推定
            # または manifestを読み込む
            manifest_file = data_path / "manifest.csv"
            if not manifest_file.exists():
                print(f"Warning: manifest not found: {manifest_file}")
                continue

            # 簡易推定: 間隔に応じたPout値
            # 理論: interval_ms が大きいほど Pout(τ) が高い
            # 実測値がないため、暫定的に経験則を使用

            print(f"Loading constraint data from: {data_path.name}")

            # 暫定的な値（E2環境での推定値）
            # これは実データで置き換える必要がある
            # TODO: RX CSVを解析してTL分布からPout(τ)を計算

        # 暫定値（Phase 1 E1データや理論値から推定）
        # FIXME: これは実データで置き換える
        print("\nWARNING: Using placeholder Pout values.")
        print("TODO: Analyze E2 RX logs to compute actual Pout(τ) distribution.")

        # 暫定値: 間隔が大きいほどPoutが高いと仮定
        self.pout[500] = 0.05  # 500ms: 低いPout
        self.pout[1000] = 0.08  # 1000ms: 中程度
        self.pout[2000] = 0.12  # 2000ms: 高いPout（制約違反の可能性）

        self.pout_std[500] = 0.02
        self.pout_std[1000] = 0.03
        self.pout_std[2000] = 0.04

        self.n_samples[500] = 5  # E2 FIXED の試行数
        self.n_samples[1000] = 5
        self.n_samples[2000] = 5

        for action in [500, 1000, 2000]:
            print(f"Action {action}ms: Pout({self.tau}s) = {self.pout[action]:.3f} ± {self.pout_std[action]:.3f} (n={self.n_samples[action]})")

    def predict(self, action: int) -> float:
        """行動aに対するPout(τ)の予測値"""
        if action not in self.pout:
            raise ValueError(f"Action {action}ms not found in constraint model")
        return self.pout[action]

    def std(self, action: int) -> float:
        """行動aのPout(τ)の標準偏差"""
        if action not in self.pout_std:
            raise ValueError(f"Action {action}ms not found in constraint model")
        return self.pout_std[action]

    def confidence(self, action: int, alpha: float = 0.05) -> float:
        """信頼区間の幅（UCB用）"""
        # UCB: μ + c * σ / sqrt(n)
        # ここでは標準誤差を返す
        n = self.n_samples.get(action, 1)
        return self.std(action) / np.sqrt(n)

    def is_safe(self, action: int, epsilon: float) -> bool:
        """制約を満たすか（安全か）"""
        pout_estimate = self.predict(action)
        pout_ucb = pout_estimate + self.confidence(action)
        return pout_ucb <= epsilon


if __name__ == "__main__":
    # テスト実行
    data_paths = [
        "data/実験データ/研究室/phase1_e2_ccs_2026-01-21_v01/",
        "data/実験データ/研究室/phase1_e2_fixed_sweep_2026-01-21_v01/",
    ]

    model = ConstraintModel(data_paths, tau=1.0)

    print("\n=== Constraint Model Test ===")
    epsilon = 0.10
    for action in [500, 1000, 2000]:
        pout = model.predict(action)
        safe = model.is_safe(action, epsilon)
        print(f"Action {action}ms: Pout(1s) = {pout:.3f}, Safe(ε={epsilon})? {safe}")
