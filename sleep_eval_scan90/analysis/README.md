# sleep_eval_scan90 analysis

- `summarize_txsd_power.py`: `sleep_eval_scan90/data/**/TX/trial_*.csv`（TXSDログ）のフッタ（`# summary/# diag`）から平均電力を抽出し、`sleep_eval_scan90/metrics/` と `sleep_eval_scan90/plots/` を生成する。
  - `--run <run>` を指定すると `sleep_eval_scan90/metrics/<run>/` と `sleep_eval_scan90/plots/<run>/` に出力する。
  - `data/<run>/condition_overrides.csv`（または `--overrides`）があれば、`cond_id=0` やラベルずれを補正して集計できる。
- `summarize_rx_trials.py`: `sleep_eval_scan90/data/**/RX/rx_trial_*.csv`（RXログ）から `# condition_label` と受信回数/受信レートを抽出し、`sleep_eval_scan90/metrics/` に `rx_trials.csv` と `rx_rate_summary.csv` を生成する。
