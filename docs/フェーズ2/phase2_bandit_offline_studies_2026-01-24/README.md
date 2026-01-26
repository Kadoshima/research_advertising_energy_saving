# Phase 2: Bandit Offline Studies (2026-01-24 v01, 2026-01-25 v02/v03, 2026-01-26 v04/v05)

## 目的/範囲
- Safe Contextual Bandit（Safe-UCB）導入前に、報酬/制約推定の妥当性と環境シフト耐性をオフラインで確認する。
- 対象は **非コンテキスト（context固定）** の最小構成（行動=広告間隔、制約=Pout(τ)）とする。



## 結論（Gate B/C）
- 手続き: Gate B（環境シフト）で warm/mid の worst-case を統合し、`viol_after_worst_mean <= 25` の cap を入れて候補抽出（`results/phase2_offline_studies_2026-01-26_v05/gateb_pareto_cap25.md`）。
- 診断: Gate C（非定常診断）で m sweep を行い、m>=0.015 が 100ms 固定へ退化することを確認した（`results/phase2_gatec_sweep_m_2026-01-26_v02/sim_summary.csv`）。
- 結論: w=0, reset=1, m=0.01 を暫定 default とし、m=0.02/0.03 を安全寄り感度分析として併記する。

## 入力データ（出所/版/行数/SHA256）
- 報酬モデル（ΔE sweep, μC推定）
  - `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv`（2026-01-21, rows=17, sha256=6dd0e80acaba7b452b02f3e096a613cbf8167deab36396f31d6d777cc835126d）
  - `results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv`（2026-01-21, rows=50, sha256=89521ce5289a0050fb583004423132aab3efaa75a8ddcb87a97c987ef8fc65b9）
- 制約モデル（E1 scan90 full-set）
  - `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_full_scan90_v5.csv`（rows=8, sha256=009cbbb719ab9199b7f56c86f378c8d42022fe7171d498be23001f85e4e151e6）
- 制約モデル（E1 scan90/scan70, {100,500}）
  - `uccs_d4b_scan90/metrics/01/per_trial.csv`（rows=12, sha256=98e60a62e3d4be48c051d05843d33608258d9d91a49bd639d7fdbc2df8cdc598）
  - `uccs_d4b_scan70/metrics/01_fixed/per_trial.csv`（rows=12, sha256=9809fbe0d36130d34a80bc50682ec48fa07396f106402ed0cfc358e64e204832）
- 制約モデル（E2 fixed sweep, RXログ由来）
  - `data/実験データ/研究室/phase1_e2_fixed_sweep_2026-01-21_v01/manifest.csv`（rows=34, sha256=fd5ca19a268c93aa52f6218d520b84680638e8787823d7d5e9a4ccc078230f88）

## 出力物（生成日/生成スクリプト）
- 生成日: 2026-01-24 (v01), 2026-01-25 (v02/v03)
- 生成スクリプト: `scripts/phase2_offline_eval/run_offline_studies.py`
- v01: `results/phase2_offline_studies_2026-01-24_v01/`
  - reward_mode: `per_adv`（μC=[μJ/adv]）
  - `tradeoff_table.csv`: env×action のコスト（μC）と Pout(1s/2s)
  - `epsilon_tau_sensitivity.csv`: (ε,τ) に対する safe/unsafe
  - `validity_reward_split.csv`: 報酬モデルの train/test 分割チェック
  - `validity_constraint_e2_split.csv`: 制約（E2 fixed）train/test 分割チェック
  - `sim_replicates.csv`: シミュレーション各反復の指標
  - `sim_summary.csv`: 集計（mean/std）
- v02: `results/phase2_offline_studies_2026-01-25_v02/`
  - reward_mode: `per_60s`（ΔE_total=[mJ/60s]）
  - `tradeoff_table.csv`: env×action の cost_mean/cost_std と Pout(1s/2s)
  - `epsilon_tau_sensitivity.csv`: (ε,τ) に対する safe/unsafe
  - `validity_reward_split.csv`: 報酬モデルの train/test 分割チェック
  - `validity_constraint_e2_split.csv`: 制約（E2 fixed）train/test 分割チェック
  - `sim_replicates.csv`: シミュレーション各反復の指標
  - `sim_summary.csv`: 集計（mean/std）
- v03: `results/phase2_offline_studies_2026-01-25_v03/`
  - reward_mode: `per_60s`（ΔE_total=[mJ/60s]）
  - Safe-UCB: `constraint_ci=hoeffding`, `delta=0.05`, `init_strategy=safe_seed`
  - `filter_ucb`（Safety Filter + UCB）を追加し、Gate A/B/C 用のシナリオを追加
  - `sim_summary.csv`: 診断指標（safe_set_empty_rate等）と行動選択比（pull_*）を追加
- v04: `results/phase2_offline_studies_2026-01-26_v04/`
  - reward_mode: `per_60s`（ΔE_total=[mJ/60s]）
  - Safe-UCB: `constraint_ci=wilson`, `delta=0.05`, `init_strategy=safe_seed`
  - `filter_ucb_online`（オンライン更新の Safety Filter + UCB）を追加し、Gate B を「抑え方込み」で比較可能にした
    - sweep: `prior_weight w` / `margin m` / `reset_on_switch`
    - 指標: `violations_first_after_switch_k`（デフォルト k=50）を追加
