# phase1_e2_compare_2026-01-22

目的/範囲
- E2環境における CCS / FIXED100 / FIXED2000 の比較表を整理する。
- Phase1の論文用結果整理の下敷きとする。

入力データ（出所/版/行数/SHA256）
- 出所: `data/実験データ/研究室/phase1_e2_ccs_2026-01-22_v03/`
- 出所: `data/実験データ/研究室/phase1_e2_baseline_2026-01-22_v01/`
- 版: v03 (CCS), v01 (Baseline)

出力物（生成日/生成スクリプト）
- 生成日: 2026-01-22
- 生成物: 本README

比較表（E2）

| 条件 | N | Avg Current (mA) | TL p50 (ms) | TL p95 (ms) | Pout(2s) | PDR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FIXED100 | 3 | 96.93 +/- 0.72 | 55.3 | 251.7 | 0.00% | 0.802 |
| CCS | 5 | 90.12 +/- 0.57 | 505.2 | 4116.6 | 10.77% | 0.801 |
| CCS+TailGuard | 6 | 92.01 +/- 3.03 | 88.3 | 944.5 | 1.28% | 0.821 |
| FIXED2000 | 3 | 87.78 +/- 2.28 | 836.3 | 3689.3 | 11.11% | 0.822 |

参照元
- CCS: `results/phase1_e2_ccs_2026-01-22_v03.md`
- CCS+TailGuard: `results/phase1_e2_ccs_tail_guard_2026-01-23_v05_v06.md`
- Baseline: `results/phase1_e2_baseline_2026-01-22_v01.md`

考察メモ（論文化の視点）
- CCSはFIXED100より省電力だが、Pout(2s)とTL p95は悪化している
- CCSはFIXED2000よりTL p50は改善する一方、Pout(2s)は同程度で尾部が重い
- PDRは条件間で近く、差の主因は「受信率」ではなく「遅延分布（tail）」にある可能性
- 位置づけは「Pareto的な中間解」＋「tail-aware制約の必要性（Phase2の必然）」が妥当

追加で見るべき観点（短期）
- TL/Poutの算出条件が `docs/metrics_definition.md` と整合しているか確認
- Pout(2s)に寄与した遷移イベントの上位抽出（tail原因の可視化）
- Nが小さいため、差分はCI/ブートストラップで不確実性を明示

注記
- 解析用に `results/phase1_e2_ccs_2026-01-22_v03_input/` と `results/phase1_e2_baseline_2026-01-22_v01_input/` を使用。
- ステージングで `prog_id` 列除去と trial_id 整合のリネームを実施（生データは未改変）。

状態
- draft

関連リンク
- `docs/フェーズ1/要件定義.md`
- `docs/フェーズ1/phase1_e2_ccs_2026-01-22/README.md`
- `docs/フェーズ1/phase1_e2_baseline_2026-01-22/README.md`

更新履歴（YYYY-MM-DD）
- 2026-01-22: 初版（E2比較表）
