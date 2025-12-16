# data/

`uccs_d4_scan90` の実機ログ（RX/TXSDのSDカード内容）を run 単位で集約する。

## ルール

* 1回の計測ごとに run ディレクトリを作成（例: `01/`）。
* その中に `RX/` と `TX/` を作り、SDの `/logs/` を丸ごとコピーする（TX=TXSDログ）。
* `README.md` に測定条件（距離/環境/電源/scan duty 等）を簡潔に残す。

## 例

* `uccs_d4_scan90/data/01/RX/`（`rx_trial_*.csv`）
* `uccs_d4_scan90/data/01/TX/`（`trial_*.csv`）

