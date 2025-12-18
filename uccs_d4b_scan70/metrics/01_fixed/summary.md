# uccs_d4b_scan90 metrics summary (v2)

- source RX: `uccs_d4b_scan70/data/01/RX`
- source TXSD: `uccs_d4b_scan70/data/01/TX`
- truth: `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv` (n_steps=1800, dt=100ms)
- selected RX trials: 014..025 (n=12)
- selected TXSD trials: grouped by adv_count=[360, 1323, 1800] (3 trials each)
- generated: 2025-12-18 20:46 (local)
- command: `python3 uccs_d4b_scan90/analysis/summarize_d4b_run_v2.py --rx-dir uccs_d4b_scan70/data/01/RX --txsd-dir uccs_d4b_scan70/data/01/TX --out-dir uccs_d4b_scan70/metrics/01_fixed`

## Summary (mean ± std)
| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) | share100_power_mix |
|---|---:|---:|---:|---:|---:|---:|---:|
| S4_ablation_ccs_off | 0.0081±0.0141 | 0.237±0.134 | 0.355±0.002 | 202.2±1.2 | 1323.0±0.0 | 0.533±0.002 | 0.780 |
| S4_fixed100 | 0.0244±0.0244 | 0.431±0.316 | 0.333±0.002 | 206.4±0.5 | 1800.0±0.0 | 1.000±0.000 |  |
| S4_fixed500 | 0.2276±0.0373 | 1.443±0.513 | 0.613±0.013 | 187.6±0.4 | 360.0±0.0 | 0.000±0.000 |  |
| S4_policy | 0.0163±0.0141 | 0.301±0.143 | 0.367±0.007 | 201.4±1.0 | 1323.0±0.0 | 0.514±0.021 | 0.735 |

## Notes
- RX window: latest 12 trials that form 4 conditions × 3 repeats (duration>=160s).
- TXSD pairing: cond_idがズレる/mtimeが壊れる可能性があるため、adv_count（tick_count）でクラスタリングして割り当て。
  - filter: avg_power_mW >= 150.0 かつ E_total_mJ>0（古いログ混在/逆符号を除外）
- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).
- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique.
- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).
