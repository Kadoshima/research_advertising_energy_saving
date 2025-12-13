# mHealth 合成セッション オフライン方策評価
- 生成データ: `data/mhealth_synthetic_sessions_v1/`（3 seeds×3本、U/CCS付き HAR 窓ログ）
- 固定間隔メトリクス: `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv`（S1/S4平均）
- 評価スクリプト: `scripts/eval_policy_offline.py`
  - 入力: HARログディレクトリ、固定メトリクスCSV
  - 出力: 方策別の interval 割合 + 固定メトリクスとの期待値合成（pdr_unique, pout_1s, tl_mean_s, E_per_adv_uJ, avg_power_mW）
  - デフォルト方策: U_ema / CCS_ema 閾値 (u_mid=0.15, u_high=0.30, c_mid=0.20, c_high=0.35, hysteresis=0.05, 初期500ms)
  - 評価は `mask_eval_window==1` の窓のみ使用（境界±1s除外）。有効窓率 ≈ 0.762 を前提。
- グリッドスイープ: `scripts/sweep_policy_pareto.py`（結果: `pareto_front/pareto_sweep.csv`, `pareto_front/pareto_summary.md`）
  - グリッド: u_mid∈{0.10,0.15,0.20}, u_high∈{0.25,0.30,0.35}, c_mid∈{0.10,0.15,0.20}, c_high∈{0.25,0.30,0.35}, hysteresis∈{0.02,0.05,0.08}（u_high>u_mid, c_high>c_mid のみ）
  - δ=0.1 は該当なし、δ=0.2 で上位は (u_mid=0.10,c_mid=0.10,c_high=0.25,hyst=0.08,u_high=0.25) など（pout_1s≈0.197, E_per_adv_uJ≈33,130, share100≈0.891, share2000≈0.014, switch_rate≈0.023）
- スイープ可視化: `scripts/plot_pareto_sweep.py` → `pareto_front/pareto_plots.png`（左: pout_1s vs E_per_adv 散布図、右: δ=0.2 上位10のintervalシェア stacked bar）

## コンテキスト混合版（stable→S1, transition→S4）
- スクリプト: `eval_policy_offline.py` / `sweep_policy_pareto.py` に `--context-mixing` を追加。truth窓内遷移あり or `CCS_ema>=0.30` を transition としてS4メトリクス、その他をS1メトリクスで合成。
- 出力: `results/mhealth_policy_eval/pareto_front_v4_context/`（CSV/summary/plot/README）。δ=0.1なし。δ=0.2で pout_1s≈0.126–0.129、share100≈0.40–0.46、share2000≈0.52–0.58、avg_power≈200.48–200.50 mW（依然フラット）。
- 解釈: 「いつ短くしたか」を入れるとQoSは改善する。電力軸は、固定メトリクスの avg_power をそのまま使うとフラットになりやすいので、必要に応じて外部 power table で上書きする。

## Power table（sleep_evalからの上書き）
- 目的: `avg_power_mW_mean` を「固定intervalの実測テーブル」で置き換え、share100削減がそのまま省電力に効く形で評価する。
- テーブル: `results/mhealth_policy_eval/power_table_sleep_eval_2025-12-13.csv`
  - 生成元: `sleep_eval_scan90/metrics/on_off_test_100~2000/txsd_power_summary.csv`（TXSD mean_p_mW, n=2, 2025-12-13）
  - 適用: `scripts/eval_policy_offline.py` / `scripts/sweep_policy_pareto.py` / `scripts/build_policy_table.py` の `--power-table` で上書き。

## 再現コマンド（デフォルト方策）
```bash
.venv_mhealth310/bin/python scripts/eval_policy_offline.py \
  --har-dir data/mhealth_synthetic_sessions_v1/sessions \
  --metrics results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv \
  --power-table results/mhealth_policy_eval/power_table_sleep_eval_2025-12-13.csv \
  --out-json results/mhealth_policy_eval/policy_eval_default.json
```

## 結果サマリ（policy_eval_default.json）
- intervalシェア: 100ms 47.1%, 500ms 9.2%, 2000ms 43.7%（1000msは未使用）
- 期待値（S1/S4平均メトリクスとの合成）
  - pdr_unique ≈ 0.909
  - pout_1s ≈ 0.166
  - tl_mean_s ≈ 10.49
  - E_per_adv_uJ ≈ 193,348
  - avg_power_mW ≈ 200.48

## 図表
- 比較表: `policy_table.md`
- バーチャート: `policy_table.png`（pdr_unique / pout_1s / tl_mean_s / E_per_adv を可視化）

## メモ
- 有効窓のみで評価しているため、mask_window_zero_ratio≈0.238（境界重畳による無効化）が考慮済み。
- 1000msが選ばれないのは閾値設定による。閾値/ヒステリシスを調整し、500↔2000 だけでなく 1000ms を使う設定も試行可能。

## 現在の結論と次アクション（2025-12-13）
- 事実: scan90固定メトリクスでは S4 の最良でも pout_1s≈0.177（1s基準）。このため δ=0.1 は行動シェア調整では達成不能。コンテキスト混合で pout_1s≈0.12 まで改善するが、avg_power はほぼフラット。
- 更新: `sleep_eval_scan90` の固定interval sweep により power table を取得したので、オフライン評価の電力軸は `--power-table` で置換可能。
- 次にやること:
  1) `--power-table` 付きで Pareto sweep を再実行し、電力（またはE_total/dur）でのトレードオフを再確認する。  
  2) δ=0.12〜0.18 を刻んで feasible 境界（制約が効く帯）を1図で出す。  
  3) 実機の動的検証は「100↔500（2値）」から開始し、Fixed 100/500/2000と最小本数で比較する。
