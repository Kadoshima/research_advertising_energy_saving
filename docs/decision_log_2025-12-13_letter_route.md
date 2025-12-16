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

## 生成済み（主張図の固定）
- δ帯の主張図（固定点＋採用候補3点）:
  - `results/mhealth_policy_eval/letter_v1/fig_delta_band.png`
  - 選定点: `results/mhealth_policy_eval/letter_v1/selected_policies.csv`

## 追記（2025-12-13, v5反映後）
- scan90固定メトリクスを v4 → v5 に更新（TL/Poutの時間同期を追加）:
  - v5: `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v5.csv`
  - v4 は開始位相ズレの影響で TL/Pout が歪む可能性があるため、以後は v5 を基準にする（`docs/metrics_definition.md` の「時間同期」参照）。
- v5を用いて、mHealth Pareto sweep を再実行（power table + context mixing）:
  - v6: `results/mhealth_policy_eval/pareto_front_v6_power_table_scan90_v5/pareto_summary.md`
  - 更新点: δ=0.10 が feasible（例: 90/243）となり、従来の「δ=0.12不可/0.13から可」は v4前提の結論として扱う。
- 影響:
  - `results/mhealth_policy_eval/letter_v1/` と `pareto_front_v5_power_table/` は v4前提の図表なので、レター本文に使う場合は v6（scan90 v5反映）で再生成が必要。

## 追記（2025-12-16, 実機D2の主結果はD2b(B)を採用）

- 採用方針:
  - 実機D2は `uccs_d2_scan90/metrics/B/summary.md`（D2b run B）を主結果として採用する。
  - `uccs_d2_scan90/metrics/01/summary.md`（D2 run 01）は **policyの100ms張り付き（CCS定義不整合）**の例としてログに残し、主張には使わない。
- 根拠（D2b run B, mean±std, n=3）:
  - S1:
    - Fixed100: 202.9±0.5 mW / pout_1s=0.0833±0.0289 / TL_mean=4.210±1.540 s
    - Fixed500: 183.3±0.2 mW / pout_1s=0.1500±0.0500 / TL_mean=5.296±0.019 s
    - Policy: 189.8±0.4 mW / pout_1s=0.1167±0.0289 / TL_mean=5.247±0.053 s / share100≈0.332
  - S4:
    - Fixed100: 202.5±0.4 mW / pout_1s=0.0569±0.0141 / TL_mean=1.247±0.010 s
    - Fixed500: 183.2±0.3 mW / pout_1s=0.1545±0.0373 / TL_mean=2.166±0.870 s
    - Policy: 195.2±0.4 mW / pout_1s=0.0813±0.0373 / TL_mean=1.588±0.582 s / share100≈0.592
- 言えること（論文主張の形）:
  - **Fixed100より省電力**かつ **Fixed500よりQoS良**（pout/TL）という「程よい点」が実機で成立した（S1/S4とも）。
  - 遷移が多い側（S4）ほど share100 が増えるため、**“必要時だけ100msに寄せる”**がデータ上で確認できる。
  - 電力は fixed100/fixed500 の線形混合で説明できる（支配要因が interval 滞在比率であることの裏付け）。
- 補足（D2→D2bの修正理由）:
  - D2の `stress_causal_*` は CCS が「変化量」ではなく「安定度（高いほどstable）」のため、そのまま使うと判定が逆になり100ms張り付きになり得る。
  - D2bで `CCS_change = 1-CCS` として定義整合を取った。

## 追記（2025-12-16, D2b主結果を統合n=6へ更新）

- run B（n=3）+ 追加取得 B/02（n=3）を統合し，`uccs_d2_scan90/metrics/B_n6/`（各条件n=6）を論文・図表の主結果として採用する。
- 根拠（D2b, mean±std, n=6）:
  - S1_policy: 191.5±1.9 mW / pout_1s=0.1250±0.0274 / TL_mean=5.239±0.049 s / share100≈0.331
  - S4_policy: 196.6±1.6 mW / pout_1s=0.0691±0.0285 / TL_mean=1.575±0.500 s / share100≈0.595
- 出力:
  - 集計: `uccs_d2_scan90/metrics/B_n6/summary.md`（CSV: `uccs_d2_scan90/metrics/B_n6/summary_by_condition.csv`）
  - 図: `uccs_d2_scan90/plots/d2b_B_n6_power_vs_pout.pdf`
- 備考: n増加後も「Fixed100より省電力・Fixed500よりQoS良（pout/TL）」が成立しているため，主張の形は維持できる。

## 追記（2025-12-16, D4→D3の追加実験を採用）

- 目的: 実機D2bの「程よい点」が **U（不確実度）**に依存しているか（新規性）と、環境変化に対して崩れにくいか（実用性）を最小本数で補強する。
- 決定: **D4（U ablation）→D3（scan dutyを1段下げる）**の順で実施する。
  - D4は「Uが効く/効かない」を短時間・低リスクで言い切れるため先行する。
  - D3は環境要因が絡むため後段（D4で主張の芯を固めてから）に回す。
- D4（S4のみ、scan90）:
  - 条件: Fixed100 / Fixed500 / Policy(U+CCS) / Ablation(U-shuffle) の4条件×n=3
  - Ablationは **U-shuffle**（Uの分布は同じ・時間相関のみ破壊）を採用する。
  - 実装/取得ディレクトリ: `uccs_d4_scan90/`（TX/RX/TXSD + 集計スクリプト）
- D3（S4のみ）:
  - scan duty を 90% → 70% or 60% に落とし、Fixed500が崩れる帯で Policy が耐えるかを確認する。
  - 条件: Fixed100 / Fixed500 / Policy の3条件×n=3（最小）。
