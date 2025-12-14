# metrics/

`uccs_d1_scan90` の実測ログ（`data/<run>/`）から抽出した集計結果を置く。

## 生成

```bash
python3 uccs_d1_scan90/analysis/summarize_d1_run.py --run 01
```

## 出力（runごと）

* `txsd_power_trials.csv`: TXSDログ（trial_*）のフッタから mean_p 等を抽出した一覧
* `txsd_power_summary.csv`: tag（fixed100/fixed500/policy）別の平均・標準偏差
* `rx_trials.csv`: RXログ（rx_trial_*）の受信数・受信率等
* `rx_rate_summary.csv`: condition_label別の平均・標準偏差
* `summary.md`: 速報（差分とpolicyの混合比の推定を含む）

