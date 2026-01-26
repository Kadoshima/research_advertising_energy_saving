"""
Safe-UCB and Baseline Algorithms for Phase 2 Evaluation

実装する手法:
1. Safe-UCB: 制約を守りながら探索
2. UCB: 制約なし（報酬のみ最大化）
3. Fixed-CCS: Phase 1の閾値写像（学習なし）
4. Oracle: 真の最適行動（上界）
"""

import numpy as np
from statistics import NormalDist
from typing import Dict, List, Optional, Tuple
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
        constraint_ci: str = "t_dependent",
        constraint_delta: float = 0.05,
        init_strategy: str = "round_robin",
    ):
        super().__init__(actions, seed)
        self.reward_model = reward_model
        self.constraint_model = constraint_model
        self.epsilon = epsilon  # 制約閾値
        self.constraint_ci = str(constraint_ci)
        self.constraint_delta = float(constraint_delta)
        self.init_strategy = str(init_strategy)
        self.baseline_action = min(self.actions) if self.actions else None

        if self.constraint_ci not in ("t_dependent", "hoeffding", "beta", "wilson"):
            raise ValueError(f"unknown constraint_ci: {self.constraint_ci!r}")
        if not (0.0 < self.constraint_delta < 1.0):
            raise ValueError("constraint_delta must be in (0,1)")
        if self.init_strategy not in ("round_robin", "safe_seed", "baseline_only"):
            raise ValueError(f"unknown init_strategy: {self.init_strategy!r}")

        # One-sided normal quantile for Wilson upper bound.
        self._wilson_z = float(NormalDist().inv_cdf(1.0 - self.constraint_delta))

        # Offline-safe seeding set (used by init_strategy="safe_seed"). We treat the
        # passed constraint_model as an offline estimate and only seed actions that
        # look safe under it.
        seed_actions: List[int] = []
        for a in sorted(self.actions):
            try:
                if self.constraint_model.is_safe(a, self.epsilon):
                    seed_actions.append(a)
            except Exception:
                continue
        if self.baseline_action is not None:
            seed_actions.append(int(self.baseline_action))
        self._seed_actions = sorted(set(seed_actions))

        # Diagnostics (for validating "Safe-UCB is learning" vs fallback behavior)
        self._diag_steps = 0
        self._diag_safe_set_empty = 0
        self._diag_safe_set_size_sum = 0
        self.last_safe_set_size = 0
        self.last_safe_set_empty = False

    def _constraint_ucb(self, action: int) -> float:
        """Upper confidence bound for Pout(tau|action) based on online samples."""
        n = int(self.n_pulls[action])
        if n <= 0:
            return float("inf")

        mean = float(self.cumulative_constraint[action] / n)
        mean = min(1.0, max(0.0, mean))

        if self.constraint_ci == "t_dependent":
            t = max(2, int(self.t))
            bonus = float(np.sqrt(2.0 * np.log(t) / n))
            return min(1.0, mean + bonus)

        if self.constraint_ci == "hoeffding":
            bonus = float(np.sqrt(np.log(1.0 / self.constraint_delta) / (2.0 * n)))
            return min(1.0, mean + bonus)

        if self.constraint_ci == "wilson":
            z = self._wilson_z
            denom = 1.0 + (z * z) / n
            center = (mean + (z * z) / (2.0 * n)) / denom
            half = (z * np.sqrt((mean * (1.0 - mean)) / n + (z * z) / (4.0 * n * n))) / denom
            return min(1.0, float(center + half))

        # Bernoulli posterior upper-quantile (Jeffreys-like with Beta(1,1) prior).
        # This is often less conservative than Hoeffding for small n.
        try:
            from scipy.stats import beta as _beta_dist
        except Exception as e:
            raise RuntimeError("constraint_ci='beta' requires scipy") from e

        s = float(self.cumulative_constraint[action])
        f = float(n) - s
        a = 1.0 + s
        b = 1.0 + max(0.0, f)
        q = float(_beta_dist.ppf(1.0 - self.constraint_delta, a, b))
        return min(1.0, max(0.0, q))

    def diagnostics(self) -> Dict[str, float]:
        steps = int(self._diag_steps)
        if steps <= 0:
            return {}
        return {
            "safe_set_empty_rate": float(self._diag_safe_set_empty) / steps,
            "safe_set_size_mean": float(self._diag_safe_set_size_sum) / steps,
        }

    def select_action(self, context: float = None) -> int:
        """Safe-UCBによる行動選択"""
        # Cold-start handling
        if self.init_strategy == "round_robin":
            # Each action is pulled once (may violate constraints).
            for a in self.actions:
                if self.n_pulls[a] == 0:
                    return a
        elif self.init_strategy == "safe_seed":
            # Seed only actions that look safe under the (offline) constraint model.
            for a in self._seed_actions:
                if self.n_pulls.get(a, 0) == 0:
                    return a
        elif self.init_strategy == "baseline_only":
            if self.baseline_action is not None and self.n_pulls[self.baseline_action] == 0:
                return int(self.baseline_action)

        # 1. 各行動のUCB値を計算
        ucb_values = {}
        pulled_actions = [a for a in self.actions if self.n_pulls[a] > 0]
        if not pulled_actions:
            return int(self.baseline_action)

        for a in pulled_actions:
            # 経験平均報酬
            mean_reward = self.cumulative_reward[a] / self.n_pulls[a]

            # UCB項
            t = max(2, int(self.t))
            ucb_term = np.sqrt(2 * np.log(t) / self.n_pulls[a])
            ucb_values[a] = mean_reward + ucb_term

        # 2. 安全行動集合を計算（制約を満たす行動）
        safe_set = []
        for a in pulled_actions:
            if self._constraint_ucb(a) <= self.epsilon:
                safe_set.append(a)

        # Diagnostics (raw safe-set, before fallback)
        self._diag_steps += 1
        self.last_safe_set_size = int(len(safe_set))
        self.last_safe_set_empty = bool(len(safe_set) == 0)
        self._diag_safe_set_empty += int(self.last_safe_set_empty)
        self._diag_safe_set_size_sum += int(self.last_safe_set_size)

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


