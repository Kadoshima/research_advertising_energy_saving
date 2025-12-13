# on_off_test_100~2000_02

interval ∈ {100,500,1000,2000}ms を `N_CYCLES=2`（計8試行）で繰り返し取得したデータセット。

## 構造
- `TX/` : TXSD（INA219）ログ（`trial_*.csv`）
- `RX/` : RXログ（`rx_trial_*.csv`）
- `TX_excluded/` : 除外（unk/0byte/短時間など）
- `RX_excluded/` : 除外（短時間など）

## 採用ルール（今回の「適切データ」）
- TXSD（`TX/`）
  - 末尾に `# summary` と `# diag` があり、かつ `ms_total>=50s` のみ採用。
  - `sleep=` は meta 行を優先（このrunは `sleep=on` のみ）。
- RX（`RX/`）
  - `# condition_label` があり、かつ `ms_total>=50s` のみ採用。

## 収録ブロック（RXファイル番号の目安）
- `rx_trial_004`〜`rx_trial_011` : 2サイクル（100→500→1000→2000を2周）
- `rx_trial_012`〜`rx_trial_019` : 2サイクル
- `rx_trial_020`〜`rx_trial_027` : 2サイクル
- `rx_trial_028`〜`rx_trial_035` : 2サイクル
- `rx_trial_036`〜`rx_trial_040` : 途中終了前の一部（`rx_trial_041` は23sで除外）

## 除外（移動済み）
- TX_excluded/
  - `trial_001_c0_i0_unk.csv`（unknown/短時間）
  - `trial_001_c1_i100_on.csv`（フッタ無し）
  - `trial_002_c1_i100_on.csv`（0byte）
  - `trial_010_c2_i500_on.csv`（短時間: 23s）
- RX_excluded/
  - `rx_trial_001.csv` / `rx_trial_002.csv` / `rx_trial_003.csv`（短時間）
  - `rx_trial_041.csv`（短時間: 23s）

## 集計
- TXSD power
  - 解析: `sleep_eval_scan90/analysis/summarize_txsd_power.py --run 'on_off_test_100~2000_02' --min-ms-total 50000`
  - 出力:
    - `sleep_eval_scan90/metrics/on_off_test_100~2000_02/txsd_power_summary.csv`
    - `sleep_eval_scan90/metrics/on_off_test_100~2000_02/txsd_power_trials.csv`
    - `sleep_eval_scan90/plots/on_off_test_100~2000_02/txsd_power_summary.png`
- RX rate（間隔が概ね反映されているかのサニティ）
  - 解析: `sleep_eval_scan90/analysis/summarize_rx_trials.py --run 'on_off_test_100~2000_02' --min-ms-total 50000`
  - 出力:
    - `sleep_eval_scan90/metrics/on_off_test_100~2000_02/rx_rate_summary.csv`
    - `sleep_eval_scan90/metrics/on_off_test_100~2000_02/rx_trials.csv`

## 結果（sleep_on）
- TXSD mean_p_mW（n=TXSD trials）
  - 100ms: 198.56 mW（n=10）
  - 500ms: 180.80 mW（n=9）
  - 1000ms: 178.62 mW（n=9）
  - 2000ms: 177.47 mW（n=9）
- RX rate_hz（n=RX trials）
  - I100: 7.93 Hz（n=10）
  - I500: 1.67 Hz（n=9）
  - I1000: 0.85 Hz（n=9）
  - I2000: 0.42 Hz（n=9）

## 注意
- run名は `on_off_test` を含むが、今回の `TX/` は meta 上 `sleep=on` のみ（sleep OFFは未取得）。
