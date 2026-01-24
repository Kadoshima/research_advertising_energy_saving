# uccs_n10_2026-01-24（UCCS D3/D4B scan70 N=10 拡張）

- 更新日: 2026-01-24
- 状態: draft

## 目的/範囲

- D3（scan70, S4のみ）と D4B（scan70, S4のみ）の各条件を **n=10** まで増やし、統計的主張の強度を上げる。
- 追加実験は既存のスケッチ/解析仕様を維持し、`program_id` をCSV列に追加した版で実施する。

## 入力データ（出所/版/行数/SHA256）

| データ | パス | 出所/版 | 行数 | SHA256 | 備考 |
| --- | --- | --- | --- | --- | --- |
| D3 scan70 RX/TXSD | `uccs_d3_scan70/data/` | 実測 | TBD | TBD | run_id/行数/SHA256は取得後に追記 |
| D4B scan70 RX/TXSD | `uccs_d4b_scan70/data/` | 実測 | TBD | TBD | run_id/行数/SHA256は取得後に追記 |

## 出力物（生成日/生成スクリプト）

- D3集計: `uccs_d3_scan70/metrics/` 配下に `summary.md`, `summary_by_condition.csv`, `per_trial.csv` を生成（生成日/コマンドは各summaryに記録）。
- D4B集計: `uccs_d4b_scan70/metrics/` 配下に同形式で生成（生成日/コマンドは各summaryに記録）。

## manifest.csv

- 追加実験ごとに manifest.csv を作成し、trial_id/session/interval/mode/run_id/start_ts_jst/distance/scan_setting/program_id を記録する。
- 配置は `uccs_d3_scan70/data/` と `uccs_d4b_scan70/data/` の各runディレクトリ直下とする。

## 再現手順（コマンド）

```
python3 uccs_d3_scan70/analysis/summarize_d3_run_v2.py --rx-dir <RX_DIR> --txsd-dir <TX_DIR> --out-dir <OUT_DIR> --n-per-cond 10
python3 uccs_d4b_scan90/analysis/summarize_d4b_run_v2.py --rx-dir <RX_DIR> --txsd-dir <TX_DIR> --out-dir <OUT_DIR> --n-per-cond 10
```

## 実行条件（固定）

- 対象セッション: S4のみ
- RX設定: scan70（interval=100ms, window=70ms）
- 条件数: D3=3条件（Fixed100/Fixed500/Policy）, D4B=4条件（Fixed100/Fixed500/Policy/U-only）
- SYNC/TICK: SYNC_START=TX GPIO26 → RX/TXSD GPIO26, SYNC_END=TX GPIO25 → RX/TXSD GPIO25, TICK_OUT=TX GPIO27 → TXSD GPIO33
- program_id（CSV列）: D3 RX=`RX_UCCS_D3_SCAN70_v1`, D3 TXSD=`TXSD_UCCS_D3_SCAN70_v1`, D4B RX=`RX_UCCS_D4B_SCAN70_v1`, D4B TXSD=`TXSD_UCCS_D4B_SCAN70_v1`

## 関連リンク

- D3概要: `uccs_d3_scan70/README.md`
- D4B概要: `uccs_d4b_scan70/README.md`
- 指標定義: `docs/metrics_definition.md`
- 統合TODO: `docs/TODO.md`

## 更新履歴

- 2026-01-24: N=10拡張タスクの初版を作成