class SafetyFilterUCB(BanditAlgorithm):
    """
    UCB with an online-updated safety filter (action masking).

    - Inner loop: standard UCB on reward among currently "allowed" actions.
    - Outer loop: start from a prior-based allow-list, then *remove* actions when
      online evidence suggests they are unsafe.

      This design is intentional for Gate B (env shift):
      - A fixed allow-list (from prior env) can become wrong after shift.
      - If we require "UCB <= epsilon" from the very beginning, the safe set tends
        to be empty for small n, making the policy degenerate (baseline-only).

    This keeps the implementation MCU-friendly (O(K) state), and makes it easy to
    diagnose failures under environment shift by logging which actions were masked.
    """

    def __init__(
        self,
        actions: List[int],
        reward_model: RewardModel,
        epsilon: float = 0.10,
        margin: float = 0.0,
        seed: int = 42,
        constraint_ci: str = "beta",
        constraint_delta: float = 0.05,
        prior_pout: Optional[Dict[int, float]] = None,
        prior_n: Optional[Dict[int, int]] = None,
        prior_weight: float = 1.0,
    ):
        super().__init__(actions, seed)
        self.reward_model = reward_model
        self.epsilon = float(epsilon)
        self.margin = float(margin)
        self.constraint_ci = str(constraint_ci)
        self.constraint_delta = float(constraint_delta)
        self.prior_weight = float(prior_weight)
        self.baseline_action = min(self.actions) if self.actions else None

        if self.constraint_ci not in ("t_dependent", "hoeffding", "beta", "wilson"):
            raise ValueError(f"unknown constraint_ci: {self.constraint_ci!r}")
        if not (0.0 < self.constraint_delta < 1.0):
            raise ValueError("constraint_delta must be in (0,1)")
        if self.margin < 0.0:
            raise ValueError("margin must be >= 0")
        if self.prior_weight < 0.0:
            raise ValueError("prior_weight must be >= 0")

        self._wilson_z = float(NormalDist().inv_cdf(1.0 - self.constraint_delta))

        # Separate constraint stats so we can warm-start / discount without
        # polluting reward UCB stats.
        self._c_n: Dict[int, float] = {a: 0.0 for a in self.actions}
        self._c_s: Dict[int, float] = {a: 0.0 for a in self.actions}  # sum of violations
        prior_pout = prior_pout or {}
        prior_n = prior_n or {}
        for a in self.actions:
            n0 = float(prior_n.get(a, 0))
            p0 = float(prior_pout.get(a, float("nan")))
            if n0 > 0 and np.isfinite(p0):
                n0w = self.prior_weight * n0
                self._c_n[a] = float(n0w)
                self._c_s[a] = float(n0w * p0)

        # Prior-based allow-list: used as the initial safety filter. We always keep
        # the baseline action as a conservative fallback to avoid empty safe sets.
        thr0 = max(0.0, self.epsilon - self.margin)
        self._base_allow: Dict[int, bool] = {a: False for a in self.actions}
        for a in self.actions:
            p0 = float(prior_pout.get(a, float("nan")))
            if np.isfinite(p0) and p0 <= thr0:
                self._base_allow[a] = True
        if self.baseline_action is not None:
            self._base_allow[int(self.baseline_action)] = True

        # Diagnostics
        self._diag_steps = 0
        self._diag_safe_set_empty = 0
        self._diag_safe_set_size_sum = 0
        self.last_safe_set_size = 0
        self.last_safe_set_empty = False

    def _constraint_ucb(self, action: int) -> float:
        n = float(self._c_n.get(action, 0.0))
        if n <= 0.0:
            return float("inf")
        s = float(self._c_s.get(action, 0.0))
        mean = min(1.0, max(0.0, s / n))

        if self.constraint_ci == "t_dependent":
            t = max(2, int(self.t))
            bonus = float(np.sqrt(2.0 * np.log(t) / n))
            return min(1.0, mean + bonus)

        if self.constraint_ci == "hoeffding":
            bonus = float(np.sqrt(np.log(1.0 / self.constraint_delta) / (2.0 * n)))
            return min(1.0, mean + bonus)

        if self.constraint_ci == "wilson":
            z = self._wilson_z
            denom = 1.0 + (z * z) / n
            center = (mean + (z * z) / (2.0 * n)) / denom
            half = (z * np.sqrt((mean * (1.0 - mean)) / n + (z * z) / (4.0 * n * n))) / denom
            return min(1.0, float(center + half))

        try:
            from scipy.stats import beta as _beta_dist
        except Exception as e:
            raise RuntimeError("constraint_ci='beta' requires scipy") from e

        # Beta(a,b) posterior with Beta(1,1) prior (allows fractional pseudo-counts).
        a = 1.0 + s
        b = 1.0 + max(0.0, n - s)
        q = float(_beta_dist.ppf(1.0 - self.constraint_delta, a, b))
        return min(1.0, max(0.0, q))

    def _constraint_lcb(self, action: int) -> float:
        """Lower confidence bound for Pout(tau|action) based on current samples."""
        n = float(self._c_n.get(action, 0.0))
        if n <= 0.0:
            return 0.0
        s = float(self._c_s.get(action, 0.0))
        mean = min(1.0, max(0.0, s / n))

        if self.constraint_ci == "t_dependent":
            t = max(2, int(self.t))
            bonus = float(np.sqrt(2.0 * np.log(t) / n))
            return max(0.0, mean - bonus)

        if self.constraint_ci == "hoeffding":
            bonus = float(np.sqrt(np.log(1.0 / self.constraint_delta) / (2.0 * n)))
            return max(0.0, mean - bonus)

        if self.constraint_ci == "wilson":
            z = self._wilson_z
            denom = 1.0 + (z * z) / n
            center = (mean + (z * z) / (2.0 * n)) / denom
            half = (z * np.sqrt((mean * (1.0 - mean)) / n + (z * z) / (4.0 * n * n))) / denom
            return max(0.0, float(center - half))

        try:
            from scipy.stats import beta as _beta_dist
        except Exception as e:
            raise RuntimeError("constraint_ci='beta' requires scipy") from e

        # Beta(a,b) posterior lower-quantile (Beta(1,1) prior).
        a = 1.0 + s
        b = 1.0 + max(0.0, n - s)
        q = float(_beta_dist.ppf(self.constraint_delta, a, b))
        return min(1.0, max(0.0, q))

    def on_switch(self, discount: float) -> None:
        """Discount (or reset) constraint history when an environment shift is detected."""
        d = float(discount)
        if d < 0.0:
            raise ValueError("discount must be >= 0")
        for a in self.actions:
            self._c_n[a] *= d
            self._c_s[a] *= d

    def diagnostics(self) -> Dict[str, float]:
        steps = int(self._diag_steps)
        if steps <= 0:
            return {}
        return {
            "safe_set_empty_rate": float(self._diag_safe_set_empty) / steps,
            "safe_set_size_mean": float(self._diag_safe_set_size_sum) / steps,
        }

    def select_action(self, context: float = None) -> int:
        # Safety filter (action masking)
        # - Start from prior allow-list.
        # - Remove actions only when we are confident they are unsafe (LCB > thr).
        #
        # This makes Gate B meaningful: a prior-safe action can be tried early
        # (and possibly violate), then gets masked when enough target evidence
        # accumulates. "margin" controls conservativeness of this masking.
        thr = max(0.0, self.epsilon - self.margin)
        safe_set: List[int] = []
        for a in self.actions:
            base_allowed = bool(self._base_allow.get(a, False))
            if base_allowed:
                # Confidently unsafe -> mask it.
                if self._constraint_lcb(a) > thr:
                    continue
                safe_set.append(a)
            else:
                # Not in prior allow-list; allow only if we are already confident safe.
                if self._constraint_ucb(a) <= thr:
                    safe_set.append(a)

        # Diagnostics (before fallback)
        self._diag_steps += 1
        self.last_safe_set_size = int(len(safe_set))
        self.last_safe_set_empty = bool(len(safe_set) == 0)
        self._diag_safe_set_empty += int(self.last_safe_set_empty)
        self._diag_safe_set_size_sum += int(self.last_safe_set_size)

        if not safe_set:
            # Always have a conservative fallback.
            return int(self.baseline_action)

        # Reward UCB among safe actions.
        for a in safe_set:
            if self.n_pulls[a] == 0:
                return a

        t = max(2, int(self.t))
        ucb_values = {}
        for a in safe_set:
            mean_reward = self.cumulative_reward[a] / self.n_pulls[a]
            ucb_term = np.sqrt(2.0 * np.log(t) / self.n_pulls[a])
            ucb_values[a] = mean_reward + ucb_term
        return max(safe_set, key=lambda a: ucb_values[a])

    def update(self, action: int, reward: float, constraint: float):
        super().update(action, reward, constraint)
        self._c_n[action] += 1.0
        self._c_s[action] += float(constraint)


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
