# uccs_d2_scan90 merged metrics summary

- purpose: merge summarized runs (per_trial.csv) and increase n without re-parsing raw logs.
- source: `uccs_d2_scan90/metrics/B`
- source: `uccs_d2_scan90/metrics/B_02`
- generated: 2025-12-16 14:52 (local)
- command: `python3 uccs_d2_scan90/analysis/merge_metrics_runs.py --out-dir uccs_d2_scan90/metrics/B_n6 --input-dir uccs_d2_scan90/metrics/B --input-dir uccs_d2_scan90/metrics/B_02`

## Summary (mean ± std)
| condition | n | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) |
|---|---:|---:|---:|---:|---:|---:|---:|
| S1_fixed100 | 6 | 0.0750±0.0274 | 3.762±1.461 | 0.789±0.016 | 204.1±1.4 | 1795.5±1.2 | 1.000±0.000 |
| S1_fixed500 | 6 | 0.1417±0.0492 | 5.292±0.018 | 0.816±0.018 | 184.7±1.5 | 359.0±0.0 | 0.000±0.000 |
| S1_policy | 6 | 0.1250±0.0274 | 5.239±0.049 | 0.803±0.022 | 191.5±1.9 | 855.0±0.0 | 0.331±0.004 |
| S4_fixed100 | 6 | 0.0528±0.0100 | 1.248±0.008 | 0.792±0.009 | 204.4±2.1 | 1796.0±0.0 | 0.998±0.002 |
| S4_fixed500 | 6 | 0.1463±0.0309 | 2.484±1.108 | 0.817±0.020 | 184.5±1.5 | 359.0±0.0 | 0.000±0.000 |
| S4_policy | 6 | 0.0691±0.0285 | 1.575±0.500 | 0.793±0.021 | 196.6±1.6 | 1227.0±0.0 | 0.595±0.008 |

## Notes
- This script does not recompute TL/Pout; it re-aggregates existing per-trial metrics.
- Rounding follows summarize_d2_run.py (pout/TL/PDR/share: 6 decimals, power/adv: 3 decimals).
