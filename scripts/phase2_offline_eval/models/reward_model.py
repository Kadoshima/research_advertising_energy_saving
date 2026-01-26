"""
Reward Model for Phase 2 Safe-UCB
報酬モデル: r(a) = -cost(a)

データソース: deltae_v3rig_sweep_2026-01-21_v02
方法: 実測データから cost(a) を計算
  - reward_mode=per_adv: cost(a)=μC(a) [μJ/adv]
  - reward_mode=per_60s: cost(a)=ΔE_total(a) [mJ/60s] （60s試行のOFF差分）
"""

import pandas as pd
import numpy as np
from pathlib import Path


class RewardModel:
    """報酬モデル: 広告間隔ごとのエネルギーコスト（modeに依存）"""

    def __init__(self, data_path: str, reward_mode: str = "per_adv"):
        """
        Args:
            data_path: deltae_v02のパス（例: data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02/）
            reward_mode:
              - "per_adv": μC(a) = (E_on - E_off)/N_adv [μJ/adv]
              - "per_60s": ΔE_total(a) = (E_on - E_off) [mJ/60s]  (60s試行)
        """
        self.data_path = Path(data_path)
        self.reward_mode = reward_mode
        self.cost_unit = {"per_adv": "uJ_per_adv", "per_60s": "mJ_per_60s"}.get(reward_mode, "")
        if not self.cost_unit:
            raise ValueError(f"unknown reward_mode: {reward_mode!r}")

        self.mu_c = {}  # 平均cost [unit: cost_unit]
        self.sigma_c = {}  # 標準偏差 [unit: cost_unit]
        self.n_samples = {}  # サンプル数

        # 実データから読み込み
        self._load_from_real_data()

    def _load_from_real_data(self):
        """実測データから cost(a) を計算"""
        # 集計済みCSVを読み込む
        stats_file = Path("results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv")
        trials_file = Path("results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv")

        if not stats_file.exists():
            raise FileNotFoundError(f"Stats file not found: {stats_file}")
        if not trials_file.exists():
            raise FileNotFoundError(f"Trials file not found: {trials_file}")

        # statsからE_total_mJ, delta_E_mJを取得
        df_stats = pd.read_csv(stats_file, dtype={'mode': str})  # modeを文字列として読み込む
        df_trials = pd.read_csv(trials_file)

        # OFFモードの平均エネルギー
        e_off_row = df_stats[(df_stats['metric'] == 'e_total_mj') & (df_stats['mode'] == 'OFF')]
        if len(e_off_row) == 0:
            raise ValueError("OFF mode data not found in stats")
        e_off_mean = e_off_row['mean'].values[0]
        e_off_std = float(e_off_row['std'].values[0])

        # ONモード（100, 500, 1000, 2000）ごとにμC計算
        for mode_ms in [100, 500, 1000, 2000]:
            # E_total(ON)の平均（modeは文字列として比較）
            e_on_row = df_stats[(df_stats['metric'] == 'e_total_mj') & (df_stats['mode'] == str(mode_ms))]
            if len(e_on_row) == 0:
                print(f"Warning: {mode_ms}ms data not found, skipping")
                continue

            e_on_mean = e_on_row['mean'].values[0]
            e_on_std = e_on_row['std'].values[0]
            n = int(e_on_row['n'].values[0])

            # ΔE = E_ON - E_OFF
            delta_e_mj = e_on_mean - e_off_mean

            if self.reward_mode == "per_adv":
                # trialsファイルから該当モードの広告回数を取得
                trials_mode = df_trials[df_trials['mode_ms'] == mode_ms]
                if len(trials_mode) == 0:
                    print(f"Warning: {mode_ms}ms trials not found, skipping")
                    continue

                # 広告回数の平均（N_adv）
                n_adv_mean = float(trials_mode['adv_count'].mean())

                # μC = ΔE / N_adv [mJ/adv] → [μJ/adv]
                mu_cost = (delta_e_mj / n_adv_mean) * 1000.0

                # 近似: E_on の分散のみを反映（v01互換のためE_offは無視）
                sigma_cost = (e_on_std / n_adv_mean) * 1000.0
            elif self.reward_mode == "per_60s":
                # cost = ΔE_total (60s試行のOFFとの差分)
                mu_cost = float(delta_e_mj)

                # 近似: E_on と E_off を独立として分散を加算
                sigma_cost = float(np.sqrt(float(e_on_std) ** 2 + float(e_off_std) ** 2))
            else:
                raise ValueError(f"unknown reward_mode: {self.reward_mode!r}")

            self.mu_c[mode_ms] = float(mu_cost)
            self.sigma_c[mode_ms] = float(sigma_cost)
            self.n_samples[mode_ms] = int(n)

            unit_str = "uJ/adv" if self.reward_mode == "per_adv" else "mJ/60s"
            print(f"Action {mode_ms}ms: cost = {mu_cost:.1f} +/- {sigma_cost:.1f} {unit_str} (n={n})")

    def mean(self, action: int) -> float:
        """行動aの平均報酬（負のコスト）"""
        if action not in self.mu_c:
            raise ValueError(f"Action {action}ms not found in reward model")
        return -self.mu_c[action]  # 報酬は負のコスト（最大化）

    def std(self, action: int) -> float:
        """行動aの標準偏差"""
        if action not in self.sigma_c:
            raise ValueError(f"Action {action}ms not found in reward model")
        return self.sigma_c[action]

    def sample(self, action: int, rng: np.random.Generator) -> float:
        """行動aからの報酬サンプル（正規分布近似）"""
        mu = self.mean(action)
        sigma = self.std(action)
        return rng.normal(mu, sigma)

    def get_optimal_action(self, actions: list) -> int:
        """最大報酬の行動（オラクル用）"""
        # 報酬 = -μC なので、μCが最小の行動が最適
        return min(actions, key=lambda a: self.mu_c[a])


if __name__ == "__main__":
    # テスト実行
    model = RewardModel("data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02/", reward_mode="per_adv")

    print("\n=== Reward Model Test ===")
    for action in [500, 1000, 2000]:
        print(f"Action {action}ms: reward = {model.mean(action):.1f} ({model.cost_unit})")

    optimal = model.get_optimal_action([500, 1000, 2000])
    print(f"\nOptimal action: {optimal}ms")
