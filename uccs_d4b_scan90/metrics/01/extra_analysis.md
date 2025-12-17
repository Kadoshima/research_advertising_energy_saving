# D4B run01: 追加解析メモ（tail / conditional）

このrun01は「同電力（同α）なのにQoS（pout/TL）が改善」の主結果を持つが、poutは少数のアウトエイジイベント（TL>1s）で決まりやすい。
そのため、平均化したタイミング指標よりも「尾（outage）」に焦点を当てた可視化を追加する。

## 1) outage story（失敗イベント中心のストーリー図）

- 出力: `uccs_d4b_scan90/plots/outage_story_01/fig_outage_timeline.svg`
- 遷移の選び方: `uccs_d4b_scan90/plots/outage_story_01/outage_ranking.csv` の上位（U-onlyのoutage率が大きい遷移）から機械的に選択
- 例（選択イベント）: transition_step=1128 は U-onlyでTL≈9.889s（outage）だが、Policy(U+CCS)はTL≈0.212s（非outage）

再現コマンド:

`python3 uccs_d4b_scan90/analysis/outage_story_trace.py --rx-dir uccs_d4b_scan90/data/01/RX --truth Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv --out-dir uccs_d4b_scan90/plots/outage_story_01 --n-steps 1800 --tau-s 1.0 --window-s 3.0`

## 2) Poutの寄与分解（尾の集中度）

- 出力: `uccs_d4b_scan90/plots/pout_tail_01/`
  - `fig_outage_count_hist.svg`（trialごとのoutage数分布）
  - `fig_delta_pout_cum.svg`（上位K遷移がΔPoutをどれだけ説明するか）

再現コマンド:

`python3 uccs_d4b_scan90/analysis/pout_tail_decomposition.py --per-transition-csv uccs_d4b_scan90/plots/outage_story_01/per_transition.csv --outage-ranking-csv uccs_d4b_scan90/plots/outage_story_01/outage_ranking.csv --out-dir uccs_d4b_scan90/plots/pout_tail_01 --tau-s 1.0 --top-k-max 20`

## 3) 条件付きタイミング（失敗しやすい遷移のみ）

- 出力: `uccs_d4b_scan90/plots/ccs_timing_conditional_01/fig_event_triggered_p100_conditional.svg`
- 条件: U-onlyが悪化している遷移（outage差上位topK）に限定して `P(interval=100ms)` を再集計（平均化で差が薄まるのを避ける）

再現コマンド:

`python3 uccs_d4b_scan90/analysis/ccs_timing_analysis_conditional.py --rx-dir uccs_d4b_scan90/data/01/RX --truth Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv --outage-ranking-csv uccs_d4b_scan90/plots/outage_story_01/outage_ranking.csv --out-dir uccs_d4b_scan90/plots/ccs_timing_conditional_01 --n-steps 1800 --window-s 2.0 --subset u_only_worse --top-k 5`

