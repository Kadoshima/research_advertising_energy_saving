# uccs_d3_scan70 metrics summary (v2)

- source RX: `uccs_d3_scan70/data/01/RX`
- source TXSD: `uccs_d3_scan70/data/01/TX`
- truth: `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv` (n_steps=1800, dt=100ms)
- selected RX trials: 010..018 (n=9)
- selected TXSD trials: grouped by adv_count=[359, 1227, 1796] (n=9)
- generated: 2025-12-16 20:35 (local)
- command: `python3 uccs_d3_scan70/analysis/summarize_d3_run_v2.py --rx-dir uccs_d3_scan70/data/01/RX --txsd-dir uccs_d3_scan70/data/01/TX --out-dir uccs_d3_scan70/metrics/01`

## Summary (mean ± std)
| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) |
|---|---:|---:|---:|---:|---:|---:|
| S4_fixed100 | 0.0650±0.0282 | 1.342±0.025 | 0.304±0.017 | 209.9±0.5 | 1796.0±0.0 | 1.000±0.000 |
| S4_fixed500 | 0.2846±0.0614 | 2.928±1.066 | 0.652±0.007 | 189.5±0.5 | 359.0±0.0 | 0.001±0.000 |
| S4_policy | 0.0894±0.0373 | 1.400±0.071 | 0.343±0.017 | 202.1±0.1 | 1227.0±0.0 | 0.420±0.018 |

## Notes
- RX window: latest 9 trials that form 3 conditions × 3 repeats (duration>=160s).
- TXSD pairing: mtimeが信頼できないため、adv_count（tick_count）でクラスタリングして各条件3本を割り当て。
  - filter: avg_power_mW >= 150.0（古いログ混在を除外）
- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).
- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique.
- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).
