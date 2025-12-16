# uccs_d4_scan90 metrics summary (v2)

- source RX: `uccs_d4_scan90/data/01/RX`
- source TXSD: `uccs_d4_scan90/data/01/TX`
- truth: `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv` (n_steps=1800, dt=100ms)
- selected RX trials: 001..012 (n=12)
- selected TXSD trials (by mtime): trial_003_c1_s4_fixed100.csv .. trial_003_c5_unk.csv (n=12)
- generated: 2025-12-16 18:40 (local)
- command: `python3 uccs_d4_scan90/analysis/summarize_d4_run_v2.py --rx-dir uccs_d4_scan90/data/01/RX --txsd-dir uccs_d4_scan90/data/01/TX --out-dir uccs_d4_scan90/metrics/01`

## Summary (mean ± std)
| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) |
|---|---:|---:|---:|---:|---:|---:|
| S4_ablation_u_shuf | 0.0488±0.0000 | 1.234±0.005 | 0.788±0.007 | 208.1±0.3 | 1715.0±0.0 | 0.943±0.000 |
| S4_fixed100 | 0.0488±0.0000 | 1.240±0.008 | 0.787±0.007 | 208.2±1.3 | 1796.0±0.0 | 1.000±0.000 |
| S4_fixed500 | 0.1301±0.0141 | 1.587±0.057 | 0.813±0.005 | 187.9±0.8 | 359.0±0.0 | 0.000±0.000 |
| S4_policy | 0.0976±0.0244 | 1.278±0.014 | 0.789±0.004 | 200.5±0.8 | 1227.0±0.0 | 0.593±0.009 |

## Notes
- RX window: latest 12 trials that form 4 conditions × 3 repeats (duration>=160s).
- TXSD pairing: last 12 TXSD trials by file modification time; zipped in order with RX window.
- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).
- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique.
- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).
