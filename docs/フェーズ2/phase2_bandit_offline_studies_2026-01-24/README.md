# Phase 2: Bandit Offline Studies (2026-01-24 v01)

## 目的/範囲
- Safe Contextual Bandit（Safe-UCB）導入前に、報酬/制約推定の妥当性と環境シフト耐性をオフラインで確認する。
- 対象は **非コンテキスト（context固定）** の最小構成（行動=広告間隔、制約=Pout(τ)）とする。

## 入力データ（出所/版/行数/SHA256）
- 報酬モデル（ΔE sweep, μC推定）
  - `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv`（2026-01-21, rows=17, sha256=6dd0e80acaba7b452b02f3e096a613cbf8167deab36396f31d6d777cc835126d）
  - `results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv`（2026-01-21, rows=50, sha256=89521ce5289a0050fb583004423132aab3efaa75a8ddcb87a97c987ef8fc65b9）
- 制約モデル（E1 scan90 full-set）
  - `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_modes_scan90_v5.csv`（rows=8, sha256=2e79663af2a488f42f850eee2d7f08357ff61fc05fea03ed877ab9e8880b7a74）
- 制約モデル（E1 scan90/scan70, {100,500}）
  - `uccs_d4b_scan90/metrics/01/per_trial.csv`（rows=12, sha256=98e60a62e3d4be48c051d05843d33608258d9d91a49bd639d7fdbc2df8cdc598）
  - `uccs_d4b_scan70/metrics/01_fixed/per_trial.csv`（rows=12, sha256=9809fbe0d36130d34a80bc50682ec48fa07396f106402ed0cfc358e64e204832）
- 制約モデル（E2 fixed sweep, RXログ由来）
  - `data/実験データ/研究室/phase1_e2_fixed_sweep_2026-01-21_v01/manifest.csv`（rows=34, sha256=fd5ca19a268c93aa52f6218d520b84680638e8787823d7d5e9a4ccc078230f88）

## 出力物（生成日/生成スクリプト）
- 生成日: 2026-01-24
- 生成スクリプト: `scripts/phase2_offline_eval/run_offline_studies.py`
- 出力ディレクトリ: `results/phase2_offline_studies_2026-01-24_v01/`
  - `tradeoff_table.csv`: env×action の μC と Pout(1s/2s)
  - `epsilon_tau_sensitivity.csv`: (ε,τ) に対する safe/unsafe
  - `validity_reward_split.csv`: 報酬モデルの train/test 分割チェック
  - `validity_constraint_e2_split.csv`: 制約（E2 fixed）train/test 分割チェック
  - `sim_replicates.csv`: シミュレーション各反復の指標
  - `sim_summary.csv`: 集計（mean/std）

## 再現手順（コマンド）
```bash
python scripts/phase2_offline_eval/run_offline_studies.py --T 1000 --n-reps 100 --base-seed 0xD4B40201
```

## 状態
- draft

## 関連リンク
- `docs/フェーズ2/Phase2_MVP仕様書_2026-01-21.md`（τ=1.0, ε=0.10）
- `docs/metrics_definition.md`（PDR/TL/Pout の定義メモ）
- `scripts/phase2_offline_eval/run_offline_eval.py`（単発の動作確認用）

## 更新履歴
- 2026-01-24: 初版（オフライン妥当性/環境シフト/行動集合/ warm-start/ ε-τ感度の最小チェックを追加）

