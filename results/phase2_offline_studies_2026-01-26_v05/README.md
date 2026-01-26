# Phase 2 Offline Studies (auto-generated)

- Date: 2026-01-26
- Script: `scripts/phase2_offline_eval/run_offline_studies.py`
- reward_mode: per_60s (mJ_per_60s)
- Safe-UCB: constraint_ci=wilson, delta=0.05, init_strategy=safe_seed
- after_switch_k: 50
- GateB sweep: prior_weights=0, margins=0,0.005,0.01,0.015,0.02,0.03, reset_on_switch=1

## Outputs

- `tradeoff_table.csv`: Reward/constraint table per env/action
- `epsilon_tau_sensitivity.csv`: Safe/unsafe table for (epsilon,tau)
- `validity_reward_split.csv`: Reward model split check (train/test)
- `validity_constraint_e2_split.csv`: Constraint split check (E2 fixed sweep)
- `sim_replicates.csv`: Per-replicate simulation metrics
- `sim_summary.csv`: Aggregated simulation metrics (includes diagnostics + action-pull means)
