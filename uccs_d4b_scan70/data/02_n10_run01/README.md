# 02_n10_run01

- 日付: 2026-01-25
- 状態: draft
- 対象: D4B scan70 n10 run01（TXSD/RX）
- 開始時刻: 2026-01-25 11:00 JST（目安）
- 距離: 1 m

## 構成

- TX/ : TXSD SDの `/logs/trial_*.csv` をコピー（D:\logs 由来）
- RX/ : RX SDの `/logs/rx_trial_*.csv` をコピー（D:\logs 由来）
- manifest.csv : 取得ファイルの行数/SHA256/条件を記録

## 補足

- RXは `rx_trial_188..227` を採用（40試行）。
- TXSDは cond_id=1..4 の最新10件ずつを採用（合計40試行）。
- TXSD PROGRAM_ID: TXSD_UCCS_D4B_SCAN70_v1
- RX PROGRAM_ID: RX_UCCS_D4B_SCAN70_v1
- USB給電時に負電流が出た初期ログは採用対象外。

## 取得元

- SD: TXSD（D:\logs）
  - コピー先: `uccs_d4b_scan70/data/02_n10_run01/TX/`
- SD: RX（D:\logs）
  - コピー先: `uccs_d4b_scan70/data/02_n10_run01/RX/`

## 行数/SHA256

- manifest.csv: rows=80, sha256=82461bf48bd9f38b6af4b2bfc788e6ce35baff1334b98251a3f2ef6039e76746
- RX: files=40, rows=10035
- TXSD: files=40, rows=700940
