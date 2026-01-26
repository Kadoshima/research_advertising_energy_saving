#!/usr/bin/env python3
"""
Phase 2 offline-safe study runner.

This script runs a small set of "next" offline experiments:
1) Model validity (train/test split) for reward/constraint estimates
2) Environment shift checks (scan90->scan70, E1->E2) via warm-start priors
3) Action-set variants ({100,500}, {500,1000,2000}, {100,500,1000,2000})
4) Warm-start vs cold-start comparison
5) epsilon/tau sensitivity tables (no simulation)

Outputs are written under: results/phase2_offline_studies_YYYY-MM-DD_v01/
"""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import sys

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from models.reward_model import RewardModel
from models.constraint_model import ConstraintModel
from models.safe_ucb import FixedCCS, Oracle, SafeUCB, SafetyFilterUCB, UCB


DEFAULT_BASE_SEED = 0xD4B40201


def _find_unique_dir(root: Path, name: str) -> Path:
    matches = [p for p in root.rglob(name) if p.is_dir()]
    if not matches:
        raise FileNotFoundError(f"Could not find directory named '{name}' under {root}")
    if len(matches) > 1:
        # Prefer the shallowest match to avoid picking nested staging dirs.
        matches = sorted(matches, key=lambda p: (len(p.parts), str(p)))
    return matches[0]


@dataclass(frozen=True)
class EnvSpec:
    env_id: str
    constraint_sources: List[str]


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    env_id: str
    actions: List[int]
    tau_s: float
    epsilon: float
    prior_env_id: Optional[str] = None  # if set, enable warm-start from this env
    filter_env_id: Optional[str] = None  # if set, use this env for action masking (safety filter)
    switch_env_id: Optional[str] = None  # if set, switch constraint env mid-run (nonstationary check)
    switch_at_frac: Optional[float] = None  # e.g., 0.5 for mid-run switch


def _today_slug() -> str:
    return dt.date.today().isoformat()


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _reward_split_validity(
    trials_csv: Path,
    train_frac: float,
    rng: np.random.Generator,
    reward_mode: str,
) -> pd.DataFrame:
    df = pd.read_csv(trials_csv)

    # Stratified split per mode_ms to keep balance.
    train_idx = []
    test_idx = []
    for mode, g in df.groupby("mode_ms"):
        idx = g.index.to_numpy()
        rng.shuffle(idx)
        n_train = int(round(len(idx) * train_frac))
        train_idx.extend(idx[:n_train])
        test_idx.extend(idx[n_train:])

    train = df.loc[train_idx].copy()
    test = df.loc[test_idx].copy()

    e_off_train = float(train[train["mode_ms"] == 0]["e_total_mj"].mean())
    if not np.isfinite(e_off_train):
        raise RuntimeError("reward split: failed to compute E_off mean from train split")

    rows = []
    for mode_ms in sorted(df["mode_ms"].unique()):
        if mode_ms == 0:
            continue
        tr = train[train["mode_ms"] == mode_ms]
        te = test[test["mode_ms"] == mode_ms]
        if tr.empty or te.empty:
            continue

        if reward_mode == "per_adv":
            # cost = (E_on - E_off)/N_adv [μJ/adv]
            c_train = (tr["e_total_mj"] - e_off_train) / tr["adv_count"] * 1000.0
            c_test = (te["e_total_mj"] - e_off_train) / te["adv_count"] * 1000.0
            cost_unit = "uJ_per_adv"
        elif reward_mode == "per_60s":
            # cost = (E_on - E_off) [mJ/60s] (60s試行)
            c_train = (tr["e_total_mj"] - e_off_train)
            c_test = (te["e_total_mj"] - e_off_train)
            cost_unit = "mJ_per_60s"
        else:
            raise ValueError(f"unknown reward_mode: {reward_mode!r}")

        mu_train = float(c_train.mean())
        mae_test = float(np.mean(np.abs(c_test - mu_train)))
        rows.append(
            {
                "action_ms": int(mode_ms),
                "e_off_train_mJ": e_off_train,
                "train_cost_mean": mu_train,
                "test_cost_mean": float(c_test.mean()),
                "mae_test": mae_test,
                "reward_mode": reward_mode,
                "cost_unit": cost_unit,
                "n_train": int(len(tr)),
                "n_test": int(len(te)),
            }
        )

    return pd.DataFrame(rows)


