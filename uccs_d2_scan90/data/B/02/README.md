# run B/02（D2b追加取得）

## 概要

- 目的: D2b（CCS反転）での追加取得。`run B` の追試（nを増やす）として使用可能か確認する。
- データ:
  - RX: `uccs_d2_scan90/data/B/02/RX/`
  - TXSD: `uccs_d2_scan90/data/B/02/TX/`

## 解析（確認済み）

- 集計: `uccs_d2_scan90/metrics/B_02/summary.md`
- コマンド:
  - `python3 uccs_d2_scan90/analysis/summarize_d2_run.py --rx-dir uccs_d2_scan90/data/B/02/RX --txsd-dir uccs_d2_scan90/data/B/02/TX --out-dir uccs_d2_scan90/metrics/B_02`
- 判定: **使用可能**（6条件×3 repeats のセットが抽出でき、TXSD指標も復元できている）。

