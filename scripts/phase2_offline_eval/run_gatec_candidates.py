"""
Gate C candidate check runner.

Goal:
- Evaluate a *small* shortlist of (w, m, reset) for filter_ucb_online under a
  non-stationary constraint switch (scan90 -> scan70).

Why tau=2.0 here?
- For tau=1.0 with the available uccs_d4b datasets (actions={100,500}), the safe
  set tends to collapse to a single action, making "tracking" uninformative.
- tau=2.0 creates a meaningful safe-set change:
    scan90: {100,500} can be safe
    scan70: 500 becomes (slightly) unsafe
  so we can measure how quickly the policy backs off after a switch.

Run from repo root, e.g.:
  python scripts/phase2_offline_eval/run_gatec_candidates.py --out-dir results/phase2_gatec_candidates_2026-01-26_v01
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _today_slug() -> str:
    from datetime import datetime, timezone, timedelta

    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d")


def _find_unique_dir(root: Path, name_substr: str) -> Path:
    matches = [p for p in root.rglob("*") if p.is_dir() and name_substr in p.name]
    if not matches:
        raise FileNotFoundError(f"Could not find dir containing {name_substr!r} under {root}")
    if len(matches) == 1:
        return matches[0]
    # Prefer the shortest path (usually the canonical one).
    matches.sort(key=lambda p: len(str(p)))
    return matches[0]


def _build_filter_prior(actions: List[int], constraint_model) -> Tuple[Dict[int, float], Dict[int, int]]:
    pout: Dict[int, float] = {}
    n: Dict[int, int] = {}
    for a in actions:
        pout[a] = float(constraint_model.predict(a))
        n[a] = int(constraint_model.n_samples(a))
    return pout, n


@dataclass(frozen=True)
class Candidate:
    w: float
    m: float
    reset: bool
    label: str


def _load_candidates_from_pareto(run_dir: Path, top_n: int) -> List[Candidate]:
    pareto_path = run_dir / "gateb_pareto_front.csv"
    if not pareto_path.exists():
        raise FileNotFoundError(pareto_path)
    df = pd.read_csv(pareto_path)
    df = df.sort_values(["viol_first_worst_p95", "cost_worst_mean"]).head(max(1, int(top_n)))
    out: List[Candidate] = []
    for _, r in df.iterrows():
        out.append(
            Candidate(
                w=float(r["w"]),
                m=float(r["m"]),
                reset=bool(int(r["reset"])),
                label=str(r["method"]),
            )
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--gateb-run-dir",
        type=str,
        default="results/phase2_offline_studies_2026-01-26_v04",
        help="v04 output dir (used to load gateb_pareto_front.csv for candidate list)",
    )
    ap.add_argument("--top-n", type=int, default=3, help="How many candidates to evaluate")
    ap.add_argument(
        "--m-list",
        type=str,
        default="",
        help="Optional comma-separated margin list; if set, overrides candidate selection from Gate B Pareto",
    )
    ap.add_argument(
        "--w",
        type=float,
        default=0.0,
        help="prior_weight w for --m-list sweep (ignored when using Gate B Pareto candidates)",
    )
    ap.add_argument(
        "--reset",
        type=int,
        default=1,
        help="reset_on_switch (0/1) for --m-list sweep (ignored when using Gate B Pareto candidates)",
    )
    ap.add_argument("--out-dir", type=str, default="", help="Output directory (default: results/phase2_gatec_candidates_<date>_v01)")
    ap.add_argument("--T", type=int, default=1000)
    ap.add_argument("--n-reps", type=int, default=100)
    ap.add_argument("--base-seed", type=lambda s: int(s, 0), default=int("0xD4B40201", 0))
    ap.add_argument("--after-switch-k", type=int, default=50)
    ap.add_argument("--tau-s", type=float, default=2.0)
    ap.add_argument("--epsilon", type=float, default=0.10)
    ap.add_argument("--reward-mode", type=str, default="per_60s", choices=["per_adv", "per_60s"])
    ap.add_argument("--constraint-ci", type=str, default="wilson", choices=["t_dependent", "hoeffding", "wilson", "beta"])
    ap.add_argument("--constraint-delta", type=float, default=0.05)
    ap.add_argument("--init-strategy", type=str, default="safe_seed", choices=["round_robin", "safe_seed", "baseline_only"])
    args = ap.parse_args()

    gateb_run_dir = Path(args.gateb_run_dir)
    if str(args.m_list).strip():
        ms: List[float] = []
        for tok in str(args.m_list).split(","):
            tok = tok.strip()
            if not tok:
                continue
            ms.append(float(tok))
        w0 = float(args.w)
        reset0 = bool(int(args.reset))
        candidates = [
            Candidate(w=w0, m=float(m), reset=reset0, label=f"filter_ucb_online_w{w0:g}_m{float(m):g}_r{int(reset0)}")
            for m in ms
        ]
    else:
        candidates = _load_candidates_from_pareto(gateb_run_dir, top_n=int(args.top_n))

    out_dir = Path(args.out_dir) if args.out_dir else Path(f"results/phase2_gatec_candidates_{_today_slug()}_v01")
    _ensure_dir(out_dir)

    # Import the shared simulation runner (not a package; add path).
    import sys

    phase2_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(phase2_dir))
    import run_offline_studies as ros  # type: ignore

    # Models
    reward_data_dir = _find_unique_dir(Path("data"), "deltae_v3rig_sweep_2026-01-21_v02")
    reward_model = ros.RewardModel(str(reward_data_dir), reward_mode=args.reward_mode)
    cost_unit = getattr(reward_model, "cost_unit", "")

    # Constraint models (nonstationary: scan90 -> scan70 mid-run)
    env_scan90 = ros.ConstraintModel(["uccs_d4b_scan90/metrics/01/per_trial.csv"], tau=float(args.tau_s))
    env_scan70 = ros.ConstraintModel(["uccs_d4b_scan70/metrics/01_fixed/per_trial.csv"], tau=float(args.tau_s))

    actions = [100, 500]
    epsilon = float(args.epsilon)
    switch_at = int(round(int(args.T) * 0.5))

    # Fixed safety mask baseline uses scan90 as filter_env (prior)
    filter_prior_pout, filter_prior_n = _build_filter_prior(actions, env_scan90)

    rep_rows: List[Dict] = []
    union_actions = list(actions)
    base_methods = ["filter_ucb", "ucb", "fixed_ccs", "safe_ucb"]

    for rep in range(int(args.n_reps)):
        seed = int(args.base_seed + rep)

        # Baselines
        for method in base_methods:
            actions_used = list(actions)
            if method == "filter_ucb":
                allowed: List[int] = []
                for a in actions:
                    if env_scan90.is_safe(a, epsilon):
                        allowed.append(int(a))
                if not allowed:
                    allowed = [min(actions)]
                actions_used = sorted(set(allowed))

            out = ros._run_one(
                method=method,
                actions=actions_used,
                reward_model=reward_model,
                constraint_model=env_scan90,
                epsilon=epsilon,
                T=int(args.T),
                seed=seed,
                constraint_model_2=env_scan70,
                switch_at=switch_at,
                constraint_ci=str(args.constraint_ci),
                constraint_delta=float(args.constraint_delta),
                init_strategy=str(args.init_strategy),
                after_switch_k=int(args.after_switch_k),
            )
            n_pulls = out.get("n_pulls", {})
            rep_rows.append(
                {
                    "scenario_id": "scan90_to_scan70_actions_100_500_tau2_switch_mid",
                    "env_id": "E1_uccs_d4b_scan90",
                    "switch_env_id": "E1_uccs_d4b_scan70",
                    "switch_at": switch_at,
                    "tau_s": float(args.tau_s),
                    "epsilon": epsilon,
                    "after_switch_k": int(args.after_switch_k),
                    "rep": rep,
                    "method": method,
                    "reward_mode": str(args.reward_mode),
                    "cost_unit": cost_unit,
                    "constraint_ci": str(args.constraint_ci),
                    "constraint_delta": float(args.constraint_delta),
                    "init_strategy": str(args.init_strategy),
                    "avg_cost": float(out["avg_cost"]),
                    "violation_rate": float(out["violation_rate"]),
                    "violations_after_switch": float(out["violations_after_switch"]),
                    "violations_first_after_switch_k": float(out["violations_first_k_after_switch"]),
                    "filter_margin": float("nan"),
                    "filter_prior_weight": float("nan"),
                    "filter_reset_on_switch": "",
                    **{f"pull_{a}": int(n_pulls.get(a, 0)) for a in union_actions},
                }
            )

        # Candidate methods
        for cand in candidates:
            out = ros._run_one(
                method="filter_ucb_online",
                actions=list(actions),
                reward_model=reward_model,
                constraint_model=env_scan90,
                epsilon=epsilon,
                T=int(args.T),
                seed=seed,
                constraint_model_2=env_scan70,
                switch_at=switch_at,
                constraint_ci=str(args.constraint_ci),
                constraint_delta=float(args.constraint_delta),
                after_switch_k=int(args.after_switch_k),
                filter_margin=float(cand.m),
                filter_prior_pout=filter_prior_pout,
                filter_prior_n=filter_prior_n,
                filter_prior_weight=float(cand.w),
                filter_reset_on_switch=bool(cand.reset),
            )
            n_pulls = out.get("n_pulls", {})
            rep_rows.append(
                {
                    "scenario_id": "scan90_to_scan70_actions_100_500_tau2_switch_mid",
                    "env_id": "E1_uccs_d4b_scan90",
                    "switch_env_id": "E1_uccs_d4b_scan70",
                    "switch_at": switch_at,
                    "tau_s": float(args.tau_s),
                    "epsilon": epsilon,
                    "after_switch_k": int(args.after_switch_k),
                    "rep": rep,
                    "method": cand.label,
                    "reward_mode": str(args.reward_mode),
                    "cost_unit": cost_unit,
                    "constraint_ci": str(args.constraint_ci),
                    "constraint_delta": float(args.constraint_delta),
                    "init_strategy": str(args.init_strategy),
                    "avg_cost": float(out["avg_cost"]),
                    "violation_rate": float(out["violation_rate"]),
                    "violations_after_switch": float(out["violations_after_switch"]),
                    "violations_first_after_switch_k": float(out["violations_first_k_after_switch"]),
                    "filter_margin": float(cand.m),
                    "filter_prior_weight": float(cand.w),
                    "filter_reset_on_switch": int(cand.reset),
                    **{f"pull_{a}": int(n_pulls.get(a, 0)) for a in union_actions},
                }
            )

    df_rep = pd.DataFrame(rep_rows)
    df_rep.to_csv(out_dir / "sim_replicates.csv", index=False)

    def mean_std(x: pd.Series) -> Tuple[float, float]:
        return float(np.mean(x)), float(np.std(x, ddof=1)) if len(x) > 1 else 0.0

    agg_rows = []
    for method, g in df_rep.groupby("method"):
        m = str(method)
        row = {
            "method": m,
            "avg_cost_mean": mean_std(g["avg_cost"])[0],
            "avg_cost_std": mean_std(g["avg_cost"])[1],
            "violation_rate_mean": mean_std(g["violation_rate"])[0],
            "violation_rate_std": mean_std(g["violation_rate"])[1],
            "violations_after_switch_mean": mean_std(g["violations_after_switch"])[0],
            "violations_after_switch_std": mean_std(g["violations_after_switch"])[1],
            "violations_first_after_switch_k_mean": mean_std(g["violations_first_after_switch_k"])[0],
            "violations_first_after_switch_k_std": mean_std(g["violations_first_after_switch_k"])[1],
            "pull_100_mean": mean_std(g["pull_100"])[0],
            "pull_500_mean": mean_std(g["pull_500"])[0],
            "filter_margin": g["filter_margin"].iloc[0],
            "filter_prior_weight": g["filter_prior_weight"].iloc[0],
            "filter_reset_on_switch": g["filter_reset_on_switch"].iloc[0],
        }
        agg_rows.append(row)
    df_sum = pd.DataFrame(agg_rows)
    df_sum = df_sum.sort_values(["violations_after_switch_mean", "avg_cost_mean"]).reset_index(drop=True)
    df_sum.to_csv(out_dir / "sim_summary.csv", index=False)

    # README
    md = []
    md.append("# Gate C candidate check (auto-generated)")
    md.append("")
    md.append(f"- Date: {_today_slug()}")
    md.append(f"- Script: `scripts/phase2_offline_eval/run_gatec_candidates.py`")
    md.append(f"- gateb_run_dir: `{gateb_run_dir.as_posix()}`")
    md.append(f"- candidates(top_n={len(candidates)}):")
    for c in candidates:
        md.append(f"  - {c.label} (w={c.w:g}, m={c.m:g}, reset={int(c.reset)})")
    md.append("")
    md.append("Scenario:")
    md.append("- scan90 -> scan70 switch mid-run")
    md.append(f"- actions: {actions}")
    md.append(f"- tau_s: {float(args.tau_s)} (diagnostic for tracking)")
    md.append(f"- epsilon: {epsilon}")
    md.append(f"- T: {int(args.T)}, n_reps: {int(args.n_reps)}, base_seed: {int(args.base_seed)}")
    md.append(f"- after_switch_k: {int(args.after_switch_k)}")
    md.append("")
    md.append("Outputs:")
    md.append("- `sim_replicates.csv`")
    md.append("- `sim_summary.csv`")
    (out_dir / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"[OK] wrote: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
