# effects_ci: D4 scan90 S4 (run01)

- source: `uccs_d4_scan90/metrics/01/per_trial.csv`
- generated: 2025-12-17 10:56 (local)
- bootstrap: percentile CI, n_boot=20000, alpha=0.05, seed=20251217

| label | delta(mean) | 95% CI | p(two-sided) |
|---|---:|---:|---:|
| Δpower_mW (policy − U-shuf) | -7.5777 | [-8.3875, -6.9261] | 0.0000 |
| Δpout (policy − U-shuf) | 0.0488 | [0.0244, 0.0732] | 0.0000 |
