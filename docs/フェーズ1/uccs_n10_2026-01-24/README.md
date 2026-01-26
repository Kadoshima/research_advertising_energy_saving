# uccs_n10_2026-01-24（UCCS D3/D4B scan70 N=10 拡張）

- 更新日: 2026-01-25
- 状態: draft

## 目的/範囲

- D3（scan70, S4のみ）と D4B（scan70, S4のみ）の各条件を **n=10** まで増やし、統計的主張の強度を上げる。
- 追加実験は既存のスケッチ/解析仕様を維持し、`program_id` をCSV列に追加した版で実施する。

## 入力データ（出所/版/行数/SHA256）

| データ | パス | 出所/版 | 行数 | SHA256 | 備考 |
| --- | --- | --- | --- | --- | --- |
| D3 scan70 RX/TXSD | `uccs_d3_scan70/data/02_n10_run01/` | 実測 | RX=33/7636行, TXSD=33/554213行, manifest=66行 | 51b013a097a3f9eca7b568f3fe9ddc16a448da0d2f92bace02877a0f6f40f99b | manifest.csv を作成済み |
| D4B scan70 RX/TXSD | `uccs_d4b_scan70/data/02_n10_run01/` | 実測 | RX=40/10035行, TXSD=40/700940行, manifest=80行 | 82461bf48bd9f38b6af4b2bfc788e6ce35baff1334b98251a3f2ef6039e76746 | manifest.csv を作成済み |

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

### D4B scan70 n10 集計結果（02_n10_run01）

- 出力: `uccs_d4b_scan70/metrics/02_n10_run01/summary.md`
- Fixed100: pout_1s=0.1439±0.0334, tl_mean=3.952±0.446, avg_power=314.5±3.7 mW
- Fixed500: pout_1s=0.3512±0.0611, tl_mean=4.872±0.305, avg_power=289.0±6.2 mW
- Policy: pout_1s=0.1415±0.0154, tl_mean=3.827±0.304, avg_power=306.9±4.0 mW
- U-only(CCS-off): pout_1s=0.1415±0.0321, tl_mean=3.897±0.515, avg_power=307.4±4.0 mW
- Policy vs Fixed500: pout_1s -0.2098（約-60%）, tl_mean -1.045 s, avg_power +17.9 mW（約+6.2%）
- Policy vs Fixed100: pout_1s -0.0024（約-1.7%）, tl_mean -0.125 s, avg_power -7.6 mW（約-2.4%）
- Policy vs U-only: pout_1s 0.0000（約+0%）, tl_mean -0.070 s, avg_power -0.5 mW（約-0.2%）

### D4B scan70 n10 詳細差分（CI/効果量）

- 出力: `uccs_d4b_scan70/metrics/02_n10_run01/effects_ci.md`
- まとめ表（差分=Policy - 比較対象、95% CI はブートストラップ）:

| 比較 | 指標 | 差分 | 95% CI | Hedges g (95% CI) |
| --- | ---:| ---:| ---:| ---:|
| Policy - Fixed500 | Pout(1s) | -0.2098 | [-0.2463, -0.1732] | -4.5114 [-7.4795, -3.6685] |
| Policy - Fixed500 | TL mean (s) | -1.0454 | [-1.2888, -0.7802] | -3.2843 [-6.3687, -2.1796] |
| Policy - Fixed500 | Avg power (mW) | +17.9203 | [13.3875, 22.0038] | +3.2915 [2.1924, 7.2932] |
| Policy - Fixed100 | Pout(1s) | -0.0024 | [-0.0220, 0.0195] | -0.0898 [-1.5582, 0.6501] |
| Policy - Fixed100 | TL mean (s) | -0.1253 | [-0.4312, 0.2034] | -0.3143 [-1.6422, 0.4866] |
| Policy - Fixed100 | Avg power (mW) | -7.5666 | [-10.7747, -4.4339] | -1.8811 [-3.1116, -1.2333] |
| Policy - U-only | Pout(1s) | -0.0000 | [-0.0220, 0.0220] | -0.0000 [-0.9384, 0.9463] |
| Policy - U-only | TL mean (s) | -0.0700 | [-0.4090, 0.2870] | -0.1585 [-1.2809, 0.7044] |
| Policy - U-only | Avg power (mW) | -0.4816 | [-3.7152, 2.8327] | -0.1154 [-1.0944, 0.7411] |

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

- 2026-01-25: D4B scan70 n10 のCI/効果量を追記し、図表をn10データで更新。
- 2026-01-24: D3 TXSD preamble window を 300ms に短縮（program_id v2）。
- 2026-01-24: D3 scan70 n10 run01 のTXSDラベルずれ（preamble+1）を記録。解析はadv_count/RXタグで補正。
- 2026-01-24: N=10拡張タスクの初版を作成

