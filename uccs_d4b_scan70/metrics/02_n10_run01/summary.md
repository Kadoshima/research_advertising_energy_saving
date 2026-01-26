# uccs_d4b_scan90 metrics summary (v2)

- source RX: `uccs_d4b_scan70\data\02_n10_run01\RX`
- source TXSD: `uccs_d4b_scan70\data\02_n10_run01\TX`
- truth: `Mode_C_2_シミュレート_causal\ccs\stress_causal_S4.csv` (n_steps=1800, dt=100ms)
- selected RX trials: 188..227 (n=40)
- selected TXSD trials: grouped by adv_count=[348, 349, 350, 351, 1266, 1268, 1269, 1271, 1272, 1274, 1275, 1277, 1278, 1280, 1281, 1283, 1284, 1286, 1748, 1749, 1751, 1752, 1754, 1755, 1757, 1758, 1760, 1761] (10 trials each)
- generated: 2026-01-25 13:39 (local)
- command: `python3 uccs_d4b_scan90/analysis/summarize_d4b_run_v2.py --rx-dir uccs_d4b_scan70\data\02_n10_run01\RX --txsd-dir uccs_d4b_scan70\data\02_n10_run01\TX --out-dir uccs_d4b_scan70\metrics\02_n10_run01 --n-per-cond 10`

## Summary (mean ± std)
| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) | share100_power_mix |
|---|---:|---:|---:|---:|---:|---:|---:|
| S4_ablation_ccs_off | 0.1415±0.0321 | 3.897±0.515 | 0.206±0.025 | 307.4±4.0 | 1279.0±4.6 | 0.401±0.008 | 0.722 |
| S4_fixed100 | 0.1439±0.0334 | 3.952±0.446 | 0.165±0.017 | 314.5±3.7 | 1754.5±4.5 | 1.000±0.000 |  |
| S4_fixed500 | 0.3512±0.0611 | 4.872±0.305 | 0.520±0.053 | 289.0±6.2 | 349.4±1.0 | 0.000±0.000 |  |
| S4_policy | 0.1415±0.0154 | 3.827±0.304 | 0.211±0.024 | 306.9±4.0 | 1273.0±4.6 | 0.401±0.010 | 0.703 |

## Notes
- RX window: latest 40 trials that form 4 conditions × 10 repeats (duration>=160s).
- TXSD pairing: cond_idがズレる/mtimeが壊れる可能性があるため、adv_count（tick_count）でクラスタリングして割り当て。
  - filter: avg_power_mW >= 150.0 かつ E_total_mJ>0（古いログ混在/逆符号を除外）
- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).
- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique.
- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).
