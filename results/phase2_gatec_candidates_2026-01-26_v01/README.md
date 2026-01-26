# Gate C candidate check (auto-generated)

- Date: 2026-01-26
- Script: `scripts/phase2_offline_eval/run_gatec_candidates.py`
- gateb_run_dir: `results/phase2_offline_studies_2026-01-26_v04`
- candidates(top_n=3):
  - filter_ucb_online_w0_m0.03_r1 (w=0, m=0.03, reset=1)
  - filter_ucb_online_w0_m0.02_r1 (w=0, m=0.02, reset=1)
  - filter_ucb_online_w0_m0_r1 (w=0, m=0, reset=1)

Scenario:
- scan90 -> scan70 switch mid-run
- actions: [100, 500]
- tau_s: 2.0 (diagnostic for tracking)
- epsilon: 0.1
- T: 1000, n_reps: 100, base_seed: 3568566785
- after_switch_k: 50

Outputs:
- `sim_replicates.csv`
- `sim_summary.csv`
