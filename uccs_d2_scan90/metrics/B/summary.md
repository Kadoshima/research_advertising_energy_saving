# uccs_d2_scan90 metrics summary

- source RX: `uccs_d2_scan90/data/B/RX`
- source TXSD: `uccs_d2_scan90/data/B/TX`
- truth: `Mode_C_2_シミュレート_causal/ccs/stress_causal_S1.csv`, `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv` (n_steps=1800, dt=100ms)
- selected RX trials: 002..019 (n=18)
- generated: 2025-12-15 18:43 (local)
- command: `python3 uccs_d2_scan90/analysis/summarize_d2_run.py --rx-dir uccs_d2_scan90/data/B/RX --txsd-dir uccs_d2_scan90/data/B/TX --out-dir uccs_d2_scan90/metrics/B`

## Summary (mean ± std, n=3 each)
| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) |
|---|---:|---:|---:|---:|---:|---:|
| S1_fixed100 | 0.0833±0.0289 | 4.210±1.540 | 0.785±0.009 | 202.9±0.5 | 1796.0±0.0 | 1.000±0.000 |
| S1_fixed500 | 0.1500±0.0500 | 5.296±0.019 | 0.816±0.021 | 183.3±0.2 | 359.0±0.0 | 0.000±0.000 |
| S1_policy | 0.1167±0.0289 | 5.247±0.053 | 0.810±0.016 | 189.8±0.4 | 855.0±0.0 | 0.332±0.006 |
| S4_fixed100 | 0.0569±0.0141 | 1.247±0.010 | 0.788±0.011 | 202.5±0.4 | 1796.0±0.0 | 0.996±0.000 |
| S4_fixed500 | 0.1545±0.0373 | 2.166±0.870 | 0.817±0.024 | 183.2±0.3 | 359.0±0.0 | 0.000±0.000 |
| S4_policy | 0.0813±0.0373 | 1.588±0.582 | 0.779±0.002 | 195.2±0.4 | 1227.0±0.0 | 0.592±0.006 |

## Notes
- RX trial selection: latest 18 trials that form 6 conditions × 3 repeats (duration>=160s).
- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).
- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique when available.
- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).
