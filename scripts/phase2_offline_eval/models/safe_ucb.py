"""
Safe-UCB and Baseline Algorithms for Phase 2 Evaluation

実装する手法:
1. Safe-UCB: 制約を守りながら探索
2. UCB: 制約なし（報酬のみ最大化）
3. Fixed-CCS: Phase 1の閾値写像（学習なし）
4. Oracle: 真の最適行動（上界）
"""

import numpy as np
from typing import List, Tuple
from .reward_model import RewardModel
from .constraint_model import ConstraintModel


class BanditAlgorithm:
    """Banditアルゴリズムの基底クラス"""

    def __init__(self, actions: List[int], seed: int = 42):
        self.actions = actions
        self.rng = np.random.default_rng(seed)
        self.t = 0  # 現在のステップ
        self.n_pulls = {a: 0 for a in actions}  # 各行動の引いた回数
        self.cumulative_reward = {a: 0.0 for a in actions}
        self.cumulative_constraint = {a: 0.0 for a in actions}

    def select_action(self, context: float = None) -> int:
        """行動選択（サブクラスで実装）"""
        raise NotImplementedError

    def update(self, action: int, reward: float, constraint: float):
        """観測の更新"""
        self.t += 1
        self.n_pulls[action] += 1
        self.cumulative_reward[action] += reward
        self.cumulative_constraint[action] += constraint


class SafeUCB(BanditAlgorithm):
    """Safe-UCB: 制約を守りながら探索"""

    def __init__(
        self,
        actions: List[int],
        reward_model: RewardModel,
        constraint_model: ConstraintModel,
        epsilon: float = 0.10,
        seed: int = 42,
    ):
        super().__init__(actions, seed)
        self.reward_model = reward_model
        self.constraint_model = constraint_model
        self.epsilon = epsilon  # 制約閾値

    def select_action(self, context: float = None) -> int:
        """Safe-UCBによる行動選択"""
        # 各行動が少なくとも1回は引かれるまではラウンドロビン
        for a in self.actions:
            if self.n_pulls[a] == 0:
                return a

        # 1. 各行動のUCB値を計算
        ucb_values = {}
        for a in self.actions:
            # 経験平均報酬
            mean_reward = self.cumulative_reward[a] / self.n_pulls[a]

            # UCB項
            ucb_term = np.sqrt(2 * np.log(self.t) / self.n_pulls[a])
            ucb_values[a] = mean_reward + ucb_term

        # 2. 安全行動集合を計算（制約を満たす行動）
        safe_set = []
        for a in self.actions:
            # 制約の経験平均（Pout推定値）
            mean_constraint = self.cumulative_constraint[a] / self.n_pulls[a]

            # 信頼区間の上界
            constraint_ucb = mean_constraint + np.sqrt(
                2 * np.log(self.t) / self.n_pulls[a]
            )

            if constraint_ucb <= self.epsilon:
                safe_set.append(a)

        # 3. 安全集合が空ならフォールバック（最も安全そうな行動）
        if len(safe_set) == 0:
            safe_set = [min(self.actions)]  # 最小間隔（最も応答性が高い）

        # 4. 安全集合の中でUCB最大の行動を選択
        return max(safe_set, key=lambda a: ucb_values[a])


class UCB(BanditAlgorithm):
    """UCB: 制約なし（報酬のみ最大化）"""

    def __init__(self, actions: List[int], seed: int = 42):
        super().__init__(actions, seed)

    def select_action(self, context: float = None) -> int:
        """UCBによる行動選択（制約なし）"""
        # ラウンドロビン
        for a in self.actions:
            if self.n_pulls[a] == 0:
                return a

        # UCB値最大の行動を選択
        ucb_values = {}
        for a in self.actions:
            mean_reward = self.cumulative_reward[a] / self.n_pulls[a]
            ucb_term = np.sqrt(2 * np.log(self.t) / self.n_pulls[a])
            ucb_values[a] = mean_reward + ucb_term

        return max(self.actions, key=lambda a: ucb_values[a])


class FixedCCS(BanditAlgorithm):
    """Fixed-CCS: Phase 1の閾値写像（学習なし）"""

    def __init__(
        self,
        actions: List[int],
        seed: int = 42,
        theta_low: float = 0.40,
        theta_high: float = 0.70,
    ):
        super().__init__(actions, seed)
        self.theta_low = theta_low
        self.theta_high = theta_high

    def select_action(self, context: float = None) -> int:
        """CCS値に基づく固定マッピング"""
        if context is None:
            # コンテキストがない場合はデフォルト
            context = 0.5

        # Phase 1の閾値写像
        if context >= self.theta_high:
            return min(self.actions)  # ACTIVE（最小間隔）
        elif context <= self.theta_low:
            return max(self.actions)  # QUIET（最大間隔）
        else:
            # UNCERTAIN（中間）
            mid_idx = len(self.actions) // 2
            return sorted(self.actions)[mid_idx]


class Oracle(BanditAlgorithm):
    """Oracle: 真の最適行動（上界）"""

    def __init__(
        self,
        actions: List[int],
        reward_model: RewardModel,
        constraint_model: ConstraintModel,
        epsilon: float = 0.10,
        seed: int = 42,
    ):
        super().__init__(actions, seed)
        self.reward_model = reward_model
        self.constraint_model = constraint_model
        self.epsilon = epsilon

        # 最適行動を事前に計算
        self.optimal_action = self._compute_optimal()

    def _compute_optimal(self) -> int:
        """制約を満たす行動の中で報酬最大の行動"""
        safe_actions = [
            a for a in self.actions if self.constraint_model.predict(a) <= self.epsilon
        ]

        if len(safe_actions) == 0:
            # 制約を満たす行動がない場合はフォールバック
            return min(self.actions)

        # 安全な行動の中で報酬最大
        return max(safe_actions, key=lambda a: self.reward_model.mean(a))

    def select_action(self, context: float = None) -> int:
        """常に最適行動を選択"""
        return self.optimal_action


if __name__ == "__main__":
    # テスト実行
    from reward_model import RewardModel
    from constraint_model import ConstraintModel

    print("=== Bandit Algorithms Test ===\n")

    # モデル読み込み
    reward_model = RewardModel(
        "data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02/"
    )
    constraint_model = ConstraintModel(
        [
            "data/実験データ/研究室/phase1_e2_ccs_2026-01-21_v01/",
            "data/実験データ/研究室/phase1_e2_fixed_sweep_2026-01-21_v01/",
        ],
        tau=1.0,
    )

    actions = [500, 1000, 2000]
    epsilon = 0.10

    # 各アルゴリズムを初期化
    safe_ucb = SafeUCB(actions, reward_model, constraint_model, epsilon, seed=42)
    ucb = UCB(actions, seed=42)
    fixed_ccs = FixedCCS(actions, seed=42)
    oracle = Oracle(actions, reward_model, constraint_model, epsilon, seed=42)

    print(f"Oracle optimal action: {oracle.optimal_action}ms\n")

    # 数ステップ実行
    for t in range(10):
        # Safe-UCB
        action = safe_ucb.select_action()
        reward = reward_model.sample(action, safe_ucb.rng)
        constraint_val = float(constraint_model.predict(action) > epsilon)
        safe_ucb.update(action, reward, constraint_val)

        print(f"t={t+1}: Safe-UCB選択 {action}ms, reward={reward:.1f}")

    print("\nTest completed.")