def _constraint_split_validity_e2_fixed(
    model: ConstraintModel,
    epsilon: float,
    tau_s: float,
    train_frac: float,
    rng: np.random.Generator,
) -> pd.DataFrame:
    # Uses internal per-trial Pout lists derived from RX logs.
    # If the model was built from non-RX sources, this table may be empty.
    trial_pout = getattr(model, "_rx_trial_pout", {})

    rows = []
    for action_ms in sorted(trial_pout.keys()):
        vals = trial_pout[action_ms].get(tau_s, [])
        if not vals:
            continue
        idx = np.arange(len(vals))
        rng.shuffle(idx)
        n_train = max(1, int(round(len(idx) * train_frac)))
        tr = [vals[i] for i in idx[:n_train]]
        te = [vals[i] for i in idx[n_train:]] or [vals[i] for i in idx[n_train - 1 : n_train]]

        p_train = float(np.mean(tr))
        p_test = float(np.mean(te))
        rows.append(
            {
                "action_ms": int(action_ms),
                "tau_s": float(tau_s),
                "pout_train_mean": p_train,
                "pout_test_mean": p_test,
                "abs_error": abs(p_test - p_train),
                "pred_safe": p_train <= epsilon,
                "actual_safe": p_test <= epsilon,
                "n_train_trials": int(len(tr)),
                "n_test_trials": int(len(te)),
            }
        )

    return pd.DataFrame(rows)


def _build_warm_start_prior(
    actions: List[int],
    reward_model: RewardModel,
    constraint_model: ConstraintModel,
) -> Dict[int, Tuple[int, float, float]]:
    """
    Returns mapping: action -> (n0, reward_mean, constraint_mean).

    n0 uses available sample sizes from both reward and constraint sources (conservative min).
    """
    prior: Dict[int, Tuple[int, float, float]] = {}
    for a in actions:
        n_r = int(getattr(reward_model, "n_samples", {}).get(a, 0))
        n_c = int(constraint_model.n_samples(a))
        n0 = min(n_r, n_c)
        if n0 <= 0:
            continue
        prior[a] = (n0, float(reward_model.mean(a)), float(constraint_model.predict(a)))
    return prior


def _build_filter_prior(
    actions: List[int],
    constraint_model: ConstraintModel,
) -> Tuple[Dict[int, float], Dict[int, int]]:
    """Return (prior_pout_mean, prior_n_trials) per action for safety-filter initialization."""
    pout: Dict[int, float] = {}
    n: Dict[int, int] = {}
    for a in actions:
        try:
            pout[a] = float(constraint_model.predict(a))
            n[a] = int(constraint_model.n_samples(a))
        except Exception:
            continue
    return pout, n


def _apply_warm_start(alg: SafeUCB, prior: Dict[int, Tuple[int, float, float]]) -> None:
    total = 0
    for a, (n0, r_mean, c_mean) in prior.items():
        alg.n_pulls[a] = n0
        alg.cumulative_reward[a] = r_mean * n0
        alg.cumulative_constraint[a] = c_mean * n0
        total += n0
    alg.t = total


