# uccs_d3_scan70 metrics summary (v2)

- source RX: `uccs_d3_scan70\data\02_n10_run01\RX`
- source TXSD: `uccs_d3_scan70\data\02_n10_run01\TX`
- truth: `Mode_C_2_シミュレート_causal\ccs\stress_causal_S4.csv` (n_steps=1800, dt=100ms)
- selected RX trials: 004..033 (n=30)
- selected TXSD trials: grouped by adv_count=[357, 358, 1225, 1226, 1789, 1790] (n=30)
- generated: 2026-01-25 00:53 (local)
- command: `python3 uccs_d3_scan70/analysis/summarize_d3_run_v2.py --rx-dir uccs_d3_scan70\data\02_n10_run01\RX --txsd-dir uccs_d3_scan70\data\02_n10_run01\TX --out-dir uccs_d3_scan70\metrics\02_n10_run01 --n-per-cond 10`

## Summary (mean ± std)
| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) | share100_power_mix |
|---|---:|---:|---:|---:|---:|---:|---:|
| S4_fixed100 | 0.0756±0.0243 | 1.065±0.306 | 0.157±0.026 | 312.6±3.8 | 1789.5±0.5 | 1.000±0.000 |  |
| S4_fixed500 | 0.3073±0.0682 | 1.971±0.402 | 0.481±0.075 | 284.3±1.8 | 357.5±0.5 | 0.000±0.000 |  |
| S4_policy | 0.0976±0.0230 | 1.025±0.154 | 0.195±0.031 | 301.2±2.5 | 1225.6±0.5 | 0.349±0.014 | 0.597 |

## Notes
- RX window: latest 30 trials that form 3 conditions × 10 repeats (duration>=160s).
- TXSD pairing: mtimeが信頼できないため、adv_count（tick_count）でクラスタリングして各条件を割り当て。
  - filter: avg_power_mW >= 150.0（古いログ混在を除外）
- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).
- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique.
- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).
