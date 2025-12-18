# uccs_d4b_scan90 metrics summary (v2)

- source RX: `uccs_d4b_scan70/data/01/RX`
- source TXSD: `uccs_d4b_scan70/data/01/TX`
- truth: `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv` (n_steps=1800, dt=100ms)
- selected RX trials: 020..031 (n=12)
- selected TXSD trials: grouped by adv_count=[359, 1215, 1787, 1796] (3 trials each)
- generated: 2025-12-17 17:20 (local)
- command: `python3 uccs_d4b_scan90/analysis/summarize_d4b_run_v2.py --rx-dir uccs_d4b_scan70/data/01/RX --txsd-dir uccs_d4b_scan70/data/01/TX --out-dir uccs_d4b_scan70/metrics/01`

## Summary (mean ± std)
| condition | pout_1s | tl_mean_s | pdr_unique | avg_power_mW | adv_count | share100_time_est (RX tags) | share100_power_mix |
|---|---:|---:|---:|---:|---:|---:|---:|
| S4_ablation_ccs_off | 0.0081±0.0141 | 0.235±0.157 | 0.266±0.004 | 205.4±0.2 | 1787.0±0.0 | 0.500±0.023 | 0.910 |
| S4_fixed100 | 0.0244±0.0244 | 0.446±0.307 | 0.331±0.002 | 207.1±0.2 | 1796.0±0.0 | 1.000±0.000 |  |
| S4_fixed500 | 0.0163±0.0141 | 0.357±0.207 | 1.000±0.000 | 187.5±0.3 | 359.0±0.0 | 0.000±0.000 |  |
| S4_policy | 0.0000±0.0000 | 0.120±0.004 | 0.396±0.003 | 199.0±0.2 | 1215.0±0.0 | 0.511±0.015 | 0.586 |

## Notes
- RX window: latest 12 trials that form 4 conditions × 3 repeats (duration>=160s).
- TXSD pairing: cond_idがズレる/mtimeが壊れる可能性があるため、adv_count（tick_count）でクラスタリングして割り当て。
  - filter: avg_power_mW >= 150.0 かつ E_total_mJ>0（古いログ混在/逆符号を除外）
- TL/Pout alignment: per-trial constant offset estimated from (step_idx*100ms - first_rx_ms(step_idx)).
- TXSD adv_count is tick_count (1 tick per payload update); used as denominator for pdr_unique.
- share100_time_est: estimated from RX tags (unique step_idx by interval); sanity only (RX has drops).
