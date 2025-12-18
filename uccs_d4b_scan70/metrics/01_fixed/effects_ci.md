# effects_ci: D4B scan70 S4 (run01_fixed)

- source: `uccs_d4b_scan70/metrics/01_fixed/per_trial.csv`
- generated: 2025-12-18 23:24 (local)
- bootstrap: percentile CI, n_boot=20000, alpha=0.05, seed=20251218

| label | delta(mean) | 95% CI | p(two-sided) |
|---|---:|---:|---:|
| Δpout (U+CCS − U-only) | 0.0081 | [-0.0081, 0.0244] | 0.6325 |
| Δpower_mW (U+CCS − U-only) | -0.8414 | [-2.2284, 0.5457] | 0.2601 |
| Δadv_count (U+CCS − U-only) | 0.0000 | [0.0000, 0.0000] | 1.0000 |
