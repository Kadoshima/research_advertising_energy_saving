# scan50 index (S1/S4 × 100/500/1000/2000, legacy RX scan duty)
- 最新 (v5: TL/Pout の **時間同期** を追加)
  - `stress_causal_real_summary_1211_stress_full_scan50_v5.csv` : per-trial summary（`tl_time_offset_ms` あり）
  - `stress_causal_real_summary_1211_stress_modes_scan50_v5.csv` : per-trial trimmed view
  - `stress_causal_real_summary_1211_stress_agg_scan50_v5.csv` : per (session, interval) mean/median/std
  - `stress_causal_real_summary_1211_stress_agg_enriched_scan50_v5.csv` : agg + pout1s_excess, tl_mean_norm

- 旧版（時間同期なし）
  - `stress_causal_real_summary_1211_stress_full_scan50.csv`
  - `stress_causal_real_summary_1211_stress_modes_scan50.csv`
  - `stress_causal_real_summary_1211_stress_agg_scan50.csv`
  - `stress_causal_real_summary_1211_stress_agg_enriched_scan50.csv`
- `gap_stats_scan50.csv` : inter-packet gap p95/max per trial
