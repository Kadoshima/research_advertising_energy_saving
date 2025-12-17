# effects_ci: D3 scan70 S4 (run01)

- source: `uccs_d3_scan70/metrics/01/per_trial.csv`
- generated: 2025-12-17 10:56 (local)
- bootstrap: percentile CI, n_boot=20000, alpha=0.05, seed=20251217

| label | delta(mean) | 95% CI | p(two-sided) |
|---|---:|---:|---:|
| Δpout (policy − fixed500) | -0.1951 | [-0.2602, -0.1301] | 0.0000 |
| Δpower_mW (policy − fixed100) | -7.7612 | [-8.2441, -7.2247] | 0.0000 |
