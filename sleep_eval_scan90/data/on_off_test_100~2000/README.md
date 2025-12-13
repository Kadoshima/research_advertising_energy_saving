# on_off_test_100~2000

interval ∈ {100,500,1000,2000}ms を `N_CYCLES=2`（計8試行）で取得したデータセット。

## 構造
- `TX/` : TXSD（INA219）ログ（`trial_*.csv`）
- `RX/` : RXログ（`rx_trial_*.csv`）

## 集計
- 解析: `sleep_eval_scan90/analysis/summarize_txsd_power.py --run 'on_off_test_100~2000' --min-ms-total 50000`
- 出力:
  - `sleep_eval_scan90/metrics/on_off_test_100~2000/txsd_power_summary.csv`
  - `sleep_eval_scan90/metrics/on_off_test_100~2000/txsd_power_trials.csv`
  - `sleep_eval_scan90/plots/on_off_test_100~2000/txsd_power_summary.png`

## 注意
- `trial_*_unk.csv` や 0byte のファイルが混在している場合がある。集計では `ms_total>=50s` のみ採用する。

