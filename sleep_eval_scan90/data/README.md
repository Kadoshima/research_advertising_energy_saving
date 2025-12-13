# sleep_eval_scan90 データ

## 構造
- `100/` : ADV interval=100ms の計測データ
  - `TX/` : TXSD（INA219）ログ（`trial_*.csv`）
  - `RX/` : RXログ（`rx_trial_*.csv`）
- `2000/` : ADV interval=2000ms の計測データ
  - `TX/` : TXSD（INA219）ログ（`trial_*.csv`）
  - `RX/` : RXログ（`rx_trial_*.csv`）

## 注意
- TXSDログは末尾に `# summary` と `# diag` が付与される。これが無いファイルは「途中終了」とみなし、集計では除外している。
  - 例: `100/TX/trial_064_on.csv` はフッタ無し（除外）。
- RXログも同様に、極端に短いファイルは途中終了の可能性がある。
  - 例: `100/RX/rx_trial_056.csv` は行数が極端に少ない（参考扱い）。

## 集計
- `sleep_eval_scan90/analysis/summarize_txsd_power.py` がTXSDログを集計し、`sleep_eval_scan90/metrics/` と `sleep_eval_scan90/plots/` を生成する。

## SHA256
- `sleep_eval_scan90/data/SHA256.txt` に、`data/` 配下のCSV/READMEのSHA256を保存。
