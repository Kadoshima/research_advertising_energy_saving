# 修論締め TODO（Phase1→Phase2 接続 / オフライン完結）

- 更新日: 2026-01-28
- 状態: draft
- 前提: 追加の実機実験なし。既存ログと既存シミュレーション結果のみで結論を固定する。
- 目的: Phase1→Phase2 の系譜と妥当性を固定し、提案法の優位性をシミュレーションで示して修論を閉じる。

---

## P0) 修論で通る主張を 1 枚に固定する（Claim）

- [ ] TODO P0-1: Claim を 1 枚で固定する
  - 出力: `docs/フェーズ2/phase2_bandit_offline_studies_2026-01-24/claim.md`
  - 含める主張（3点）:
    - Phase1 の評価系（TX/TXSD/RX 同時計測・時刻整合が必須）が成立している
    - Phase2 は Phase1 実測に基づく報酬/制約モデルを使っている
    - 提案法がベースラインより良いトレードオフを示す（Gate A/B/C）
  - KPI 定義: cost, Pout(τ), violation_rate, violations_first_after_switch_k(k=50)
  - Gate A/B/C の勝ち定義（cap 付き Pareto を含む）
  - 参照パスを明記（データとシミュレーション結果）

---

## P1) Phase1→Phase2 の「データ系譜」を表で固定する（Evidence Matrix）

- [ ] TODO P1-1: Evidence Matrix を作成する
  - 出力: `docs/フェーズ2/phase2_bandit_offline_studies_2026-01-24/phase1_to_phase2_provenance.md`
  - 表の列: パラメータ / 数式 / 元データ / 実測根拠（ログ列） / 集約方法 / SHA256
  - 報酬モデル出典:
    - `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv`
    - `results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv`
  - 制約モデル出典:
    - `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_full_scan90_v5.csv`
    - `uccs_d4b_scan90/metrics/01/per_trial.csv`
    - `uccs_d4b_scan70/metrics/01_fixed/per_trial.csv`
    - `data/実験データ/研究室/phase1_e2_fixed_sweep_2026-01-21_v01/manifest.csv`
  - 電力テーブル出典:
    - `results/mhealth_policy_eval/power_table_sleep_eval_2025-12-14_interval_sweep_sleep_on_n9_10.csv`

- [ ] TODO P1-2: Phase1 で「電力/QoS を細かく計測できる」根拠を短文化
  - 参照: `docs/フェーズ1/実験設計書.md`, `docs/フェーズ1/現状整理_2026-01-12.md`
  - 追記先: `phase1_to_phase2_provenance.md`（文章 2 段落以内）

---

## P2) シミュレーション妥当性を過不足なく固定する

- [ ] TODO P2-1: split 妥当性の表を 1 枚にまとめる
  - 出典:
    - `results/phase2_offline_studies_2026-01-25_v02/validity_reward_split.csv`
    - `results/phase2_offline_studies_2026-01-25_v02/validity_constraint_e2_split.csv`
  - 表項目: action, MAE, boundary crossing（safe/unsafe 反転の有無）
  - 追記先: `claim.md` または `phase1_to_phase2_provenance.md`

- [ ] TODO P2-2: 1 pull = 60s の時間解釈を明記する
  - 追記先: `claim.md`, `docs/フェーズ2/phase2_bandit_offline_studies_2026-01-24/現状詳細.md`
  - 影響指標: k=50 を「シフト後 50 分相当」として説明可能にする

---

## P3) Gate A/B/C を最小 3 図 + 3 表に圧縮する

- [ ] TODO P3-1: Gate A（safe が複数）を 1 図 + 1 表に圧縮
  - 出典: `results/phase2_offline_studies_2026-01-25_v03/sim_summary.csv`
  - シナリオ: `E1_actions_100_500_1000_2000_cold`
  - 対象: Oracle / UCB / Safe-UCB / filter_ucb
  - 指標: avg_cost_mean, violation_rate_mean, pull_*（Safe-UCB 張り付きの証拠）

- [ ] TODO P3-2: Gate B（環境シフト）を Pareto 表で固定
  - 出典:
    - `results/phase2_offline_studies_2026-01-26_v05/sim_summary.csv`
    - `results/phase2_offline_studies_2026-01-26_v05/gateb_pareto_cap25.md`
  - 指標: avg_cost_mean, violations_first_after_switch_k_mean(k=50), violations_after_switch_mean
  - 勝ち条件: cap を満たす中で cost 最小（または k=50 最小）

- [ ] TODO P3-3: Gate C（非定常: scan90→scan70）を同じ軸で比較
  - 出典: `results/phase2_gatec_sweep_m_2026-01-26_v02/sim_summary.csv`
  - 指標: avg_cost_mean, violations_first_after_switch_k_mean, violations_after_switch_mean
  - 目的: Gate B と同じ勝ち定義で「追従性」を示す

---

## P4) ドキュメント整合を最後に締める

- [ ] TODO P4-1: README / 考察 / 現状詳細 / TODO の整合を監査する
  - `docs/フェーズ2/phase2_bandit_offline_studies_2026-01-24/README.md`
  - `docs/フェーズ2/phase2_bandit_offline_studies_2026-01-24/考察.md`
  - `docs/フェーズ2/phase2_bandit_offline_studies_2026-01-24/現状詳細.md`
  - `docs/フェーズ2/phase2_bandit_offline_studies_2026-01-24/TODO.md`
  - 指摘: scan90 制約ソースは full-set を明記する

- [ ] TODO P4-2: v04/v04b の扱いを決める（削除はしない）
  - 候補: `results/phase2_offline_studies_archive/` に移動して README に理由を記載
  - 目的: 再現性は残しつつ本文の導線を v05 に集中させる

---

## P5) 修論に入れる最小成果物セットを固定する

- [ ] TODO P5-1: 図 3 枚 + 表 3 つを最小セットとして確定
  - Gate A 図表 / Gate B Pareto / Gate C 追従性
  - 追加: Evidence Matrix（1 ページ）と Threats to Validity（半ページ）

- [ ] TODO P5-2: Threats to Validity を固定する
  - データ駆動シミュレーションであること
  - i.i.d. 近似 / 環境依存残り / n の小さい条件の不安定性
  - 「比較目的には妥当」と明記（過度な担保表現は避ける）

