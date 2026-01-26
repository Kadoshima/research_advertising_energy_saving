# Phase 2 offline studies: TODO / Gate 設計（2026-01-26）

- 更新日: 2026-01-26
- 状態: draft
- 対象: `scripts/phase2_offline_eval/`（bandit導入前のオフライン検証）
- 関連:
  - 現状詳細: `docs/フェーズ2/phase2_bandit_offline_studies_2026-01-24/現状詳細.md`
  - 考察: `docs/フェーズ2/phase2_bandit_offline_studies_2026-01-24/考察.md`
  - v02 出力: `results/phase2_offline_studies_2026-01-25_v02/`
  - v03 出力: `results/phase2_offline_studies_2026-01-25_v03/`
  - v04 出力: `results/phase2_offline_studies_2026-01-26_v04/`

本TODOは、現状の Phase 2 offline studies（v03まで）を「次フェーズへ進んでよいことの証明（gate）」へ変えるための、最短で効く順番に並べ替えた計画である。

---

## 0) いま何が言えるか（v02/v03の到達点）

2026-01-25 時点で、以下は **再現可能に示せている**（出典: `results/phase2_offline_studies_2026-01-25_v02/`）。

- **報酬定義で bandit の挙動が変わる**（per_adv では差が出にくいが、per_60s では差が出る）。
- **UCB が省電力側（長間隔）に寄って制約を破り、Safe-UCB で抑えられる**。
  - 例: E2 cold で UCB violation_rate_mean≈0.48、Safe-UCB≈0.00069（出典: `results/phase2_offline_studies_2026-01-25_v02/sim_summary.csv`）。

ここまでは「正しい方向の最小構成」だが、gateとしては弱い点が残っている（次節）。

v03 では gate を強くするために、以下を追加した（出典: `results/phase2_offline_studies_2026-01-25_v03/`）。
- Safe-UCB の診断指標（safe_set_empty_rate, pull_*）を追加し、「学習している/していない」を可視化できるようにした。
- `filter_ucb`（Safety Filter + UCB）を追加し、safe が複数ある環境（Gate A）と環境シフト（Gate B）を再現しやすくした。

v04 では Gate B を「抑え方込み」で比較できるように、`filter_ucb_online`（オンライン更新の Safety Filter + UCB）と、序盤違反メトリクス `violations_first_after_switch_k`（k=50）を追加した（出典: `results/phase2_offline_studies_2026-01-26_v04/`）。

---

## 1) 最優先で疑うべき前提: Safe-UCB が「学習」していない可能性

### 1.1 観測: v02 の Safe-UCB 違反率が「初期探索の違反」だけで説明できる

E2_fixed_v01 の Pout(1s) は、1000ms=0.111..., 2000ms=0.555...（出典: `results/phase2_offline_studies_2026-01-25_v02/tradeoff_table.csv`）。

Safe-UCB の実装は初期に各腕を1回ずつ引く（出典: `scripts/phase2_offline_eval/models/safe_ucb.py`）。
このとき 1000/2000 を各1回引く期待違反回数は:

- 0.111... + 0.555... = 0.666...
- T=1000 で割ると 0.000666...

実測の violation_rate_mean≈0.00069（出典: `results/phase2_offline_studies_2026-01-25_v02/sim_summary.csv`）と整合し、**初期ラウンドロビン後は常に 500ms に張り付いている**可能性が高い。

### 1.2 原因候補: safe_set 判定が「空になりやすい」ため、フォールバック装置化している

現状実装の safe_set 判定は以下（出典: `scripts/phase2_offline_eval/models/safe_ucb.py`）。

- mean_constraint + sqrt(2 log t / n) <= epsilon

仮に mean_constraint=0（違反が観測されない安全腕）でも、t=1000 では 2 log t ≈ 13.8 なので、

- sqrt(13.8 / n) <= 0.10（epsilon=0.10）を満たすには n >= 1380 が必要

