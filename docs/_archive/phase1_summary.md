# フェーズ1 基準セットサマリ（row_1120 ON × row_1123_off OFF, manifest+MAD適用）

> 2025-12-03 注: 本ページの値は v2 rig（計測込み）＋UART化けの旧構成に基づく歴史的参照値です。正式な比較・設計には v3 rig 再計測の Mode A/B/C…（P_off_B≈23 mW, P_off_A≈11.8 mW, Mode C2/C2' の新ΔE/adv）を使用してください。

- OFF baseline: P_off_mean ≈ 22.106 mW（row_1123_off, keep 7/7, MAD=3）※旧構成
- ΔE/adv (mJ/adv, mean ± std) ※旧構成:
  - 100ms: 2.2568 ± 0.1622
  - 500ms: 9.7601 ± 0.3392
  - 1000ms: 19.6611 ± 0.1335（1 trial high_current_outlier 除外）
  - 2000ms: 39.4818 ± 0.0631
- PDR (TXSD+RX join, `--dedup-seq`, `--clip-pdr`):
  - PDR_ms (正式, clip済): 100=0.814, 500=0.845, 1000=0.872, 2000=0.876
  - 参考: PDR_raw_mean 100=1.149, 500=0.921, 1000=0.921, 2000=0.915 / PDR_unique_mean 100=1.120, 500=0.897, 1000=0.898, 2000=0.888
- ソース:
  - ΔE/adv: `docs/フェーズ1/results/delta_energy_row1120_row1123_off.md`
  - PDR: `docs/フェーズ1/results/pdr_row1120_txsd_rx.md`

備考:
- ON: ADV 300回送出設計。manifest で high_current_outlier (median+3MAD) を除外。
- OFF: 60s固定窓、P_off_trial に median+3MAD 適用。高基線は manifest で include=false。
