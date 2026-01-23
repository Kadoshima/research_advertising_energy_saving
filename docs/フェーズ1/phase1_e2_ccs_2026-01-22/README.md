# Phase1 E2/CCS 実験レポート（2026-01-22 v03）

## 目的/範囲
- E2（高Wi-Fi干渉）環境でCCS制御の実測KPIを整理し、Phase 1の要件定義に転記する
- Baseline（固定100ms/2000ms）の比較は `docs/フェーズ1/phase1_e2_compare_2026-01-22/README.md` に整理済み

## 入力データ（出所/版/行数/SHA256）
- 出所: `data/実験データ/研究室/phase1_e2_ccs_2026-01-22_v03/`
- 版: v03（2026-01-22）
- 行数: RX合計 7,369 行 / TXSD合計 300,614 行（`RX/rx_*.csv`, `TXSD/pwr_*.csv` の行数合計）
- SHA256: `data/実験データ/研究室/phase1_e2_ccs_2026-01-22_v03/README.md` に記載

## 出力物（生成日/生成スクリプト）
- `results/phase1_e2_ccs_2026-01-22_v03.md`（2026-01-22, `python scripts/analyze_ccs_experiment.py ...`）
- `results/phase1_e2_ccs_2026-01-22_v03.json`（同上）

## 結果サマリ（E2/CCS, N=5）
- 平均電流: 90.12 +/- 0.57 mA
- TL p50: 505.2 ms / TL p95: 4116.6 ms
- Pout(1s/2s/3s): 43.08% / 10.77% / 9.23%
- PDR: 0.801
- 参照元: `results/phase1_e2_ccs_2026-01-22_v03.md`

## 再現手順（コマンド）
1. `python scripts/analyze_ccs_experiment.py --data-dir "results/phase1_e2_ccs_2026-01-22_v03_input" --session-manifest "data/esp32_sessions/session_manifest.json" --out "results/phase1_e2_ccs_2026-01-22_v03.md" --json-out "results/phase1_e2_ccs_2026-01-22_v03.json"`
2. 依存データ: `data/実験データ/研究室/phase1_e2_ccs_2026-01-22_v03/`（RX/TXSD）

## 状態（draft/frozen/obsolete）
- draft

## 関連リンク
- `docs/フェーズ1/要件定義.md`
- `data/実験データ/研究室/phase1_e2_ccs_2026-01-22_v03/README.md`
- `results/phase1_e2_ccs_2026-01-22_v03.md`

## 更新履歴（YYYY-MM-DD）
- 2026-01-22: 初版（E2/CCS v03）
