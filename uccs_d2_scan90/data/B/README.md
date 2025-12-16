# run B（D2b: CCS反転でpolicy張り付き解消）

## 概要

- 取得日: 2025-12-15
- 目的: D2（`step_idx` 起点 TL/Pout 算出）の枠組みで、**policyが100ms張り付きにならず**に（100↔500）動作することを確認する。
- スケッチ: `uccs_d2_scan90/README.md` の D2b（CCS反転＋preamble guard）を使用。

## データ内容

- RX: `uccs_d2_scan90/data/B/RX/`（`rx_trial_*.csv`）
- TXSD: `uccs_d2_scan90/data/B/TX/`（SD `/logs/trial_*.csv` をコピー）

## 解析結果（参照）

- 集計: `uccs_d2_scan90/metrics/B/summary.md`
- 実行コマンド例:
  - `python3 uccs_d2_scan90/analysis/summarize_d2_run.py --rx-dir uccs_d2_scan90/data/B/RX --txsd-dir uccs_d2_scan90/data/B/TX --out-dir uccs_d2_scan90/metrics/B`
 - 追加取得（B/02）:
   - データ: `uccs_d2_scan90/data/B/02/README.md`
   - 集計: `uccs_d2_scan90/metrics/B_02/summary.md`

## 注意

- TXSD側のファイル名（`cond_id`/tag）が一部混在・誤ラベルの可能性があるため、解析では `adv_count`（tick_count）分布とRXタグ由来の `share100_time_est` を用いて policy のペアリングを復元している。
