# uccs_d4b_scan90 metrics summary (v2)

- source RX: `uccs_d4b_scan90/data/01/RX`
- source TXSD: `uccs_d4b_scan90/data/01/TX`
- truth: `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv` (n_steps=1800, dt=100ms)
- selected RX trials: 002..013 (n=12)
- selected TXSD trials: grouped by adv_count=[359, 1215, 1227, 1796] (3 trials each)
- generated: 2025-12-17 00:10 (local)
- command: `python3 uccs_d4b_scan90/analysis/summarize_d4b_run_v2.py --rx-dir uccs_d4b_scan90/data/01/RX --txsd-dir uccs_d4b_scan90/data/01/TX --out-dir uccs_d4b_scan90/metrics/01`

## Summary (mean ± std)
| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) | share100_power_mix |
|---|---:|---:|---:|---:|---:|---:|---:|
| S4_ablation_ccs_off | 0.0650±0.0141 | 1.407±0.148 | 0.434±0.016 | 200.6±0.2 | 1227.0±0.0 | 0.429±0.009 | 0.621 |
| S4_fixed100 | 0.0813±0.0141 | 1.487±0.115 | 0.377±0.043 | 208.3±0.5 | 1796.0±0.0 | 1.000±0.000 |  |
| S4_fixed500 | 0.1301±0.0282 | 1.210±0.263 | 0.823±0.015 | 188.1±0.3 | 359.0±0.0 | 0.000±0.000 |  |
| S4_policy | 0.0488±0.0000 | 1.317±0.025 | 0.448±0.005 | 200.6±0.1 | 1215.0±0.0 | 0.434±0.005 | 0.620 |

## Notes
- RX window: latest 12 trials that form 4 conditions × 3 repeats (duration>=160s).
- TXSD pairing: cond_idがズレる/mtimeが壊れる可能性があるため、adv_count（tick_count）でクラスタリングして割り当て。
  - filter: avg_power_mW >= 150.0 かつ E_total_mJ>0（古いログ混在/逆符号を除外）
- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).
- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique.
- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).
