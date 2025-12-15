# uccs_d2_scan90 metrics summary

- source RX: `uccs_d2_scan90/data/RX`
- source TXSD: `uccs_d2_scan90/data/TX`
- truth: `Mode_C_2_シミュレート_causal/ccs/stress_causal_S1.csv`, `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv` (n_steps=1800, dt=100ms)
- selected RX trials: 009..026 (n=18)
- generated: 2025-12-15 14:31 (local)
- command: `python3 uccs_d2_scan90/analysis/summarize_d2_run.py --rx-dir uccs_d2_scan90/data/RX --txsd-dir uccs_d2_scan90/data/TX --out-dir uccs_d2_scan90/metrics/01`

## Summary (mean ± std, n=3 each)
| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) |
|---|---:|---:|---:|---:|---:|---:|
| S1_fixed100 | 0.0833±0.0289 | 4.200±1.552 | 0.805±0.010 | 203.8±0.1 | 1796.0±0.0 | 1.000±0.000 |
| S1_fixed500 | 0.1000±0.0000 | 5.276±0.054 | 0.831±0.014 | 183.8±0.2 | 359.0±0.0 | 0.000±0.000 |
| S1_policy | 0.0667±0.0289 | 3.315±1.538 | 0.803±0.003 | 203.7±0.3 | 1787.0±0.0 | 0.990±0.000 |
| S4_fixed100 | 0.0488±0.0000 | 1.238±0.006 | 0.805±0.012 | 203.7±0.3 | 1796.0±0.0 | 1.000±0.000 |
| S4_fixed500 | 0.1301±0.0563 | 1.946±0.417 | 0.838±0.006 | 184.3±0.2 | 359.0±0.0 | 0.000±0.000 |
| S4_policy | 0.0569±0.0141 | 1.316±0.145 | 0.810±0.008 | 204.3±0.5 | 1787.0±0.0 | 0.991±0.002 |

## Notes
- RX trial selection: latest 18 trials that form 6 conditions × 3 repeats (duration>=160s).
- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).
- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique when available.
- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).