def _run_one(
    method: str,
    actions: List[int],
    reward_model: RewardModel,
    constraint_model: ConstraintModel,
    epsilon: float,
    T: int,
    seed: int,
    warm_start_prior: Optional[Dict[int, Tuple[int, float, float]]] = None,
    early_k: int = 100,
    tail_k: int = 100,
    after_switch_k: int = 50,
    constraint_model_2: Optional[ConstraintModel] = None,
    switch_at: Optional[int] = None,
    constraint_ci: str = "t_dependent",
    constraint_delta: float = 0.05,
    init_strategy: str = "round_robin",
    filter_margin: float = 0.0,
    filter_prior_pout: Optional[Dict[int, float]] = None,
    filter_prior_n: Optional[Dict[int, int]] = None,
    filter_prior_weight: float = 1.0,
    filter_reset_on_switch: bool = False,
) -> Dict:
    rng = np.random.default_rng(seed)

    if method == "safe_ucb":
        alg = SafeUCB(
            actions,
            reward_model,
            constraint_model,
            epsilon,
            seed=seed,
            constraint_ci=constraint_ci,
            constraint_delta=constraint_delta,
            init_strategy=init_strategy,
        )
        if warm_start_prior:
            _apply_warm_start(alg, warm_start_prior)
    elif method == "filter_ucb_online":
        alg = SafetyFilterUCB(
            actions=actions,
            reward_model=reward_model,
            epsilon=epsilon,
            margin=filter_margin,
            seed=seed,
            constraint_ci=constraint_ci,
            constraint_delta=constraint_delta,
            prior_pout=filter_prior_pout,
            prior_n=filter_prior_n,
            prior_weight=filter_prior_weight,
        )
    elif method == "ucb":
        alg = UCB(actions, seed=seed)
    elif method == "filter_ucb":
        # Action-masked UCB: actions are already filtered by the caller.
        alg = UCB(actions, seed=seed)
    elif method == "fixed_ccs":
        alg = FixedCCS(actions, seed=seed)
    elif method == "oracle":
        alg = Oracle(actions, reward_model, constraint_model, epsilon, seed=seed)
    else:
        raise ValueError(f"unknown method: {method}")

    total_reward = 0.0
    total_viol = 0.0
    viol_early = 0.0
    viol_tail = 0.0
    viol_after_switch = 0.0
    viol_first_after_switch_k = 0.0

    for t in range(T):
        if method == "filter_ucb_online" and switch_at is not None and t == int(switch_at):
            # Optional safety policy for detected shifts: discount constraint history.
            if filter_reset_on_switch:
                alg.on_switch(discount=float(filter_prior_weight))

        a = alg.select_action(context=0.5)
        r = reward_model.sample(a, rng)

        cm_t = constraint_model
        if constraint_model_2 is not None and switch_at is not None and t >= int(switch_at):
            cm_t = constraint_model_2
        v = cm_t.sample_violation(a, rng)
        alg.update(a, r, v)

        total_reward += r
        total_viol += v
        if t < early_k:
            viol_early += v
        if t >= max(0, T - tail_k):
            viol_tail += v
        if switch_at is not None and t >= int(switch_at):
            viol_after_switch += v
            if t < int(switch_at) + int(after_switch_k):
                viol_first_after_switch_k += v

    diag = getattr(alg, "diagnostics", lambda: {})()  # SafeUCB only
    return {
        "total_reward": total_reward,
        "avg_cost": -total_reward / T,
        "violation_rate": total_viol / T,
        "violations_first_k": viol_early,
        "violations_last_k": viol_tail,
        "violations_after_switch": viol_after_switch if switch_at is not None else float("nan"),
        "violations_first_k_after_switch": (
            viol_first_after_switch_k if switch_at is not None else float("nan")
        ),
        "safe_set_empty_rate": float(diag.get("safe_set_empty_rate", float("nan"))),
        "safe_set_size_mean": float(diag.get("safe_set_size_mean", float("nan"))),
        "n_pulls": dict(getattr(alg, "n_pulls", {})),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="", help="Output directory (default: results/phase2_offline_studies_YYYY-MM-DD_v01)")
    ap.add_argument(
        "--reward-mode",
        default="per_adv",
        choices=["per_adv", "per_60s"],
        help="Reward mode: per_adv (uJ/adv) or per_60s (mJ/60s)",
    )
    ap.add_argument(
        "--constraint-ci",
        default="t_dependent",
        choices=["t_dependent", "hoeffding", "wilson", "beta"],
        help="Constraint upper CI: t_dependent (legacy), hoeffding (fixed-delta), wilson (score), beta (posterior quantile)",
    )
    ap.add_argument(
        "--constraint-delta",
        type=float,
        default=0.05,
        help="One-sided delta for constraint CI when using --constraint-ci hoeffding|beta (e.g., 0.05)",
    )
    ap.add_argument(
        "--init-strategy",
        default="round_robin",
        choices=["round_robin", "safe_seed", "baseline_only"],
        help="Safe-UCB cold-start strategy (safe_seed avoids seeding unsafe actions)",
    )
    ap.add_argument(
        "--after-switch-k",
        type=int,
        default=50,
        help="Window size K for violations_first_K_after_switch (only for switch scenarios)",
    )
    ap.add_argument(
        "--gateb-prior-weights",
        default="1.0,0.5,0.2,0.0",
        help="Comma-separated prior weights for Gate B sweeps (e.g., 1.0,0.5,0.2,0.0)",
    )
    ap.add_argument(
        "--gateb-margins",
        default="0,0.01,0.02,0.03",
        help="Comma-separated safety margins m for Gate B sweeps (safe if UCB <= epsilon-m)",
    )
    ap.add_argument(
        "--gateb-reset-on-switch",
        default="0,1",
        help="Comma-separated 0/1 for whether to discount constraint history at switch time",
    )
    ap.add_argument("--T", type=int, default=1000)
    ap.add_argument("--n-reps", type=int, default=100)
    ap.add_argument("--base-seed", type=lambda s: int(s, 0), default=DEFAULT_BASE_SEED)
    args = ap.parse_args()

    def parse_float_list(s: str) -> List[float]:
        out: List[float] = []
        for tok in str(s).split(","):
            tok = tok.strip()
            if not tok:
                continue
            out.append(float(tok))
        return out

    def parse_bool01_list(s: str) -> List[bool]:
        out: List[bool] = []
        for tok in str(s).split(","):
            tok = tok.strip()
            if not tok:
                continue
            out.append(bool(int(tok)))
        return out

    gateb_prior_weights = parse_float_list(args.gateb_prior_weights)
    gateb_margins = parse_float_list(args.gateb_margins)
    gateb_reset_on_switch = parse_bool01_list(args.gateb_reset_on_switch)

    out_dir = Path(args.out_dir) if args.out_dir else Path(f"results/phase2_offline_studies_{_today_slug()}_v01")
    _ensure_dir(out_dir)

    # ------------------------------------------------------------------
    # Models / environments
    # ------------------------------------------------------------------
    reward_data_dir = _find_unique_dir(Path("data"), "deltae_v3rig_sweep_2026-01-21_v02")
    reward_model = RewardModel(str(reward_data_dir), reward_mode=args.reward_mode)
    cost_unit = getattr(reward_model, "cost_unit", "")

    envs: Dict[str, EnvSpec] = {
        "E1_scan90_stress_v5": EnvSpec(
            env_id="E1_scan90_stress_v5",
            constraint_sources=[
                "results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_full_scan90_v5.csv",
            ],
        ),
        "E2_fixed_v01": EnvSpec(
            env_id="E2_fixed_v01",
            constraint_sources=[
                str(_find_unique_dir(Path("data"), "phase1_e2_fixed_sweep_2026-01-21_v01")),
            ],
        ),
        "E1_uccs_d4b_scan90": EnvSpec(
            env_id="E1_uccs_d4b_scan90",
            constraint_sources=["uccs_d4b_scan90/metrics/01/per_trial.csv"],
        ),
        "E1_uccs_d4b_scan70": EnvSpec(
            env_id="E1_uccs_d4b_scan70",
            constraint_sources=["uccs_d4b_scan70/metrics/01_fixed/per_trial.csv"],
        ),
    }

    constraint_cache: Dict[Tuple[str, float], ConstraintModel] = {}

    def get_constraint(env_id: str, tau_s: float) -> ConstraintModel:
        key = (env_id, float(tau_s))
        if key not in constraint_cache:
            spec = envs[env_id]
            constraint_cache[key] = ConstraintModel(spec.constraint_sources, tau=tau_s)
        return constraint_cache[key]

    # ------------------------------------------------------------------
    # 1) Deterministic tables (tradeoff + epsilon/tau sensitivity)
    # ------------------------------------------------------------------
    trade_rows = []
    sens_rows = []
    for env_id in ["E1_scan90_stress_v5", "E2_fixed_v01", "E1_uccs_d4b_scan90", "E1_uccs_d4b_scan70"]:
        cm_1 = get_constraint(env_id, 1.0)
        cm_2 = get_constraint(env_id, 2.0)
        actions_available = sorted({*cm_1._stats.keys(), *cm_2._stats.keys()})
        for a in actions_available:
            if a not in getattr(reward_model, "mu_c", {}):
                # Reward model is not defined for non-fixed actions (e.g., policy rows); skip.
                continue
            trade_rows.append(
                {
                    "env_id": env_id,
                    "action_ms": a,
                    "reward_mode": args.reward_mode,
                    "cost_mean": -reward_model.mean(a),
                    "cost_std": reward_model.std(a),
                    "cost_unit": cost_unit,
                    "pout_1s": cm_1.predict(a),
                    "pout_2s": cm_2.predict(a),
                }
            )
            for eps in (0.03, 0.10):
                sens_rows.append(
                    {
                        "env_id": env_id,
                        "action_ms": a,
                        "epsilon": eps,
                        "safe_tau1": cm_1.predict(a) <= eps,
                        "safe_tau2": cm_2.predict(a) <= eps,
                    }
                )

    pd.DataFrame(trade_rows).sort_values(["env_id", "action_ms"]).to_csv(out_dir / "tradeoff_table.csv", index=False)
    pd.DataFrame(sens_rows).sort_values(["env_id", "epsilon", "action_ms"]).to_csv(out_dir / "epsilon_tau_sensitivity.csv", index=False)

    # ------------------------------------------------------------------
    # 2) Model validity (simple splits)
    # ------------------------------------------------------------------
    rng_split = np.random.default_rng(args.base_seed ^ 0xA5A5A5A5)

    reward_valid = _reward_split_validity(
        trials_csv=Path("results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv"),
        train_frac=0.7,
        rng=rng_split,
        reward_mode=args.reward_mode,
    )
    reward_valid.to_csv(out_dir / "validity_reward_split.csv", index=False)

    cm_e2_tau1 = get_constraint("E2_fixed_v01", 1.0)
    validity_e2 = _constraint_split_validity_e2_fixed(
        model=cm_e2_tau1,
        epsilon=0.10,
        tau_s=1.0,
        train_frac=0.6,
        rng=rng_split,
    )
    validity_e2.to_csv(out_dir / "validity_constraint_e2_split.csv", index=False)

    # ------------------------------------------------------------------
    # 3) Bandit simulations (selected scenarios)
    # ------------------------------------------------------------------
    scenarios: List[Scenario] = [
        # Gate A: safe actions are multiple; the algorithm should converge to the best safe arm.
        Scenario(
            scenario_id="E1_actions_100_500_1000_2000_cold",
            env_id="E1_scan90_stress_v5",
            actions=[100, 500, 1000, 2000],
            tau_s=1.0,
            epsilon=0.10,
        ),
        # Diagnostic: in E2, tau=2s makes {500,1000} safe while 2000 is unsafe.
        Scenario(
            scenario_id="E2_actions_500_1000_2000_tau2_cold",
            env_id="E2_fixed_v01",
            actions=[500, 1000, 2000],
            tau_s=2.0,
            epsilon=0.10,
        ),
        Scenario(
            scenario_id="E2_actions_500_1000_2000_cold",
            env_id="E2_fixed_v01",
            actions=[500, 1000, 2000],
            tau_s=1.0,
            epsilon=0.10,
        ),
        Scenario(
            scenario_id="E2_actions_500_1000_2000_warm_in_domain",
            env_id="E2_fixed_v01",
            actions=[500, 1000, 2000],
            tau_s=1.0,
            epsilon=0.10,
            prior_env_id="E2_fixed_v01",
        ),
        Scenario(
            scenario_id="E2_actions_500_1000_2000_warm_shift_from_E1",
            env_id="E2_fixed_v01",
            actions=[500, 1000, 2000],
            tau_s=1.0,
            epsilon=0.10,
            prior_env_id="E1_scan90_stress_v5",
            filter_env_id="E1_scan90_stress_v5",
        ),
        # Gate B (explicit shift): start in E1, then switch to E2 mid-run.
        Scenario(
            scenario_id="E1_to_E2_actions_500_1000_2000_switch_mid",
            env_id="E1_scan90_stress_v5",
            actions=[500, 1000, 2000],
            tau_s=1.0,
            epsilon=0.10,
            filter_env_id="E1_scan90_stress_v5",
            switch_env_id="E2_fixed_v01",
            switch_at_frac=0.5,
        ),
        Scenario(
            scenario_id="scan70_actions_100_500_cold",
            env_id="E1_uccs_d4b_scan70",
            actions=[100, 500],
            tau_s=1.0,
            epsilon=0.10,
        ),
        Scenario(
            scenario_id="scan70_actions_100_500_warm_from_scan90",
            env_id="E1_uccs_d4b_scan70",
            actions=[100, 500],
            tau_s=1.0,
            epsilon=0.10,
            prior_env_id="E1_uccs_d4b_scan90",
            filter_env_id="E1_uccs_d4b_scan90",
        ),
        # Gate C (minimal): nonstationary constraint switch scan90 -> scan70 (mid-run).
        Scenario(
            scenario_id="scan90_to_scan70_actions_100_500_switch_mid",
            env_id="E1_uccs_d4b_scan90",
            actions=[100, 500],
            tau_s=1.0,
            epsilon=0.10,
            switch_env_id="E1_uccs_d4b_scan70",
            switch_at_frac=0.5,
        ),
    ]

    base_methods = ["safe_ucb", "filter_ucb", "ucb", "fixed_ccs", "oracle"]
    rep_rows = []
    union_actions = sorted({a for sc in scenarios for a in sc.actions})

    for sc in scenarios:
        cm = get_constraint(sc.env_id, sc.tau_s)
        cm2 = get_constraint(sc.switch_env_id, sc.tau_s) if sc.switch_env_id else None
        switch_at = None
        if sc.switch_env_id and sc.switch_at_frac is not None:
            switch_at = int(round(args.T * float(sc.switch_at_frac)))
        # Gate B (shift at start): when prior != target, treat the entire run as
        # "after switch" so that we can report violations_first_K_after_switch.
        if switch_at is None and sc.prior_env_id and sc.prior_env_id != sc.env_id:
            switch_at = 0

        prior = None
        if sc.prior_env_id:
            prior_cm = get_constraint(sc.prior_env_id, sc.tau_s)
            prior = _build_warm_start_prior(sc.actions, reward_model, prior_cm)

        for rep in range(args.n_reps):
            seed = int(args.base_seed + rep)
            # Oracle first (for regret baseline). For nonstationary scenarios, keep NaN.
            oracle_total_reward = float("nan")
            if sc.switch_env_id is None:
                oracle_out = _run_one(
                    method="oracle",
                    actions=sc.actions,
                    reward_model=reward_model,
                    constraint_model=cm,
                    epsilon=sc.epsilon,
                    T=args.T,
                    seed=seed,
                )
                oracle_total_reward = float(oracle_out["total_reward"])

            for m in base_methods:
                actions_used = list(sc.actions)
                filter_env_id = sc.filter_env_id or sc.env_id
                if m == "filter_ucb":
                    fm = get_constraint(filter_env_id, sc.tau_s)
                    allowed: List[int] = []
                    for a in sc.actions:
                        try:
                            if fm.is_safe(a, sc.epsilon):
                                allowed.append(a)
                        except Exception:
                            continue
                    if not allowed:
                        allowed = [min(sc.actions)]
                    actions_used = sorted(set(allowed))

                warm = prior if (m == "safe_ucb" and prior is not None) else None
                out = _run_one(
                    method=m,
                    actions=actions_used,
                    reward_model=reward_model,
                    constraint_model=cm,
                    epsilon=sc.epsilon,
                    T=args.T,
                    seed=seed,
                    warm_start_prior=warm,
                    constraint_model_2=cm2,
                    switch_at=switch_at,
                    constraint_ci=args.constraint_ci,
                    constraint_delta=args.constraint_delta,
                    init_strategy=args.init_strategy,
                    after_switch_k=args.after_switch_k,
                )

                n_pulls = out.get("n_pulls", {})
                distinct_actions = sum(1 for a in union_actions if int(n_pulls.get(a, 0)) > 0)
                rep_rows.append(
                    {
                        "scenario_id": sc.scenario_id,
                        "env_id": sc.env_id,
                        "prior_env_id": sc.prior_env_id or "",
                        "filter_env_id": sc.filter_env_id or "",
                        "switch_env_id": sc.switch_env_id or "",
                        "switch_at": int(switch_at) if switch_at is not None else "",
                        "actions": ",".join(str(a) for a in sc.actions),
                        "actions_used": ",".join(str(a) for a in actions_used),
                        "tau_s": sc.tau_s,
                        "epsilon": sc.epsilon,
                        "rep": rep,
                        "method": m if warm is None else "safe_ucb_warm",
                        "reward_mode": args.reward_mode,
                        "cost_unit": cost_unit,
                        "constraint_ci": args.constraint_ci,
                        "constraint_delta": args.constraint_delta,
                        "init_strategy": args.init_strategy,
                        "avg_cost": out["avg_cost"],
                        "violation_rate": out["violation_rate"],
                        "violations_first_100": out["violations_first_k"],
                        "violations_last_100": out["violations_last_k"],
                        "violations_after_switch": out["violations_after_switch"],
                        "after_switch_k": int(args.after_switch_k),
                        "violations_first_after_switch_k": out["violations_first_k_after_switch"],
                        "safe_set_empty_rate": out["safe_set_empty_rate"],
                        "safe_set_size_mean": out["safe_set_size_mean"],
                        "filter_margin": float("nan"),
                        "filter_prior_weight": float("nan"),
                        "filter_reset_on_switch": "",
                        "distinct_actions_pulled": distinct_actions,
                        "regret_vs_oracle": oracle_total_reward - out["total_reward"],
                        **{f"pull_{a}": int(n_pulls.get(a, 0)) for a in union_actions},
                    }
                )

            # ------------------------------------------------------------------
            # Gate B sweeps: Safety Filter + UCB (online-updated masking)
            # ------------------------------------------------------------------
            filter_env_id = sc.filter_env_id or sc.env_id
            fm = get_constraint(filter_env_id, sc.tau_s)
            prior_pout, prior_n = _build_filter_prior(sc.actions, fm)

            variants = []
            # Default (single) variant for all scenarios.
            variants.append((1.0, 0.0, False))

            # Gate B (shift at start): sweep prior_weight and margin (E1 -> E2).
            if sc.scenario_id.endswith("warm_shift_from_E1"):
                for w in gateb_prior_weights:
                    for mrg in gateb_margins:
                        variants.append((float(w), float(mrg), False))

            # Gate B (explicit mid-run switch): also sweep reset_on_switch.
            if sc.switch_env_id is not None and sc.scenario_id.startswith("E1_to_E2_"):
                for w in gateb_prior_weights:
                    for mrg in gateb_margins:
                        for reset in gateb_reset_on_switch:
                            variants.append((float(w), float(mrg), bool(reset)))

            seen_labels = set()
            for w, mrg, reset in variants:
                label = f"filter_ucb_online_w{w:g}_m{mrg:g}_r{int(reset)}"
                if label in seen_labels:
                    continue
                seen_labels.add(label)

                out = _run_one(
                    method="filter_ucb_online",
                    actions=list(sc.actions),
                    reward_model=reward_model,
                    constraint_model=cm,
                    epsilon=sc.epsilon,
                    T=args.T,
                    seed=seed,
                    constraint_model_2=cm2,
                    switch_at=switch_at,
                    constraint_ci=args.constraint_ci,
                    constraint_delta=args.constraint_delta,
                    after_switch_k=args.after_switch_k,
                    filter_margin=mrg,
                    filter_prior_pout=prior_pout,
                    filter_prior_n=prior_n,
                    filter_prior_weight=w,
                    filter_reset_on_switch=reset,
                )

                n_pulls = out.get("n_pulls", {})
                distinct_actions = sum(1 for a in union_actions if int(n_pulls.get(a, 0)) > 0)
                rep_rows.append(
                    {
                        "scenario_id": sc.scenario_id,
                        "env_id": sc.env_id,
                        "prior_env_id": sc.prior_env_id or "",
                        "filter_env_id": filter_env_id,
                        "switch_env_id": sc.switch_env_id or "",
                        "switch_at": int(switch_at) if switch_at is not None else "",
                        "actions": ",".join(str(a) for a in sc.actions),
                        "actions_used": ",".join(str(a) for a in sc.actions),
                        "tau_s": sc.tau_s,
                        "epsilon": sc.epsilon,
                        "rep": rep,
                        "method": label,
                        "reward_mode": args.reward_mode,
                        "cost_unit": cost_unit,
                        "constraint_ci": args.constraint_ci,
                        "constraint_delta": args.constraint_delta,
                        "init_strategy": args.init_strategy,
                        "avg_cost": out["avg_cost"],
                        "violation_rate": out["violation_rate"],
                        "violations_first_100": out["violations_first_k"],
                        "violations_last_100": out["violations_last_k"],
                        "violations_after_switch": out["violations_after_switch"],
                        "after_switch_k": int(args.after_switch_k),
                        "violations_first_after_switch_k": out["violations_first_k_after_switch"],
                        "safe_set_empty_rate": out["safe_set_empty_rate"],
                        "safe_set_size_mean": out["safe_set_size_mean"],
                        "filter_margin": float(mrg),
                        "filter_prior_weight": float(w),
                        "filter_reset_on_switch": int(reset),
                        "distinct_actions_pulled": distinct_actions,
                        "regret_vs_oracle": oracle_total_reward - out["total_reward"],
                        **{f"pull_{a}": int(n_pulls.get(a, 0)) for a in union_actions},
                    }
                )

    df_rep = pd.DataFrame(rep_rows)
    df_rep.to_csv(out_dir / "sim_replicates.csv", index=False)

    agg = (
        df_rep.groupby(["scenario_id", "method"], as_index=False)
        .agg(
            env_id=("env_id", "first"),
            prior_env_id=("prior_env_id", "first"),
            filter_env_id=("filter_env_id", "first"),
            switch_env_id=("switch_env_id", "first"),
            switch_at=("switch_at", "first"),
            after_switch_k=("after_switch_k", "first"),
            actions=("actions", "first"),
            actions_used=("actions_used", "first"),
            tau_s=("tau_s", "first"),
            epsilon=("epsilon", "first"),
            reward_mode=("reward_mode", "first"),
            cost_unit=("cost_unit", "first"),
            constraint_ci=("constraint_ci", "first"),
            constraint_delta=("constraint_delta", "first"),
            init_strategy=("init_strategy", "first"),
            filter_margin=("filter_margin", "first"),
            filter_prior_weight=("filter_prior_weight", "first"),
            filter_reset_on_switch=("filter_reset_on_switch", "first"),
            avg_cost_mean=("avg_cost", "mean"),
            avg_cost_std=("avg_cost", "std"),
            violation_rate_mean=("violation_rate", "mean"),
            violation_rate_std=("violation_rate", "std"),
            violations_first_100_mean=("violations_first_100", "mean"),
            violations_first_100_std=("violations_first_100", "std"),
            violations_last_100_mean=("violations_last_100", "mean"),
            violations_last_100_std=("violations_last_100", "std"),
            violations_after_switch_mean=("violations_after_switch", "mean"),
            violations_after_switch_std=("violations_after_switch", "std"),
            violations_first_after_switch_k_mean=("violations_first_after_switch_k", "mean"),
            violations_first_after_switch_k_std=("violations_first_after_switch_k", "std"),
            safe_set_empty_rate_mean=("safe_set_empty_rate", "mean"),
            safe_set_empty_rate_std=("safe_set_empty_rate", "std"),
            safe_set_size_mean_mean=("safe_set_size_mean", "mean"),
            safe_set_size_mean_std=("safe_set_size_mean", "std"),
            distinct_actions_pulled_mean=("distinct_actions_pulled", "mean"),
            distinct_actions_pulled_std=("distinct_actions_pulled", "std"),
            pull_100_mean=("pull_100", "mean"),
            pull_1000_mean=("pull_1000", "mean"),
            pull_2000_mean=("pull_2000", "mean"),
            pull_500_mean=("pull_500", "mean"),
            regret_vs_oracle_mean=("regret_vs_oracle", "mean"),
            regret_vs_oracle_std=("regret_vs_oracle", "std"),
            n_reps=("rep", "nunique"),
        )
        .sort_values(["scenario_id", "method"])
    )
    agg.to_csv(out_dir / "sim_summary.csv", index=False)

    # Lightweight index for human reading.
    (out_dir / "README.md").write_text(
        "\n".join(
            [
                "# Phase 2 Offline Studies (auto-generated)",
                "",
                f"- Date: {dt.datetime.now().strftime('%Y-%m-%d')}",
                f"- Script: `scripts/phase2_offline_eval/run_offline_studies.py`",
                f"- reward_mode: {args.reward_mode} ({cost_unit})",
                f"- Safe-UCB: constraint_ci={args.constraint_ci}, delta={args.constraint_delta}, init_strategy={args.init_strategy}",
                f"- after_switch_k: {args.after_switch_k}",
                f"- GateB sweep: prior_weights={args.gateb_prior_weights}, margins={args.gateb_margins}, reset_on_switch={args.gateb_reset_on_switch}",
                "",
                "## Outputs",
                "",
                "- `tradeoff_table.csv`: Reward/constraint table per env/action",
                "- `epsilon_tau_sensitivity.csv`: Safe/unsafe table for (epsilon,tau)",
                "- `validity_reward_split.csv`: Reward model split check (train/test)",
                "- `validity_constraint_e2_split.csv`: Constraint split check (E2 fixed sweep)",
                "- `sim_replicates.csv`: Per-replicate simulation metrics",
                "- `sim_summary.csv`: Aggregated simulation metrics (includes diagnostics + action-pull means)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"[OK] Wrote: {out_dir}")


if __name__ == "__main__":
    main()