Horizon T=1000 では到達不能で、safe_set が空→フォールバックで min(action) を選ぶ挙動になりやすい。

結論:
- 現状の Safe-UCB は「安全側フォールバック装置」としては動いているが、**bandit（最適化器）としては動いていない**可能性がある。
- このまま実機コンテキスト化へ進むと、Phase2（学習導入）が形骸化しやすい。

---

## 2) 最短で効く順番（P0→P2）

### P0: Safe bandit が学習できる土台を作る（最優先）

- [x] **制約の信頼区間（上側CI）を現実的に収束する形へ変更（オプション化）**
  - 目的: safe_set が「空→フォールバック」になり続ける状態を脱する
  - 候補（実装コスト低）:
    - (A) 時刻t依存をやめ、固定δの上側CIへ
      - 例: Hoeffding: U_g = mean + sqrt( ln(1/δ) / (2n) )
      - 追加パラメータ δ は、凍結仕様（`docs/TODO.md`）と整合する形で別途決める（推測で固定しない）
    - (B) Bernoulli 前提の上側区間
      - Clopper-Pearson / Beta posterior quantile（Poutは確率のため筋が良い）
  - 対象コード:
    - `scripts/phase2_offline_eval/models/safe_ucb.py`（safe_set 判定）
    - （必要なら）`scripts/phase2_offline_eval/models/constraint_model.py`（confidence の定義）

- [x] **初期探索（round-robin）を安全設計に合わせて変更（オプション化）**
  - 目的: 実機投入時の「最初から安全要件違反」を避ける（offlineでも同作法に寄せる）
  - 方針案:
    - baseline safe arm（例: 500ms）から開始
    - 他腕は「安全と言える条件（上側CI<=ε）」を満たすまで探索しない
    - 実装上は Safety Filter（Action Masking）として外側に分離してもよい
  - 対象コード:
    - `scripts/phase2_offline_eval/models/safe_ucb.py`（初期挙動）

- [x] **診断用メトリクスを出力する（gateの証拠）**
  - 例: safe_set_empty_rate, safe_set_size 推移、行動選択比率（収束先の可視化）
  - 対象コード:
    - `scripts/phase2_offline_eval/run_offline_studies.py`（CSV列追加）

- [ ] （低優先）報酬側の探索項に std を反映して仕様書と整合を取る
  - 目的: `docs/フェーズ2/Phase2_MVP仕様書_2026-01-21.md` の擬似コード（sigma_r を使う）へ寄せる
  - 対象コード:
    - `scripts/phase2_offline_eval/models/safe_ucb.py`

### P1: Safe bandit の価値が出るシナリオ（safeが複数）で gate を作る

- [x] **E1_scan90_stress_v5 で actions={100,500,1000,2000} のシナリオを追加**
  - 目的: safe arm が複数ある環境で「安全の中で省電力最適」をできるか確認する（Gate A）
  - 根拠: ε=0.10 なら 100/500/1000 が safe、2000 が unsafe になり得る（出典: `results/phase2_offline_studies_2026-01-25_v03/epsilon_tau_sensitivity.csv` の E1_scan90_stress_v5 行）
  - 対象コード:
    - `scripts/phase2_offline_eval/run_offline_studies.py`（scenario追加）

- [x] **E2 は診断用に τ=2.0 を許容して safe が2点以上になる条件でテスト**
  - 目的: 「Safe bandit が安全集合内で選好を変える」こと自体を確認する（仕様変更ではなく健全性テスト）
  - 根拠: E2_fixed_v01 では ε=0.10 のとき 1000ms が tau=2.0 なら safe になり得る（出典: `results/phase2_offline_studies_2026-01-25_v03/epsilon_tau_sensitivity.csv` の E2_fixed_v01 行）

### P2: warm-start を「本当に危ない条件」でテストする（Gate B）

