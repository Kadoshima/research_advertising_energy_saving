# Phase2 修論締め Claim（オフライン完結）

- 作成日: 2026-01-28
- 状態: draft
- 対象: Phase 2 offline studies（Gate A/B/C, v05 まで）
- 前提: 追加の実機実験なし。既存ログと既存シミュレーション結果のみで結論を固定する。

---

## 1. 最終主張（Claim: 3点）

1) Phase1で **電力 + QoS を同一試行で同時計測できる評価系** を構築した。  
   TX/TXSD/RX の三ノード構成で、TXSD は電流電圧系列の集約、RX は時刻/seq/RSSI を保持し、TL/Pout 算出には時刻整合が必須という設計が明文化されている。  
   参照: `docs/フェーズ1/実験設計書.md`, `docs/フェーズ1/現状整理_2026-01-12.md`

2) Phase2 のシミュレーションは、Phase1 実測から作った **経験的な報酬モデル / 制約モデル** を用いている。  
   報酬（電力コスト）は deltaE sweep 由来、制約（Pout）は scan90 固定実験や RX ログ由来であり、Phase1 実測に基づくパラメータである。  
   参照: `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv`, `results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv`, `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_full_scan90_v5.csv`

3) 提案法（Safety Filter + UCB 系）が、既存ベースラインより良い **省電力 vs 違反抑制** のトレードオフを **シミュレーション空間** で示した。  
   Gate A/B/C の比較軸と勝ち定義を固定し、提案法が安全集合内で低コストに近づくこと、環境シフトの序盤違反を抑えること、非定常でも追従可能であることを示す。  
   参照: `results/phase2_offline_studies_2026-01-25_v03/sim_summary.csv`, `results/phase2_offline_studies_2026-01-26_v05/gateb_pareto_cap25.md`, `results/phase2_gatec_sweep_m_2026-01-26_v02/sim_summary.csv`

---

## 2. KPI 定義（固定）

- cost: `per_60s`（mJ/60s）。報酬は `reward = -cost`。  
  参照: `scripts/phase2_offline_eval/models/reward_model.py`
- Pout(τ): `Pr[TL > τ]`。TL は RX ログから算出（時刻整合を含む）。  
  参照: `scripts/phase2_offline_eval/models/constraint_model.py`
- violation_rate: `v`（違反フラグ）の平均。`v` は `constraint_model.sample_violation` の出力（0/1）。  
  参照: `scripts/phase2_offline_eval/run_offline_studies.py`
- violations_first_after_switch_k: 環境シフト後の最初の k ステップの違反数（k=50）。  
  参照: `scripts/phase2_offline_eval/run_offline_studies.py`
- 時間解釈: 1 pull = 60s 相当（DEFAULT_EVENT_PERIOD_MS=60_000）。  
  参照: `scripts/phase2_offline_eval/models/constraint_model.py`

---

## 3. Gate A/B/C の勝ち定義（固定）

### Gate A（safe が複数ある環境で最適化できる）

- シナリオ: `E1_actions_100_500_1000_2000_cold`  
  参照: `results/phase2_offline_studies_2026-01-25_v03/sim_summary.csv`
- 制約: τ=1.0, ε=0.10  
  参照: `docs/フェーズ2/Phase2_MVP仕様書_2026-01-21.md`
- 勝ち定義:
  - violation_rate_mean <= ε
  - avg_cost_mean を最小化（safe 集合内で Oracle-safe に近づく）
  - Safe-UCB は safe_set_empty_rate / pull_* で張り付き傾向を診断する

### Gate B（環境シフトで序盤違反を抑える）

- シナリオ:
  - start shift: `E2_actions_500_1000_2000_warm_shift_from_E1`
  - mid-run shift: `E1_to_E2_actions_500_1000_2000_switch_mid`
- 勝ち定義:
  - warm/mid を worst-case で統合し、`viol_after_worst_mean <= 25` の cap を満たす候補を残す  
    参照: `results/phase2_offline_studies_2026-01-26_v05/gateb_pareto_cap25.md`
  - その中で `violations_first_after_switch_k_mean` と `avg_cost_mean` の Pareto 上位を採用

