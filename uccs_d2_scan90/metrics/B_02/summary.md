# uccs_d2_scan90 metrics summary

- source RX: `uccs_d2_scan90/data/B/02/RX`
- source TXSD: `uccs_d2_scan90/data/B/02/TX`
- truth: `Mode_C_2_シミュレート_causal/ccs/stress_causal_S1.csv`, `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv` (n_steps=1800, dt=100ms)
- selected RX trials: 084..101 (n=18)
- generated: 2025-12-16 14:38 (local)
- command: `python3 uccs_d2_scan90/analysis/summarize_d2_run.py --rx-dir uccs_d2_scan90/data/B/02/RX --txsd-dir uccs_d2_scan90/data/B/02/TX --out-dir uccs_d2_scan90/metrics/B_02`

## Summary (mean ± std, n=3 each)
| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) |
|---|---:|---:|---:|---:|---:|---:|
| S1_fixed100 | 0.0667±0.0289 | 3.314±1.536 | 0.792±0.023 | 205.4±0.4 | 1795.0±1.7 | 1.000±0.000 |
| S1_fixed500 | 0.1333±0.0577 | 5.289±0.020 | 0.815±0.020 | 186.0±0.4 | 359.0±0.0 | 0.000±0.000 |
| S1_policy | 0.1333±0.0289 | 5.230±0.055 | 0.796±0.029 | 193.2±0.2 | 855.0±0.0 | 0.329±0.002 |
| S4_fixed100 | 0.0488±0.0000 | 1.248±0.007 | 0.796±0.007 | 206.3±0.5 | 1796.0±0.0 | 1.000±0.000 |
| S4_fixed500 | 0.1382±0.0282 | 2.802±1.417 | 0.817±0.020 | 185.9±0.3 | 359.0±0.0 | 0.000±0.000 |
| S4_policy | 0.0569±0.0141 | 1.562±0.536 | 0.807±0.022 | 198.0±0.8 | 1227.0±0.0 | 0.597±0.010 |

## Notes
- RX trial selection: latest 18 trials that form 6 conditions × 3 repeats (duration>=160s).
- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).
- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique when available.
- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).
