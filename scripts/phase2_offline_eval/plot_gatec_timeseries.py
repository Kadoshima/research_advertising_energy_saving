import argparse
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# Add local module path
import sys
ROOT = Path(__file__).resolve().parents[2]
PHASE2 = ROOT / 'scripts' / 'phase2_offline_eval'
sys.path.insert(0, str(PHASE2))

from models.reward_model import RewardModel
from models.constraint_model import ConstraintModel
from models.safe_ucb import SafeUCB, SafetyFilterUCB, UCB, FixedCCS


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _find_unique_dir(root: Path, name_substr: str) -> Path:
    matches = [p for p in root.rglob('*') if p.is_dir() and name_substr in p.name]
    if not matches:
        raise FileNotFoundError(f"Could not find dir containing {name_substr!r} under {root}")
    if len(matches) == 1:
        return matches[0]
    matches.sort(key=lambda p: len(str(p)))
    return matches[0]


def _rolling_mean(x: np.ndarray, w: int) -> np.ndarray:
    if w <= 1:
        return x
    kernel = np.ones(w, dtype=float) / float(w)
    return np.convolve(x, kernel, mode='same')


def _build_filter_prior(actions, constraint_model):
    pout = {}
    n = {}
    for a in actions:
        pout[a] = float(constraint_model.predict(a))
        n[a] = int(constraint_model.n_samples(a))
    return pout, n


