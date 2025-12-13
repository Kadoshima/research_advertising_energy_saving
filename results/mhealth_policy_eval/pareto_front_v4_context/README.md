# Pareto sweep v4 (context mixing: stable=S1, transition=S4)
- 生成物: `results/mhealth_policy_eval/pareto_front_v4_context/`
  - `pareto_sweep.csv` : 243グリッド（u_mid∈{0.10,0.15,0.20}, u_high∈{0.25,0.30,0.35}, c_mid∈{0.10,0.15,0.20}, c_high∈{0.25,0.30,0.35}, hysteresis∈{0.02,0.05,0.08}, u_high>u_mid, c_high>c_mid）
  - `pareto_summary.md` : δ=0.1/0.2 の上位（avg_power軸, context mixing適用）
  - `pareto_plots.png` : pout_1s vs avg_power 散布図＋δ=0.2 上位10のintervalシェア stacked bar
- 評価ロジック: HAR窓を stable/transition に2分類し、期待値合成を stable→S1、transition→S4 メトリクスで混合。
  - transition 判定: 窓長内に truth_label4 の遷移があれば遷移扱い。なければ CCS_ema >= 0.30 で遷移扱い（デフォルト）。
  - shares_ctx_weighted を用いて、全窓に対する比率で S1/S4 を線形合成。
- 実行例:
```bash
.venv_mhealth310/bin/python scripts/sweep_policy_pareto.py \
  --context-mixing --metric power \
  --out-csv results/mhealth_policy_eval/pareto_front_v4_context/pareto_sweep.csv \
  --out-summary results/mhealth_policy_eval/pareto_front_v4_context/pareto_summary.md

CSV_PATH=results/mhealth_policy_eval/pareto_front_v4_context/pareto_sweep.csv \
OUT_PATH=results/mhealth_policy_eval/pareto_front_v4_context/pareto_plots.png \
METRIC=power \
.venv_mhealth310/bin/python scripts/plot_pareto_sweep.py
```
- 速報: δ=0.1 依然なし。δ=0.2 上位は pout_1s ≈0.126–0.129、share100≈0.40–0.46、share2000≈0.52–0.58、avg_power≈200.48–200.50 mW（ほぼフラット）。
