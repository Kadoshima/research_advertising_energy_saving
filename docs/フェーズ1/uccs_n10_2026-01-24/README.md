# uccs_n10_2026-01-24（UCCS D3/D4B scan70 N=10 拡張）

- 更新日: 2026-01-24
- 状態: draft

## 目的/範囲

- D3（scan70, S4のみ）と D4B（scan70, S4のみ）の各条件を **n=10** まで増やし、統計的主張の強度を上げる。
- 追加実験は既存のスケッチ/解析仕様を維持し、`program_id` をCSV列に追加した版で実施する。

## 入力データ（出所/版/行数/SHA256）

| データ | パス | 出所/版 | 行数 | SHA256 | 備考 |
| --- | --- | --- | --- | --- | --- |
| D3 scan70 RX/TXSD | `uccs_d3_scan70/data/02_n10_run01/` | 実測 | RX=33/7636行, TXSD=33/554213行, manifest=66行 | 51b013a097a3f9eca7b568f3fe9ddc16a448da0d2f92bace02877a0f6f40f99b | manifest.csv を作成済み |
| D4B scan70 RX/TXSD | `uccs_d4b_scan70/data/` | 実測 | TBD | TBD | run_id/行数/SHA256は取得後に追記 |

## 出力物（生成日/生成スクリプト）

- D3集計: `uccs_d3_scan70/metrics/` 配下に `summary.md`, `summary_by_condition.csv`, `per_trial.csv` を生成（生成日/コマンドは各summaryに記録）。
- D4B集計: `uccs_d4b_scan70/metrics/` 配下に同形式で生成（生成日/コマンドは各summaryに記録）。

### D3 scan70 n10 集計結果（02_n10_run01）

- 出力: `uccs_d3_scan70/metrics/02_n10_run01/summary.md`
- Fixed100: pout_1s=0.0756±0.0243, tl_mean=1.065±0.306, avg_power=312.6±3.8 mW
- Fixed500: pout_1s=0.3073±0.0682, tl_mean=1.971±0.402, avg_power=284.3±1.8 mW
- Policy: pout_1s=0.0976±0.0230, tl_mean=1.025±0.154, avg_power=301.2±2.5 mW
- Policy vs Fixed500: pout_1s -0.2098（約-68%）, tl_mean -0.946 s, avg_power +16.9 mW（約+5.9%）
- Policy vs Fixed100: pout_1s +0.0220（約+29%）, tl_mean -0.040 s, avg_power -11.4 mW（約-3.6%）

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

## 注意・補正

- 2026-01-24 D3 scan70 n10 run01: TXSD preambleのパルス数が+1で記録され、ファイル名が c2/c3/c4 になっている（本来 c1/c2/c3）。
  - 解析では adv_count と RX の label で再ラベルする（固定100≈1790、固定500≈357、policy≈1225）。
- 2026-01-24 次回以降: D3 TXSD の preamble window を 300ms に短縮し、cond_id ずれを抑制（program_id: TXSD_UCCS_D3_SCAN70_v2）。

## 更新履歴

- 2026-01-24: D3 TXSD preamble window を 300ms に短縮（program_id v2）。
- 2026-01-24: D3 scan70 n10 run01 のTXSDラベルずれ（preamble+1）を記録。解析はadv_count/RXタグで補正。
- 2026-01-24: N=10拡張タスクの初版を作成

