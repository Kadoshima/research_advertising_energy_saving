# phase1_e2_baseline_2026-01-22

目的/範囲
- E2(高Wi-Fi干渉)環境で固定間隔Baseline(100ms×3, 2000ms×3)の実測KPIを整理する。
- CCS結果との比較に用いる。

入力データ（出所/版/行数/SHA256）
- 出所: `data/実験データ/研究室/phase1_e2_baseline_2026-01-22_v01/`
- 版: v01（2026-01-22）
- 行数: RX合計 15193 行 / TXSD合計 359694 行
- SHA256: `data/実験データ/研究室/phase1_e2_baseline_2026-01-22_v01/README.md` に記載

出力物（生成日/生成スクリプト）
- `results/phase1_e2_baseline_2026-01-22_v01.md`
- `results/phase1_e2_baseline_2026-01-22_v01.json`
- 生成日: 2026-01-22
- 生成スクリプト: `python scripts/analyze_ccs_experiment.py ...`

結果サマリ（E2, N=3+3）
- FIXED100: Avg 96.93 +/- 0.72 mA, TL p50 55.3 ms / p95 251.7 ms, Pout(2s) 0.00%, PDR 0.802
- FIXED2000: Avg 87.78 +/- 2.28 mA, TL p50 836.3 ms / p95 3689.3 ms, Pout(2s) 11.11%, PDR 0.822
- 参照元: `results/phase1_e2_baseline_2026-01-22_v01.md`
- 注記: 解析用入力は `results/phase1_e2_baseline_2026-01-22_v01_input/` にステージングし、`prog_id` 列の除去と trial_id 整合のためのリネームを実施（生データは未改変）

再現手順（コマンド）
1) `python scripts/analyze_ccs_experiment.py --data-dir "results/phase1_e2_baseline_2026-01-22_v01_input" --out "results/phase1_e2_baseline_2026-01-22_v01.md" --json-out "results/phase1_e2_baseline_2026-01-22_v01.json"`

状態
- draft

関連リンク
- `docs/フェーズ1/要件定義.md`
- `docs/フェーズ1/phase1_e2_compare_2026-01-22/README.md`
- `data/実験データ/研究室/phase1_e2_baseline_2026-01-22_v01/README.md`
- `results/phase1_e2_baseline_2026-01-22_v01.md`

更新履歴（YYYY-MM-DD）
- 2026-01-22: 初版（E2/Baseline v01）
