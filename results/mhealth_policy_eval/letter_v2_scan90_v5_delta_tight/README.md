# レター用 δ帯（tight, scan90 v5）

- 生成日: 2025-12-14 (JST)
- 目的: `Fixed 500ms` が満たさない厳しめの δ帯（例: 0.03）で、`Fixed 100ms` との比較が成立する図を作る。

## 入力
- Pareto sweep（U+CCS, power table + context mixing）: `results/mhealth_policy_eval/pareto_front_v6_power_table_scan90_v5/pareto_sweep.csv`
- 固定メトリクス（scan90 v5, TL/Poutの時間同期込み）: `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v5.csv`
- power table（sleep_eval, n=2）: `results/mhealth_policy_eval/power_table_sleep_eval_2025-12-13.csv`

## 生成コマンド
```bash
MPLBACKEND=Agg XDG_CACHE_HOME=results/mhealth_policy_eval/.cache MPLCONFIGDIR=results/mhealth_policy_eval/.mplconfig \
  .venv_mhealth310/bin/python scripts/plot_letter_delta_band.py \
    --pareto-csv results/mhealth_policy_eval/pareto_front_v6_power_table_scan90_v5/pareto_sweep.csv \
    --fixed-metrics results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v5.csv \
    --power-table results/mhealth_policy_eval/power_table_sleep_eval_2025-12-13.csv \
    --deltas 0.02,0.03,0.04 \
    --select-deltas 0.02,0.03,0.04 \
    --select-style minpower \
    --out-dir results/mhealth_policy_eval/letter_v2_scan90_v5_delta_tight
```

## 出力
- 図: `fig_delta_band.png`
- 選定点: `selected_policies.csv`, `selected_policies.json`