**Gate B Pareto（cap=25, top candidates）**  
出典: `results/phase2_offline_studies_2026-01-26_v05/gateb_pareto_cap25.md`

| method | m | reset | cost_worst_mean | viol_first_worst_p95 | viol_after_worst_mean | vr_worst_mean |
| --- | --- | --- | --- | --- | --- | --- |
| filter_ucb_online_w0_m0.03_r1 | 0.03 | 1 | 1487.700 | 6.00 | 7.62 | 0.03290 |
| filter_ucb_online_w0_m0.02_r1 | 0.02 | 1 | 1469.804 | 6.05 | 12.70 | 0.03992 |
| filter_ucb_online_w0_m0.01_r1 | 0.01 | 1 | 1426.255 | 7.00 | 24.46 | 0.04661 |

### Gate C（非定常: scan90 -> scan70 の追従性）

- シナリオ: `scan90_to_scan70_actions_100_500_switch_mid`, τ=2.0（診断用）  
  参照: `results/phase2_gatec_sweep_m_2026-01-26_v02/sim_summary.csv`
- 勝ち定義:
  - Gate B と同じ軸（avg_cost_mean / violations_first_after_switch_k / violations_after_switch）で比較
  - m>=0.015 は 100ms 固定へ退化するため除外
  - Gate B と整合する候補として m=0.01 を採用（m=0.005 は診断用）

---

## 4. データ系譜（最小参照）

- 報酬（電力コスト）:
  - `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv`
  - `results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv`
- 制約（Pout / TL）:
  - `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_full_scan90_v5.csv`
  - `uccs_d4b_scan90/metrics/01/per_trial.csv`
  - `uccs_d4b_scan70/metrics/01_fixed/per_trial.csv`
  - `data/実験データ/研究室/phase1_e2_fixed_sweep_2026-01-21_v01/manifest.csv`
- 電力テーブル（補助）:
  - `results/mhealth_policy_eval/power_table_sleep_eval_2025-12-14_interval_sweep_sleep_on_n9_10.csv`

---

## 5. 妥当性の位置付け（言い切り）

### 5.1 split 妥当性（v02）

- 報酬 split（per_60s, MAE）

| action_ms | train_cost_mean | test_cost_mean | mae_test | cost_unit | n_train | n_test |
| --- | --- | --- | --- | --- | --- | --- |
| 100 | 3310.28 | 3475.30 | 1233.41 | mJ_per_60s | 7 | 3 |
| 500 | 1531.87 | 1455.70 | 245.15 | mJ_per_60s | 7 | 3 |
| 1000 | 1065.79 | 1137.89 | 158.32 | mJ_per_60s | 7 | 3 |
| 2000 | 1046.58 | 1122.34 | 75.76 | mJ_per_60s | 7 | 3 |

- 制約 split（E2 fixed, τ=1.0, ε=0.10）

| action_ms | tau_s | pout_train_mean | pout_test_mean | abs_error | pred_safe | actual_safe | n_train | n_test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 500 | 1.0 | 0.000 | 0.000 | 0.000 | True | True | 3 | 2 |
| 1000 | 1.0 | 0.148 | 0.056 | 0.093 | False | True | 3 | 2 |
| 2000 | 1.0 | 0.556 | 0.556 | 0.000 | False | False | 3 | 2 |

- 1000ms では train/test で safe/unsafe が反転しており、境界付近の不確実性を示す。  
  これは margin/online update を入れる設計根拠になる。

- 本シミュレーションは **Phase1 実測に基づくデータ駆動シミュレーション** である。  
  物理モデルの完全再現ではなく、アルゴリズム比較（安全性と省電力のトレードオフ、シフト時の挙動）を評価する目的に対して妥当である。  
  参照: `results/phase2_offline_studies_2026-01-25_v02/validity_reward_split.csv`, `results/phase2_offline_studies_2026-01-25_v02/validity_constraint_e2_split.csv`
