# mHealth 合成セッション オフライン方策評価
- 生成データ: `data/mhealth_synthetic_sessions_v1/`（3 seeds×3本、U/CCS付き HAR 窓ログ）
- 固定間隔メトリクス: `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v5.csv`（TL/Pout の時間同期込み）
- 評価スクリプト: `scripts/eval_policy_offline.py`
  - 入力: HARログディレクトリ、固定メトリクスCSV
  - 出力: 方策別の interval 割合 + 固定メトリクスとの期待値合成（pdr_unique, pout_1s, tl_mean_s, E_per_adv_uJ, avg_power_mW）
  - デフォルト方策: U_ema / CCS_ema 閾値 (u_mid=0.15, u_high=0.30, c_mid=0.20, c_high=0.35, hysteresis=0.05, 初期500ms)
  - 評価は `mask_eval_window==1` の窓のみ使用（境界±1s除外）。有効窓率 ≈ 0.762 を前提。
- グリッドスイープ: `scripts/sweep_policy_pareto.py`（結果: `pareto_front/pareto_sweep.csv`, `pareto_front/pareto_summary.md`）
  - グリッド: u_mid∈{0.10,0.15,0.20}, u_high∈{0.25,0.30,0.35}, c_mid∈{0.10,0.15,0.20}, c_high∈{0.25,0.30,0.35}, hysteresis∈{0.02,0.05,0.08}（u_high>u_mid, c_high>c_mid のみ）
  - v5（時間同期あり）に差し替えると、pout_1s の水準や feasible 境界が変わりうる（下記の v6 を参照）。
- スイープ可視化: `scripts/plot_pareto_sweep.py` → `pareto_front/pareto_plots.png`（左: pout_1s vs E_per_adv 散布図、右: δ=0.2 上位10のintervalシェア stacked bar）

## コンテキスト混合版（stable→S1, transition→S4）
- スクリプト: `eval_policy_offline.py` / `sweep_policy_pareto.py` に `--context-mixing` を追加。truth窓内遷移あり or `CCS_ema>=0.30` を transition としてS4メトリクス、その他をS1メトリクスで合成。
- 出力: `results/mhealth_policy_eval/pareto_front_v4_context/`（CSV/summary/plot/README）。δ=0.1なし。δ=0.2で pout_1s≈0.126–0.129、share100≈0.40–0.46、share2000≈0.52–0.58、avg_power≈200.48–200.50 mW（依然フラット）。
- 解釈: 「いつ短くしたか」を入れるとQoSは改善する。電力軸は、固定メトリクスの avg_power をそのまま使うとフラットになりやすいので、必要に応じて外部 power table で上書きする。

## Power table（sleep_evalからの上書き）
- 目的: `avg_power_mW_mean` を「固定intervalの実測テーブル」で置き換え、share100削減がそのまま省電力に効く形で評価する。
- 主線テーブル: `results/mhealth_policy_eval/power_table_sleep_eval_2025-12-14_interval_sweep_sleep_on_n9_10.csv`
  - 生成元: `sleep_eval_scan90/metrics/on_off_test_100~2000_02/txsd_power_summary.csv`（TXSD mean_p_mW, sleep_onのみ, n=9–10, 2025-12-14）
  - 値（mW）: 100=198.56, 500=180.80, 1000=178.62, 2000=177.47
  - 適用: `scripts/eval_policy_offline.py` / `scripts/sweep_policy_pareto.py` / `scripts/build_policy_table.py` の `--power-table` で上書き。
  - 補助（sleep効果の切り分け）: `sleep_eval_scan90/metrics/on_off_test_01/txsd_power_diff.md`（DoD=-0.25mW, n=2）

## 再現コマンド（デフォルト方策）
```bash
.venv_mhealth310/bin/python scripts/eval_policy_offline.py \
  --har-dir data/mhealth_synthetic_sessions_v1/sessions \
  --metrics results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v5.csv \
  --power-table results/mhealth_policy_eval/power_table_sleep_eval_2025-12-14_interval_sweep_sleep_on_n9_10.csv \
  --context-mixing \
  --out-json results/mhealth_policy_eval/policy_eval_default.json
```

## 結果サマリ（policy_eval_default.json）
- intervalシェア: 100ms 47.1%, 500ms 9.2%, 2000ms 43.7%（1000msは未使用）
- 期待値（context mixing: stable→S1 / transition→S4 + power table 反映）
  - pdr_unique ≈ 0.909
  - pout_1s ≈ 0.172
  - tl_mean_s ≈ 4.38
  - E_per_adv_uJ ≈ 193,566
  - avg_power_mW ≈ 187.71

## 図表
- 比較表: `policy_table.md`
- バーチャート: `policy_table.png`（pdr_unique / pout_1s / tl_mean_s / E_per_adv を可視化）
- レター用δ帯（tight, scan90 v5, power table=robust）: `letter_v3_scan90_v5_delta_tight_sleep_on_n9_10/fig_delta_band.png`
- 実機100↔500用 δ帯（tight, actions={100,500}）: `letter_v4_scan90_v5_delta_tight_sleep_on_n9_10_actions_100_500/fig_delta_band.png`

## メモ
- 有効窓のみで評価しているため、mask_window_zero_ratio≈0.238（境界重畳による無効化）が考慮済み。
- 1000msが選ばれないのは閾値設定による。閾値/ヒステリシスを調整し、500↔2000 だけでなく 1000ms を使う設定も試行可能。

## 現在の結論と次アクション（2025-12-14）
- 事実（v5）: TL/Pout は開始位相ズレ（RX `ms` と truth）を補正しないと歪むため、以後は scan90 v5 を基準にする（`docs/metrics_definition.md` の「時間同期」参照）。
- 更新（v7）: scan90 v5 + power table(robust) + context mixing の Pareto sweep を `results/mhealth_policy_eval/pareto_front_v7_power_table_scan90_v5_sleep_on_n9_10/` に出力（例: δ=0.03 feasible 36/243）。
- 更新（v8, actions={100,500}）: 実機の行動空間に揃えた2値版の Pareto sweep を `results/mhealth_policy_eval/pareto_front_v8_power_table_scan90_v5_sleep_on_n9_10_actions_100_500/` に出力（δ=0.03 feasible 243/243）。
- 次にやること:
  1) δ tight（0.02/0.03/0.04）をレター主線として凍結し、候補点（特に δ=0.03のpower-min）を実機で成立確認する。  
  2) 実機の動的検証は「100↔500（2値）」から開始し、Fixed 100/500 と最小本数で比較する（動的はTX payloadに時刻/状態を入れて同期を担保）。
     - 実機用の代表点（例, δ=0.03 power-min, actions={100,500}）: `letter_v4_scan90_v5_delta_tight_sleep_on_n9_10_actions_100_500/summary.md` を参照。  