def _simulate_timeseries(
    method,
    actions,
    reward_model,
    constraint_model_1,
    constraint_model_2,
    epsilon,
    T,
    seed,
    switch_at,
    constraint_ci,
    constraint_delta,
    init_strategy,
    filter_margin,
    filter_prior_pout,
    filter_prior_n,
    filter_prior_weight,
    filter_reset_on_switch,
):
    rng = np.random.default_rng(seed)

    if method == 'safe_ucb':
        alg = SafeUCB(
            actions,
            reward_model,
            constraint_model_1,
            epsilon,
            seed=seed,
            constraint_ci=constraint_ci,
            constraint_delta=constraint_delta,
            init_strategy=init_strategy,
        )
    elif method == 'filter_ucb_online':
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
    elif method == 'ucb':
        alg = UCB(actions, seed=seed)
    elif method == 'fixed_ccs':
        alg = FixedCCS(actions, seed=seed)
    else:
        raise ValueError(f"unknown method: {method}")

    actions_ts = np.zeros(T, dtype=int)
    viol_ts = np.zeros(T, dtype=float)

    for t in range(T):
        if method == 'filter_ucb_online' and switch_at is not None and t == int(switch_at):
            if filter_reset_on_switch:
                alg.on_switch(discount=float(filter_prior_weight))

        a = int(alg.select_action(context=0.5))
        r = float(reward_model.sample(a, rng))

        cm_t = constraint_model_1
        if constraint_model_2 is not None and switch_at is not None and t >= int(switch_at):
            cm_t = constraint_model_2
        v = float(cm_t.sample_violation(a, rng))

        alg.update(a, r, v)

        actions_ts[t] = a
        viol_ts[t] = v

    return actions_ts, viol_ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', type=str, default='results/phase2_gatec_sweep_m_2026-01-26_v02/figs')
    ap.add_argument('--T', type=int, default=1000)
    ap.add_argument('--n-reps', type=int, default=200)
    ap.add_argument('--base-seed', type=lambda s: int(s, 0), default=int('0xD4B40201', 0))
    ap.add_argument('--switch-at-frac', type=float, default=0.5)
    ap.add_argument('--tau-s', type=float, default=2.0)
    ap.add_argument('--epsilon', type=float, default=0.10)
    ap.add_argument('--reward-mode', type=str, default='per_60s', choices=['per_adv', 'per_60s'])
    ap.add_argument('--constraint-ci', type=str, default='wilson', choices=['t_dependent', 'hoeffding', 'wilson', 'beta'])
    ap.add_argument('--constraint-delta', type=float, default=0.05)
    ap.add_argument('--init-strategy', type=str, default='safe_seed', choices=['round_robin', 'safe_seed', 'baseline_only'])
    ap.add_argument('--filter-margin', type=float, default=0.0)
    ap.add_argument('--filter-prior-weight', type=float, default=0.0)
    ap.add_argument('--filter-reset-on-switch', type=int, default=1)
    ap.add_argument('--rolling', type=int, default=50)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    _ensure_dir(out_dir)

    reward_dir = _find_unique_dir(Path('data'), 'deltae_v3rig_sweep_2026-01-21_v02')
    reward_model = RewardModel(str(reward_dir), reward_mode=args.reward_mode)

    env_scan90 = ConstraintModel(['uccs_d4b_scan90/metrics/01/per_trial.csv'], tau=float(args.tau_s))
    env_scan70 = ConstraintModel(['uccs_d4b_scan70/metrics/01_fixed/per_trial.csv'], tau=float(args.tau_s))

    actions = [100, 500]
    switch_at = int(round(int(args.T) * float(args.switch_at_frac)))

    prior_pout, prior_n = _build_filter_prior(actions, env_scan90)

    methods = [
        ('filter_ucb_online', 'Safety Filter UCB'),
        ('ucb', 'UCB'),
        ('fixed_ccs', 'Fixed-CCS'),
    ]

    n_reps = int(args.n_reps)
    T = int(args.T)

    action_share = {m[0]: np.zeros(T, dtype=float) for m in methods}
    viol_rate = {m[0]: np.zeros(T, dtype=float) for m in methods}

    for rep in range(n_reps):
        seed = int(args.base_seed + rep)
        for method, _label in methods:
            actions_ts, viol_ts = _simulate_timeseries(
                method=method,
                actions=actions,
                reward_model=reward_model,
                constraint_model_1=env_scan90,
                constraint_model_2=env_scan70,
                epsilon=float(args.epsilon),
                T=T,
                seed=seed,
                switch_at=switch_at,
                constraint_ci=str(args.constraint_ci),
                constraint_delta=float(args.constraint_delta),
                init_strategy=str(args.init_strategy),
                filter_margin=float(args.filter_margin),
                filter_prior_pout=prior_pout,
                filter_prior_n=prior_n,
                filter_prior_weight=float(args.filter_prior_weight),
                filter_reset_on_switch=bool(int(args.filter_reset_on_switch)),
            )
            action_share[method] += (actions_ts == min(actions)).astype(float)
            viol_rate[method] += viol_ts

    # Mean across reps
    for method, _label in methods:
        action_share[method] /= float(n_reps)
        viol_rate[method] /= float(n_reps)

    # Rolling mean for readability
    win = int(args.rolling)
    action_share_s = {m: _rolling_mean(v, win) for m, v in action_share.items()}
    viol_rate_s = {m: _rolling_mean(v, win) for m, v in viol_rate.items()}

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharex=True)

    colors = {
        'filter_ucb_online': '#f28e2b',
        'ucb': '#4e79a7',
        'fixed_ccs': '#59a14f',
    }

    # Panel A: share of 100ms (short interval)
    ax = axes[0]
    for method, label in methods:
        ax.plot(action_share_s[method], label=label, color=colors.get(method))
    ax.axvline(switch_at, color='k', linestyle='--', linewidth=1.0)
    ax.set_ylim(-0.02, 1.02)
    ax.set_ylabel('share of 100ms')
    ax.set_xlabel('step')
    ax.set_title('Action shift (scan90 -> scan70)')

    # Panel B: violation rate (Pout)
    ax = axes[1]
    for method, label in methods:
        ax.plot(viol_rate_s[method], label=label, color=colors.get(method))
    ax.axvline(switch_at, color='k', linestyle='--', linewidth=1.0, label='switch')
    ax.axhline(float(args.epsilon), color='#777', linestyle=':', linewidth=1.0)
    ax.set_ylim(-0.02, 0.40)
    ax.set_ylabel('Pout (rolling mean)')
    ax.set_xlabel('step')
    ax.set_title('QoS violations after switch')

    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=4, frameon=False)

    fig.tight_layout(rect=[0, 0, 1, 0.92])

    out_png = out_dir / 'gatec_timeseries_scan90_to_scan70.png'
    out_pdf = out_dir / 'gatec_timeseries_scan90_to_scan70.pdf'
    fig.savefig(out_png, dpi=200)
    fig.savefig(out_pdf)
    print(f"[OK] wrote: {out_png}")
    print(f"[OK] wrote: {out_pdf}")


if __name__ == '__main__':
    main()
