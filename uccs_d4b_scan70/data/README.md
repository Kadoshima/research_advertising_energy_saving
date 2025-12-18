# uccs_d4b_scan70/data

## 役割

実機（scan70）で取得したSDカード上の `/logs/` を、runごとにコピーして保管する。

## ディレクトリ構成（推奨）

`data/<run_id>/` 配下に、最低限以下を置く。

- `data/<run_id>/RX/`：RX（受信ロガ）の `rx_trial_*.csv`
- `data/<run_id>/TX/`：TXSD（電力ロガ）の `trial_*.csv`
- `data/<run_id>/README.md`：実験条件のメモ（日時JST、距離、遮蔽物、電源、scan設定、スケッチ名、備考）

例:

`data/01/RX/rx_trial_001.csv`
`data/01/TX/trial_001_c1_s4_fixed100.csv`

## 注意

- 重要: runごとに **SDの `/logs/` を空にしてから**計測する（ログ混在の予防）。
- 解析は scan90 と同じスクリプトを流用する:
  - `python3 uccs_d4b_scan90/analysis/summarize_d4b_run_v2.py --rx-dir uccs_d4b_scan70/data/<run_id>/RX --txsd-dir uccs_d4b_scan70/data/<run_id>/TX --out-dir uccs_d4b_scan70/metrics/<run_id>`

