# effects_ci: D3 scan70 n10 (02_n10_run01)

- source: `uccs_d3_scan70\metrics\02_n10_run01\per_trial.csv`
- generated: 2026-01-25 14:23 (local)
- bootstrap: percentile CI, n_boot=20000, alpha=0.05, seed=20260125

| label | delta(mean) | 95% CI | p(two-sided) | hedges_g | g 95% CI |
|---|---:|---:|---:|---:|---:|
| Pout(1s): Policy - Fixed500 | -0.2098 | [-0.2488, -0.1634] | 0.0000 | -3.9466 | [-9.3354, -2.3973] |
| Avg power: Policy - Fixed100 | -11.3973 | [-14.2080, -8.7932] | 0.0000 | -3.3615 | [-6.2009, -2.5750] |
