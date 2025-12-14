# Pareto-like sweep (scan90 v5 + power table, sleep_on n=9–10)

- 生成日: 2025-12-14 (JST)
- 目的: U/CCSルールの閾値・ヒステリシスをグリッドスイープし、`pout_1s` 制約下で `avg_power_mW` を最小化する候補点を整理する。

## 入力
- HARログ（U/CCS, 合成mHealthセッション）: `data/mhealth_synthetic_sessions_v1/sessions/*_har.csv`
- 固定間隔メトリクス（scan90 v5, stable→S1 / transition→S4 合成に使用）: `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v5.csv`
- power table（TXSD, interval sweep, sleep_on, n=9–10）: `results/mhealth_policy_eval/power_table_sleep_eval_2025-12-14_interval_sweep_sleep_on_n9_10.csv`

## 生成コマンド
```bash
.venv_mhealth310/bin/python scripts/sweep_policy_pareto.py \
  --har-dir data/mhealth_synthetic_sessions_v1/sessions \
  --metrics results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v5.csv \
  --power-table results/mhealth_policy_eval/power_table_sleep_eval_2025-12-14_interval_sweep_sleep_on_n9_10.csv \
  --context-mixing \
  --metric power \
  --deltas 0.02,0.03,0.04 \
  --out-csv results/mhealth_policy_eval/pareto_front_v7_power_table_scan90_v5_sleep_on_n9_10/pareto_sweep.csv \
  --out-summary results/mhealth_policy_eval/pareto_front_v7_power_table_scan90_v5_sleep_on_n9_10/pareto_summary.md

MPLBACKEND=Agg XDG_CACHE_HOME=results/mhealth_policy_eval/.cache MPLCONFIGDIR=results/mhealth_policy_eval/.mplconfig \
  CSV_PATH=results/mhealth_policy_eval/pareto_front_v7_power_table_scan90_v5_sleep_on_n9_10/pareto_sweep.csv \
  OUT_PATH=results/mhealth_policy_eval/pareto_front_v7_power_table_scan90_v5_sleep_on_n9_10/pareto_plots.png \
  METRIC=power \
  .venv_mhealth310/bin/python scripts/plot_pareto_sweep.py
```

## 出力
- `pareto_sweep.csv`: 全243点（各パラメータと share/switch/QoS/power/adv_rate）
- `pareto_summary.md`: δごとのTop候補（power-min / event-min / stable / QoS）
- `pareto_plots.png`: `pout_1s vs avg_power_mW` 散布図 + 上位点のシェア可視化
