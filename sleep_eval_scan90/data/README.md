# sleep_eval_scan90 データ

## 構造
- `sleep_on/<interval_ms>/` : sleep ON（想定）の計測データ
  - 例: `sleep_on/100/`, `sleep_on/2000/`
  - `TX/` : TXSD（INA219）ログ（`trial_*.csv`）
  - `RX/` : RXログ（`rx_trial_*.csv`）
- `sleep_off/<interval_ms>/` : sleep OFF の計測データ（今後追加）

## 注意
- TXSDログは末尾に `# summary` と `# diag` が付与される。これが無いファイルは「途中終了」とみなし、集計では除外している。
  - 例: `sleep_on/100/TX/trial_064_on.csv` はフッタ無し（除外）。
- RXログも同様に、極端に短いファイルは途中終了の可能性がある。
  - 例: `sleep_on/100/RX/rx_trial_056.csv` は行数が極端に少ない（参考扱い）。

## 集計
- `sleep_eval_scan90/analysis/summarize_txsd_power.py` がTXSDログを集計し、`sleep_eval_scan90/metrics/` と `sleep_eval_scan90/plots/` を生成する。

## SHA256
- `sleep_eval_scan90/data/SHA256.txt` に、`data/` 配下のCSV/READMEのSHA256を保存。
