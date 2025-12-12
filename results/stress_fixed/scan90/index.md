# scan90 index (S1/S4 × 100/500/1000/2000, scan duty 90%)
- 最新 (v4: v3ロジック＋rx_dup_factor追加)
  - `stress_causal_real_summary_1211_stress_full_scan90_v4.csv` : per-trial (pdr_raw/unique, TL/Pout/clamp率, E/Power)
  - `stress_causal_real_summary_1211_stress_modes_scan90_v4.csv` : per-trial trimmed + rx_dup_factor
  - `stress_causal_real_summary_1211_stress_agg_scan90_v4.csv` : (session, interval) mean/median/std
  - `stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv` : agg + pout1s_excess, tl_mean_norm
  - `missed_state_scan90_v4.csv` : missed-state（中身はv3と同一ロジック。seq→idx=interval/100、truth範囲外はclampカウントして除外）
- 参考: `gap_stats_scan90.csv` : inter-packet gap p95/max per trial
- 旧版: `_scan90.csv` / `_v2.csv` / `_v3.csv` は解析ロジック前 or dup_factor無しの出力。v2はseq→idxスケーリング不足を修正済みだが、v3でinterval倍数チェック＋clamp可視化、v4でdup_factor追加。

補足定義メモ:
- adv_count と rx_unique が +1 になる場合がある（seqは0始まり・inclusiveカウント／TXSDとRXの端点差異）。PDR比較は pdr_unique を主指標とし、pdr_raw・rx_dup_factor は重複/負荷の参考指標として扱う。
- 参考: `gap_stats_scan90.csv` : inter-packet gap p95/max per trial
- 旧版: `_scan90.csv` / `_v2.csv` などは解析ロジック前の出力。v2はseq→idxスケーリング不足を修正済みだが、v3でinterval倍数チェック＋clamp可視化を追加。
