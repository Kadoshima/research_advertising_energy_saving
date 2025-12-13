# Pareto sweep v3 (adv_rate + power/energy view)
- 生成物: `results/mhealth_policy_eval/pareto_front_v3/`
  - `pareto_sweep.csv` : 243グリッド（u_mid∈{0.10,0.15,0.20}, u_high∈{0.25,0.30,0.35}, c_mid∈{0.10,0.15,0.20}, c_high∈{0.25,0.30,0.35}, hysteresis∈{0.02,0.05,0.08}, u_high>u_mid, c_high>c_mid）
  - `pareto_summary.md` : δ=0.1/0.2 の上位（avg_power軸）
  - `pareto_plots.png` : pout_1s vs avg_power 散布図（size=share100, color=switch_rate）＋ δ=0.2 上位10の interval シェア stacked bar
- 追加指標:
  - `adv_rate` (adv/s) = share100/0.1 + share500/0.5 + share1000/1.0 + share2000/2.0
  - `mean_interval_ms` (調和平均ベース) = 1000 / adv_rate

## 実行コマンド
```bash
.venv_mhealth310/bin/python scripts/sweep_policy_pareto.py \
  --metric power \
  --out-csv results/mhealth_policy_eval/pareto_front_v3/pareto_sweep.csv \
  --out-summary results/mhealth_policy_eval/pareto_front_v3/pareto_summary.md

CSV_PATH=results/mhealth_policy_eval/pareto_front_v3/pareto_sweep.csv \
OUT_PATH=results/mhealth_policy_eval/pareto_front_v3/pareto_plots.png \
METRIC=power \
.venv_mhealth310/bin/python scripts/plot_pareto_sweep.py
```

## 速報（δ=0.2 上位例）
- avg_power ≈ 200.38–200.39 mW（v2と同傾向でフラット）
- share100 ≈ 0.40–0.46, share2000 ≈ 0.52–0.58
- adv_rate ≈ 4.4–5.0 adv/s（固定100msの 10 adv/s 比で約50–56%削減）
- δ=0.1 は該当なし