- v05: `results/phase2_offline_studies_2026-01-26_v05/`
  - v04 をベースに、Gate C から得た候補（mの細粒度）を Gate B に戻して再評価するために、m を追加して再実行
  - Gate B の候補絞り込み（cap付きPareto）:
    - `scripts/phase2_offline_eval/analyze_gateb_pareto.py`
    - `results/phase2_offline_studies_2026-01-26_v05/gateb_pareto_cap25.md`

## 再現手順（コマンド）
```bash
# NOTE: v01 は 2026-01-24 時点のスナップショットで、後続の reward_mode 対応により
# CSVの列名（スキーマ）が変わっています。値の再生成は以下で可能です（上書き注意）。
python scripts/phase2_offline_eval/run_offline_studies.py --reward-mode per_adv --T 1000 --n-reps 100 --base-seed 0xD4B40201 --out-dir results/phase2_offline_studies_2026-01-24_v01

# v02 (reward_mode=per_60s)
python scripts/phase2_offline_eval/run_offline_studies.py --reward-mode per_60s --T 1000 --n-reps 100 --base-seed 0xD4B40201 --out-dir results/phase2_offline_studies_2026-01-25_v02

# v03 (reward_mode=per_60s, Safe-UCB CI/init を変更 + filter_ucb + Gateシナリオ追加)
python scripts/phase2_offline_eval/run_offline_studies.py --reward-mode per_60s --constraint-ci hoeffding --constraint-delta 0.05 --init-strategy safe_seed --T 1000 --n-reps 100 --base-seed 0xD4B40201 --out-dir results/phase2_offline_studies_2026-01-25_v03

# v04 (Gate B: 抑え方込みで比較, filter_ucb_online + violations_first_after_switch_k)
python scripts/phase2_offline_eval/run_offline_studies.py --reward-mode per_60s --constraint-ci wilson --constraint-delta 0.05 --init-strategy safe_seed --T 1000 --n-reps 100 --base-seed 0xD4B40201 --out-dir results/phase2_offline_studies_2026-01-26_v04

# v05 (Gate B: w=0 に絞り、m を細粒度に追加して再実行)
python scripts/phase2_offline_eval/run_offline_studies.py --reward-mode per_60s --constraint-ci wilson --constraint-delta 0.05 --init-strategy safe_seed --T 1000 --n-reps 100 --base-seed 0xD4B40201 --gateb-prior-weights 0 --gateb-margins 0,0.005,0.01,0.015,0.02,0.03 --gateb-reset-on-switch 1 --out-dir results/phase2_offline_studies_2026-01-26_v05

# Gate B Pareto (cap付き候補圧縮)
python scripts/phase2_offline_eval/analyze_gateb_pareto.py --run-dir results/phase2_offline_studies_2026-01-26_v05 --epsilon 0.10 --max-viol-after-worst-mean 25 --out-candidates results/phase2_offline_studies_2026-01-26_v05/gateb_candidates_cap25.csv --out-pareto results/phase2_offline_studies_2026-01-26_v05/gateb_pareto_front_cap25.csv --out-md results/phase2_offline_studies_2026-01-26_v05/gateb_pareto_cap25.md

# Gate C（候補だけで確認 / mの細粒度スイープ）
python scripts/phase2_offline_eval/run_gatec_candidates.py --gateb-run-dir results/phase2_offline_studies_2026-01-26_v05 --m-list 0,0.005,0.01,0.015,0.02 --w 0 --reset 1 --tau-s 2.0 --epsilon 0.10 --T 1000 --n-reps 100 --base-seed 0xD4B40201 --out-dir results/phase2_gatec_sweep_m_2026-01-26_v02
```

## 状態
- draft

## 関連リンク
- `docs/フェーズ2/Phase2_MVP仕様書_2026-01-21.md`（τ=1.0, ε=0.10）
- `docs/metrics_definition.md`（PDR/TL/Pout の定義メモ）
- `scripts/phase2_offline_eval/run_offline_eval.py`（単発の動作確認用）
- `docs/フェーズ2/phase2_bandit_offline_studies_2026-01-24/現状詳細.md`（現状の実装・データ・結果の詳細）
- `docs/フェーズ2/phase2_bandit_offline_studies_2026-01-24/TODO.md`（gate設計と優先度付きTODO）

## 更新履歴
- 2026-01-24: 初版（オフライン妥当性/環境シフト/行動集合/ warm-start/ ε-τ感度の最小チェックを追加）
- 2026-01-25: reward_mode切替（μJ/adv と mJ/60s）を追加し、mJ/60s で v02 を実行
- 2026-01-25: gate設計（Safe-UCBが学習器として成立する条件、Gate A/B/C）を `TODO.md`/`考察.md` に反映
- 2026-01-25: v03（CI/初期探索のオプション化、filter_ucb追加、Gate A/B/C シナリオ追加）を実行し結果を保存
- 2026-01-26: v04（filter_ucb_online追加、Gate B の抑え方 sweep と序盤違反メトリクス追加）を実行し結果を保存
- 2026-01-26: v05（Gate B の候補定義に cap を入れるために、m を細粒度追加して再実行；Gate C で候補を確認）を実行
