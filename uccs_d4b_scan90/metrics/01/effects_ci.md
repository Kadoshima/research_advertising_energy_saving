# effects_ci: D4B scan90 S4 (run01)

- source: `uccs_d4b_scan90/metrics/01/per_trial.csv`
- generated: 2025-12-17 10:56 (local)
- bootstrap: percentile CI, n_boot=20000, alpha=0.05, seed=20251217

| label | delta(mean) | 95% CI | p(two-sided) |
|---|---:|---:|---:|
| Δpout (U+CCS − U-only) | -0.0163 | [-0.0244, 0.0000] | 0.0758 |
| Δpower_mW (U+CCS − U-only) | -0.0235 | [-0.2332, 0.1886] | 0.8283 |
| Δtl_mean_s (U+CCS − U-only) | -0.0892 | [-0.2592, 0.0143] | 0.2274 |
| Δpdr_unique (U+CCS − U-only) | 0.0142 | [-0.0013, 0.0296] | 0.0624 |
