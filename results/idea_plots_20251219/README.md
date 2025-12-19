# idea_plots_20251219

実験データからの探索的な図案をまとめたディレクトリ。各図はサブディレクトリに格納し、生成スクリプトと入力ログの SHA256 を記載。

## 構成
- `stress_fixed_s4_energy_vs_time/` : S4 固定間隔（100/500/1000/2000ms）の累積エネルギー
- `stress_fixed_s4_tradeoff_power_vs_pout/` : 平均電力 vs Pout(1s) 散布図
- `stress_fixed_s4_power_pout_index/` : 平均電力 × Pout(1s) 棒グラフ
- `stress_fixed_s4_eperadv_vs_pout/` : E_per_adv vs Pout(1s) 散布図
- `uccs_s4_energy_vs_time/` : UCCS 条件の累積エネルギー（D4B+D4混在）
- `uccs_s4_tradeoff_power_vs_pout/` : UCCS 条件の平均電力 vs Pout(1s) 散布図
- `uccs_s4_power_pout_index/` : UCCS 条件の平均電力 × Pout(1s) 棒グラフ
- `uccs_s4_pout_tau_curves/` : UCCS 条件の Pout(tau) カーブ（tau=1/2/3s）
- `uccs_transition_aligned_p100/` : 遷移アラインの P(100ms) 波形（Policy vs U-only）
- `uccs_policy_vs_uonly_paired_delta_pout/` : Policy vs U-only のペア差分（Pout(1s)）

## 生成日
- 2025-12-19
