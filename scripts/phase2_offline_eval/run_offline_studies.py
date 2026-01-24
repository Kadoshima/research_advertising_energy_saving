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
from models.safe_ucb import FixedCCS, Oracle, SafeUCB, UCB


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


def _today_slug() -> str:
    return dt.date.today().isoformat()


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _reward_split_validity(
    trials_csv: Path,
    train_frac: float,
    rng: np.random.Generator,
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

        # Estimate cost per event using train E_off
        c_train = (tr["e_total_mj"] - e_off_train) / tr["adv_count"] * 1000.0
        c_test = (te["e_total_mj"] - e_off_train) / te["adv_count"] * 1000.0

        mu_train = float(c_train.mean())
        mae_test = float(np.mean(np.abs(c_test - mu_train)))
        rows.append(
            {
                "action_ms": int(mode_ms),
                "e_off_train_mJ": e_off_train,
                "mu_c_train_uJ_event": mu_train,
                "mu_c_test_uJ_event_mean": float(c_test.mean()),
                "mae_test_uJ_event": mae_test,
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
) -> Dict:
    rng = np.random.default_rng(seed)

    if method == "safe_ucb":
        alg = SafeUCB(actions, reward_model, constraint_model, epsilon, seed=seed)
        if warm_start_prior:
            _apply_warm_start(alg, warm_start_prior)
    elif method == "ucb":
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

    for t in range(T):
        a = alg.select_action(context=0.5)
        r = reward_model.sample(a, rng)
        v = constraint_model.sample_violation(a, rng)
        alg.update(a, r, v)

        total_reward += r
        total_viol += v
        if t < early_k:
            viol_early += v

    return {
        "total_reward": total_reward,
        "avg_energy_uJ_event": -total_reward / T,
        "violation_rate": total_viol / T,
        "violations_first_k": viol_early,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="", help="Output directory (default: results/phase2_offline_studies_YYYY-MM-DD_v01)")
    ap.add_argument("--T", type=int, default=1000)
    ap.add_argument("--n-reps", type=int, default=100)
    ap.add_argument("--base-seed", type=lambda s: int(s, 0), default=DEFAULT_BASE_SEED)
    args = ap.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else Path(f"results/phase2_offline_studies_{_today_slug()}_v01")
    _ensure_dir(out_dir)

    # ------------------------------------------------------------------
    # Models / environments
    # ------------------------------------------------------------------
    reward_data_dir = _find_unique_dir(Path("data"), "deltae_v3rig_sweep_2026-01-21_v02")
    reward_model = RewardModel(str(reward_data_dir))

    envs: Dict[str, EnvSpec] = {
        "E1_scan90_stress_v5": EnvSpec(
            env_id="E1_scan90_stress_v5",
            constraint_sources=[
                "results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_modes_scan90_v5.csv",
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
                    "mu_c_uJ_event": -reward_model.mean(a),
                    "sigma_c_uJ_event": reward_model.std(a),
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
        ),
    ]

    methods = ["safe_ucb", "ucb", "fixed_ccs", "oracle"]
    rep_rows = []

    for sc in scenarios:
        cm = get_constraint(sc.env_id, sc.tau_s)
        prior = None
        if sc.prior_env_id:
            prior_cm = get_constraint(sc.prior_env_id, sc.tau_s)
            prior = _build_warm_start_prior(sc.actions, reward_model, prior_cm)

        for rep in range(args.n_reps):
            seed = int(args.base_seed + rep)
            # Oracle first (for regret baseline)
            oracle_out = _run_one(
                method="oracle",
                actions=sc.actions,
                reward_model=reward_model,
                constraint_model=cm,
                epsilon=sc.epsilon,
                T=args.T,
                seed=seed,
            )
            for m in methods:
                warm = prior if (m == "safe_ucb" and prior is not None and "warm" in sc.scenario_id) else None
                out = _run_one(
                    method=m,
                    actions=sc.actions,
                    reward_model=reward_model,
                    constraint_model=cm,
                    epsilon=sc.epsilon,
                    T=args.T,
                    seed=seed,
                    warm_start_prior=warm,
                )
                rep_rows.append(
                    {
                        "scenario_id": sc.scenario_id,
                        "env_id": sc.env_id,
                        "prior_env_id": sc.prior_env_id or "",
                        "actions": ",".join(str(a) for a in sc.actions),
                        "tau_s": sc.tau_s,
                        "epsilon": sc.epsilon,
                        "rep": rep,
                        "method": m if warm is None else "safe_ucb_warm",
                        "avg_energy_uJ_event": out["avg_energy_uJ_event"],
                        "violation_rate": out["violation_rate"],
                        "violations_first_100": out["violations_first_k"],
                        "regret_vs_oracle": oracle_out["total_reward"] - out["total_reward"],
                    }
                )

    df_rep = pd.DataFrame(rep_rows)
    df_rep.to_csv(out_dir / "sim_replicates.csv", index=False)

    agg = (
        df_rep.groupby(["scenario_id", "method"], as_index=False)
        .agg(
            avg_energy_uJ_event_mean=("avg_energy_uJ_event", "mean"),
            avg_energy_uJ_event_std=("avg_energy_uJ_event", "std"),
            violation_rate_mean=("violation_rate", "mean"),
            violation_rate_std=("violation_rate", "std"),
            violations_first_100_mean=("violations_first_100", "mean"),
            violations_first_100_std=("violations_first_100", "std"),
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
                "",
                "## Outputs",
                "",
                "- `tradeoff_table.csv`: Reward/constraint table per env/action",
                "- `epsilon_tau_sensitivity.csv`: Safe/unsafe table for (epsilon,tau)",
                "- `validity_reward_split.csv`: Reward model split check (train/test)",
                "- `validity_constraint_e2_split.csv`: Constraint split check (E2 fixed sweep)",
                "- `sim_replicates.csv`: Per-replicate simulation metrics",
                "- `sim_summary.csv`: Aggregated simulation metrics",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"[OK] Wrote: {out_dir}")


if __name__ == "__main__":
    main()
