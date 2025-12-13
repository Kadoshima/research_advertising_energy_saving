# decision_log_2025-12-13_letter_route

- 日付: 2025-12-13
- 目的: レター投稿を最速で成立させるため、「新規性」と「実装/実験リスク」を比較してルートを確定する。

## 前提（いま揃っているもの）
- 実機固定（Mode C2′, scan90%）: `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v4.csv`
- オフライン（mHealth合成 + U/CCS）: `results/mhealth_policy_eval/`（policy table / Pareto sweep / context mixing）
- 電力テーブル（固定interval）: `results/mhealth_policy_eval/power_table_sleep_eval_2025-12-13.csv`
  - 生成元: `sleep_eval_scan90/metrics/on_off_test_100~2000/txsd_power_summary.csv`（TXSD mean_p_mW, n=2）

## 候補ルート（TODOとの比較）

### ルートA（docs/TODO.mdの主線）
- P0: TL/Pout定義の固定 → scan90固定フルセット図表化（実測vsシミュ説明）
- P1: CCS_causal を実機で取得（S1/S4）→ 固定と比較
- P2: self-UCB（不確実性駆動）をシミュで設計

**長所**
- 既存のMode C2′資産（S1/S4、scan90、解析パイプライン）に直結していてブレが少ない。

**短所（新規性）**
- CCS_causal が「HAR不確実度（U）そのもの」から少し遠く、レターの主張を「不確実性駆動」に寄せにくい。

### ルートB（今回の流れ: U/CCS→interval のオフライン最適化を主線にする）
- mHealth合成から得た U/CCS ログに対して、閾値ルール（ヒステリシス）を評価。
- scan90固定（S1/S4）メトリクスで QoS を、sleep_eval の power table で電力を合成し、Paretoを提示。
- Safe-MABは「Future Work」または「オフライン1図」までに留める。

**長所（新規性×最速）**
- 「HARの不確実度に基づく通信制御」をPhase1（ルールベース）で主張できる。
- power table を入れることで「share100を減らすと電力が下がる」を定量で示せる。

**短所（リスク）**
- 実機の“動的切替そのもの”の実証が薄いと突っ込まれる可能性がある。
  - 対策: 実機は最小セット（固定 + 2値制御）で「切替が成立する」だけ確認し、主結果はオフライン合成で示す。

## 評価（新規性の観点）
レター（Phase 1）の主張は `docs/全体像.md` のとおり「決め打ちルールで固定より良い」を示すこと。
ここでの差は「CCS（擬似安定度）」中心か、「U（不確実度）」中心か。

- 新規性を立てやすいのはルートB（U/CCSを明示できる）。
- ただし、論文化の安全性（再現性・測定系の説明容易性）はルートAの資産を活かす方が高い。

## 決定（Best / Fast）
**ルートBを主線**にして、TODOのP0（指標定義・図表化）は並行で必ず踏む。

具体的には：
1) **P0（必須）**: TL/Poutの真値定義を固定し、scan90固定の図表を整える（ここはTODO準拠）。
2) **Phase1主結果**: U/CCS→interval（ルールベース）を、scan90 QoS + power table でオフライン評価し、Pareto（pout_1s vs avg_power）を提示。
3) **実機は最小**: 動的切替の動作確認は「100↔500（2値）」で最小本数のみ（固定100/500/2000と合わせて比較、nは小さくてよい）。
4) **Safe-MAB**: レターでは Future Work（またはオフライン1図）に留める。

## 直近の根拠データ（境界条件の確定）
- power table（sleep_eval, n=2）:
  - 100ms: 201.45 mW
  - 500ms: 182.95 mW
  - 1000ms: 180.50 mW
  - 2000ms: 179.75 mW
  - 重要: 電力低下の主効果は「100→500」で、500→2000は小さい。
- Pareto v5（power_table反映 + context mixing）:
  - `results/mhealth_policy_eval/pareto_front_v5_power_table/pareto_summary.md`
  - δ=0.12 は feasible=0、δ=0.13 は feasible>0（境界が 0.12〜0.13 にある）。

## 次アクション（この順で進める）
- A1: `scripts/analyze_stress_causal_real.py` のTL/Pout真値定義を再確認し、`docs/metrics_definition.md` と整合させる（TODO P0）。
- B1: `results/mhealth_policy_eval/pareto_front_v5_power_table/` を主結果候補として固定（図・表の整理）。
- B2: レター用に action を {100,500}（2値）へ縮退した評価を追加（説明簡単・電力の主効果に一致）。
- C1: 実機（動的切替）を最小セットで確認（Fixed 100/500/2000 + 2値制御、各n=1〜3）。

