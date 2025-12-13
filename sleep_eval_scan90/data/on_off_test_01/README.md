# on_off_test_01

sleep ON/OFF × interval ∈ {100,500,1000,2000}ms を `N_CYCLES=2`（各条件n=2）で取得したデータセット。

## 構造
- `TX/` : TXSD（INA219）ログ（`trial_*.csv`）
- `RX/` : RXログ（`rx_trial_*.csv`）
- `TX_excluded/` : 除外（短時間など）
- `RX_excluded/` : 除外（短時間など）

## 採用ルール（今回の「適切データ」）
- TXSD（`TX/`）
  - 末尾に `# summary` と `# diag` があり、かつ `ms_total>=50s` のみ採用。
  - `sleep=` と `adv_interval_ms` は meta 行の値を採用。
- RX（`RX/`）
  - `# condition_label` があり、かつ `ms_total>=50s` のみ採用。

## 除外（移動済み）
- TX_excluded/
  - `trial_001_c1_i100_off.csv`（短時間）
  - `trial_002_c1_i100_off.csv`（短時間）
- RX_excluded/
  - `rx_trial_001.csv` / `rx_trial_002.csv` / `rx_trial_003.csv`（短時間）

## 集計
- TXSD power
  - 解析: `sleep_eval_scan90/analysis/summarize_txsd_power.py --run 'on_off_test_01' --min-ms-total 50000`
  - 出力:
    - `sleep_eval_scan90/metrics/on_off_test_01/txsd_power_summary.csv`
    - `sleep_eval_scan90/metrics/on_off_test_01/txsd_power_trials.csv`
    - `sleep_eval_scan90/metrics/on_off_test_01/txsd_power_diff.md`（DoD）
    - `sleep_eval_scan90/plots/on_off_test_01/txsd_power_summary.png`
- RX rate（間隔が概ね反映されているかのサニティ）
  - 解析: `sleep_eval_scan90/analysis/summarize_rx_trials.py --run 'on_off_test_01' --min-ms-total 50000`
  - 出力:
    - `sleep_eval_scan90/metrics/on_off_test_01/rx_rate_summary.csv`
    - `sleep_eval_scan90/metrics/on_off_test_01/rx_trials.csv`

## 結果（TXSD mean_p_mW, mean±std, n=2）
- sleep OFF
  - 100ms: 202.20 ± 0.71 mW
  - 500ms: 183.75 ± 0.21 mW
  - 1000ms: 180.70 ± 0.14 mW
  - 2000ms: 178.35 ± 1.20 mW
- sleep ON
  - 100ms: 202.30 ± 0.99 mW
  - 500ms: 183.55 ± 0.49 mW
  - 1000ms: 179.85 ± 0.78 mW
  - 2000ms: 178.70 ± 1.41 mW

### DoD（difference-of-differences, 100ms基準）
- `sleep_eval_scan90/metrics/on_off_test_01/txsd_power_diff.md` のとおり
  - sleep_effect@100ms = P(100,OFF) − P(100,ON) = −0.10 mW
  - sleep_effect@2000ms = P(2000,OFF) − P(2000,ON) = −0.35 mW
  - DoD = −0.25 mW

