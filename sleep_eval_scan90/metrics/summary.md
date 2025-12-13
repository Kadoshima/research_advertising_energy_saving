# sleep_eval_scan90: TXSD power summary

集計元: `sleep_eval_scan90/data/**/TX/trial_*.csv`（TXSD INA219ログ）

集計スクリプト: `sleep_eval_scan90/analysis/summarize_txsd_power.py`

出力CSV: `sleep_eval_scan90/metrics/txsd_power_summary.csv`

## 結果（mean_p_mW）
- sleep_on
  - 100ms: n=2, mean=200.80 mW, std=0.57 mW
  - 2000ms: n=5, mean=178.74 mW, std=1.38 mW

差分（2000ms - 100ms）: -22.06 mW（約 -11.0%）

## サニティチェック（RX受信イベント率）
- RXログ（`sleep_eval_scan90/data/*/RX/rx_trial_*.csv`）のADV行カウントより:
  - 100ms: 約7.8 adv/s（n=2, 59s程度）
  - 2000ms: 約0.4 adv/s（n=5, 55–58s程度）
→ intervalの切替が概ね成立していることの確認用（PDR評価用途ではない）。

注記:
- `sleep_on/100/TX/trial_064_on.csv` はフッタ無しのため除外。
- sleep_off データを `sleep_eval_scan90/data/sleep_off/` に追加すると、同じ集計スクリプトでON/OFF比較の土台が揃う。