- [x] **E1→E2 の環境シフトで「序盤違反が出る条件」を作る**
  - 狙い:
    - prior 環境では 1000ms が safe に見える
    - target（E2）では 1000ms が ε を跨ぐ/境界付近（v02では mean=0.111...）
    - warm-start により 1000ms を早期に選び、違反が出る
    - Safety Filter / 保守マージン / 初期探索設計で「違反バーストを抑えられる」ことを示す
  - 対象コード:
    - `scripts/phase2_offline_eval/run_offline_studies.py`（prior/target設計、メトリクス）
  - 出典:
    - `results/phase2_offline_studies_2026-01-26_v04/sim_summary.csv`
    - 例（E2 warm shift）: filter_ucb violation_rate_mean=0.11264 -> filter_ucb_online_w0_m0.03_r0 0.00762

- [x] **E1_scan90 の制約ソースを per-trial に切替（warm-start破綻を出しやすく）**
  - 目的: prior 側の推定分散を持たせ、境界越え/誤判定が起きる状況を作る
  - 候補ソース:
    - `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_full_scan90_v5.csv`

---

## 3) 報酬の扱い（結論）

- 主タスク（学習・評価）は **per_time 系（per_60s 等）に統一**する。
- per_adv は「計測系の健全性チェック」など副用途に格下げする（差が出ないのは自然）。
- 対象コード:
  - `scripts/phase2_offline_eval/models/reward_model.py`（既に reward_mode 対応済み）

---

## 4) 実機へ繋ぐ最小設計（提案）

実機投入を安全にするには「いきなり置き換えない」構成が強い。

- 二層構造（推奨）
  - 外側: Safety Filter（Action Masking）で「絶対に選べない行動」を落とす
  - 内側: 通常 bandit（UCB/TS 等）で省電力最適化に集中

メモ:
- Safe-UCB 一発で完結させるより、Safety Filter + bandit の方が説明が簡単で壊れにくい可能性がある（採用は要検討）。

---

## 5) 次の gate（3つに絞る）

### Gate A: safe が複数ある環境で「安全の中で」最適へ寄れる

- 環境: E1_scan90_stress_v5
- 行動: {100,500,1000,2000}
- 報酬: per_60s（mJ/60s）
- 制約: tau=1.0, epsilon=0.10
- 確認観点（pass/fail の判定軸）:
  - violation_rate が epsilon を超えない（保守マージン込みの評価は別途設計）
  - 最頻値が「最も省電力な safe（例: 1000ms）」へ寄る（=学習の実体）
  - avg_cost が baseline safe（500ms）より改善する

### Gate B: warm-start が壊れる条件で、壊れ方を制御できる

- prior(E1) -> target(E2) で序盤違反が出る条件を作る
- 確認観点:
  - violations_first_100 が warm-start で増えることを再現
  - Safety Filter / 初期探索設計で「違反バーストを抑えられる」ことを定量化

### Gate C: 非定常っぽさへの耐性（最低限）

- シミュ途中で Pout テーブルを切替（env switch）などを入れ、追従性を確認する
- 確認観点:
  - env switch 後に violation_rate が跳ねた後、許容範囲へ戻れるか
  - safe_set_empty_rate が高止まりしないか
- 2026-01-26: tau=2.0（追従性診断）で scan90->scan70 の候補チェックを実行
  - 出典: `results/phase2_gatec_sweep_m_2026-01-26_v02/sim_summary.csv`
  - 観測:
    - m>=0.015 は 100ms 固定になり省電力観点で不利（action={100,500}のとき）
    - m=0.005/0.01 は 500ms を維持しつつ shift 後に一部 100ms へ退避（QoS寄りに倒せる領域がある）
  - 次: Gate B 側の候補定義（cap付き）と統合し、m を 0.005-0.01 近傍で一本化できるか検討

---

## 6) 作業メモ（このTODOの位置付け）

- 本TODOは「次の実機コンテキスト化（CCS導入）へ進む前の gate」を明確化するためのもの。
- 以降の実装・出力は、同ディレクトリの README と worklog に追記して残す。
