# data/

`uccs_d2_scan90` の実機ログ（RX/TXSDのSDカード内容）をここに集約する。

- `RX/`: RX の SD `/logs/`（`rx_trial_*.csv` など）
- `TX/`: TXSD の SD `/logs/`（`trial_*.csv` など。フォルダ名は互換のため `TX/` としている）

## ルール

* 1回の計測ごとに run ディレクトリを作成（例: `01/`, `02/`）。
* その中に `RX/` と `TX/` を作り、SDの `/logs/` を丸ごとコピーする。
* `README.md` に測定条件（距離/環境/電源/scan duty 等）を簡潔に残す。

## 現状（暫定）

- 2025-12-14 取得分は `data/RX/` と `data/TX/` に直接配置（run=01相当）。次回から run ディレクトリに揃える。
- 2025-12-15 D2b（CCS反転でpolicy張り付き解消）: `uccs_d2_scan90/data/B/`（READMEあり、集計は `uccs_d2_scan90/metrics/B/summary.md`）
