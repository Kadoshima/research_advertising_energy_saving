# Gate B Pareto (auto-generated)

- run_dir: `results/phase2_offline_studies_2026-01-26_v04`
- epsilon: 0.1
- caps:
  - max_viol_after_worst_mean: 25.0
- scenario_start: `E2_actions_500_1000_2000_warm_shift_from_E1` (reset=0; treated as shift-at-start)
- scenario_mid: `E1_to_E2_actions_500_1000_2000_switch_mid` (reset may be used)

Pareto front definition:
- x: cost_worst_mean (mJ/60s, lower is better)
- y: violations_first_after_switch_k_worst_p95 (k=50, lower is better)

Top candidates on Pareto front:
| method | w | m | reset | cost_worst_mean | viol_first_worst_p95 | viol_after_worst_mean | vr_worst_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| filter_ucb_online_w0_m0.03_r1 | 0.0 | 0.03 | 1 | 1487.700 | 6.00 | 7.62 | 0.03290 |
| filter_ucb_online_w0_m0.02_r1 | 0.0 | 0.02 | 1 | 1469.804 | 6.05 | 12.70 | 0.03992 |
| filter_ucb_online_w0_m0.01_r1 | 0.0 | 0.01 | 1 | 1426.255 | 7.00 | 24.46 | 0.04661 |

Full tables: `results/phase2_offline_studies_2026-01-26_v04/gateb_candidates_cap25.csv`, `results/phase2_offline_studies_2026-01-26_v04/gateb_pareto_front_cap25.csv`
