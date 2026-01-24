# 02_n10_run01

- 日付: 2026-01-24
- 状態: draft
- 対象: D3 scan70 n10 run01（TXSD/RX）
- 開始時刻: 2026-01-24 22:00 JST
- 距離: 1 m

## 構成

- TX/ : TXSD SDの `/logs/trial_*.csv` をコピー（D:\logs 由来）
- RX/ : RX SDの `/logs/rx_trial_*.csv` をコピー（D:\logs 由来）
- manifest.csv : 取得ファイルの行数/SHA256/条件を記録

## 補足

- TXSDのファイル名 cond_id が +1（c2/c3/c4）にずれ。解析では adv_count と RX の label で再ラベルする。
- TXSD PROGRAM_ID: TXSD_UCCS_D3_SCAN70_v1
- RX SDの `/logs/` に `rx_00279806_a6a2e619.csv` があるため、必要なら別途取り込みする。

## 取得元

- SD: TXSD（D:\logs）
  - コピー先: uccs_d3_scan70/data/02_n10_run01/TX/
- SD: RX（D:\logs）
  - コピー先: uccs_d3_scan70/data/02_n10_run01/RX/

## 行数/SHA256

- manifest.csv: rows=66, sha256=51b013a097a3f9eca7b568f3fe9ddc16a448da0d2f92bace02877a0f6f40f99b
- RX: files=33, rows=7636
- TXSD: files=33, rows=554213
