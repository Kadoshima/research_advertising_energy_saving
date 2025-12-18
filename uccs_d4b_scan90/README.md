# uccs_d4b_scan90（Step D4B: CCSが効いている切り分け / Ablation）

## 目的

Step D4で「Uを壊す（U-shuffle）と100ms張り付き寄りに崩れる」を示した。次にレターで突っ込まれやすい
「CCSは要るのか？ Uだけで十分では？」へ答えるため、**CCSを無効化したU-only**を追加して切り分ける。

* 対象セッション: **S4のみ**（差が出やすい）
* 条件: 4条件 × n=3（最小セット）
  1. Fixed100
  2. Fixed500
  3. Policy（U+CCS, 100↔500）
  4. Ablation（CCS-off = **U-only**, 100↔500）

## 真値（truth）

* `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv`（100msグリッド, n_steps=1800=180s）
* TXは上記CSV由来の `label/U/CCS` をフラッシュに埋め込み、同一セッションを再生する。

## スケッチ（Arduino IDE 用）

* TX: `uccs_d4b_scan90/src/tx/TX_UCCS_D4B_SCAN90/TX_UCCS_D4B_SCAN90.ino`
* RX: `uccs_d4b_scan90/src/rx/RX_UCCS_D4B_SCAN90/RX_UCCS_D4B_SCAN90.ino`
* TXSD: `uccs_d4b_scan90/src/txsd/TXSD_UCCS_D4B_SCAN90/TXSD_UCCS_D4B_SCAN90.ino`

## 配線

* TX `GPIO25 (SYNC_OUT)` → RX `GPIO26 (SYNC_IN)` / TXSD `GPIO26 (SYNC_IN)`
* TX `GPIO27 (TICK_OUT)` → TXSD `GPIO33 (TICK_IN)`

## 実行

* 1回の起動で S4 × 4条件を自動実行（`REPEAT=3`）。
* trial長: 180s（`EFFECTIVE_LEN_STEPS=1800`）。

## TX payload仕様（ManufacturerData）

形式: `<step_idx>_<tag>`

* `step_idx`: 100msグリッドの整数（0..）
* `tag`: `F4-<label>-<itv>` / `P4-<label>-<itv>` / `U4-<label>-<itv>`
  * `F`: fixed, `P`: policy(U+CCS), `U`: U-only（CCS-off）
  * `<label>`: truth label（2桁）
  * `<itv>`: current interval（100 or 500）

## TXSD cond_id（preamble TICKパルス数）

* 1: S4 fixed100
* 2: S4 fixed500
* 3: S4 policy
* 4: S4 ablation_ccs_off（U-only）

trial中は「広告更新」ごとにTICKを1発出し、TXSD側で `adv_count=tick_count` を記録する（近似）。

## データ配置

* SDから吸い上げた `/logs/` を `uccs_d4b_scan90/data/<run>/{RX,TX}/` にコピーする（TX=TXSDログ）。
* `uccs_d4b_scan90/data/<run>/README.md` に測定条件をメモ。

## 解析

* 集計スクリプト: `uccs_d4b_scan90/analysis/summarize_d4b_run_v2.py`
  * 入力: `--rx-dir .../RX --txsd-dir .../TX`
  * 出力: `per_trial.csv`, `summary_by_condition.csv`, `summary.md`
  * 注意: SDコピーでmtimeが壊れる/cond_idがズレることがあるため、TXSDは **adv_count（tick_count）でクラスタリング**して割り当てる（古いログ混在/逆符号はフィルタで除外）。

* 図（任意）: `uccs_d4b_scan90/analysis/plot_power_vs_pout.py`
  * 入力: `--summary-csv uccs_d4b_scan90/metrics/<run>/summary_by_condition.csv`
  * 出力: `uccs_d4b_scan90/plots/d4b_<run>_power_vs_pout.svg`（matplotlibが無い環境ではSVGを生成）

## 結果（run01）

- 集計: `uccs_d4b_scan90/metrics/01/summary.md`
- 図: `uccs_d4b_scan90/plots/d4b_01_power_vs_pout.svg`
  - 統合図（D3/D4/D4B）: `uccs_d4b_scan90/plots/role_separation_d3_d4_d4b.svg`
  - 同mixの証拠（adv_count/α_adv表）: `uccs_d4b_scan90/plots/adv_count_alpha_table.md`
  - Outage TOP-k（scan90 vs scan70, selected trials）: `uccs_d4b_scan90/plots/outage_topk_scan90_scan70_selected.md`
  - α正規化図（runごとのfixed100/500で正規化）: `uccs_d4b_scan90/plots/alpha_vs_pout_overview.svg`
  - 失敗イベント中心のストーリー図（TL>1sを生んだ少数イベントの追跡）: `uccs_d4b_scan90/plots/outage_story_01/fig_outage_timeline.svg`
    - selected trials版: `uccs_d4b_scan90/plots/outage_story_01_selected/fig_outage_timeline.svg`
  - Poutの寄与分解（上位少数遷移が支配することの可視化）: `uccs_d4b_scan90/plots/pout_tail_01/`
  - 条件付きタイミング（失敗しやすい遷移だけに条件付け）: `uccs_d4b_scan90/plots/ccs_timing_conditional_01/fig_event_triggered_p100_conditional.svg`
  - 追加解析（CCSタイミング可視化）: `uccs_d4b_scan90/plots/ccs_timing_01/`
    - `fig_event_triggered_p100.svg`（truth遷移中心のP(100ms)）
    - `fig_lag_cdf.svg`（遷移→100msへのlag CDF）
    - `fig_hit_cover.svg`（Hit/PreHit/Coverの棒グラフ）
    - `alloc_efficiency_summary.csv`（100ms割当の“効率”指標）
  - 主図（scan70/scan90を同一座標に統合）: `uccs_d4b_scan90/plots/mainfig_scan70_scan90.svg`

### 主要な結論（S4のみ, mean±std, n=3）

同じ2値（100↔500）で **電力/100ms滞在（share100）がほぼ同等**のまま、CCSを有効にした `Policy(U+CCS)` の方が `U-only(CCS-off)` よりQoSが改善した。

- `S4_policy(U+CCS)`:
  - `avg_power_mW = 200.6±0.1`, `pout_1s = 0.0488±0.0000`, `share100_power_mix≈0.620`
- `S4_ablation_ccs_off(U-only)`:
  - `avg_power_mW = 200.6±0.2`, `pout_1s = 0.0650±0.0141`, `share100_power_mix≈0.621`

→ **Uは100ms滞在（電力）を決め、CCSは同じ電力の範囲でQoS（pout/TL）を改善する**、という「U/CCSの2本立て設計」の正当化に使える。

### レター用の言い切り（D4B単体）

`Policy(U+CCS)` と `U-only(CCS-off)` は **平均電力がほぼ同一**なのに、`Policy(U+CCS)` が **QoSを改善**している。

- 平均電力: `200.626 mW` vs `200.649 mW`（差 `-0.023 mW`）
- `adv_count`: `1215` vs `1227`（100/500のmixもほぼ同等）
- QoS改善（同電力での改善）:
  - `pout_1s`: `0.0650 → 0.0488`（絶対 `-0.0163`, 相対 `-25%`）
  - `tl_mean_s`: `1.407 → 1.317`（約 `-0.089 s`, 相対 `-6.3%`）
  - `pdr_unique`: `0.434 → 0.448`（小さいが改善）

→ **CCSは「100msを増やす」ことでなく、“同じ100ms予算の使い方（タイミング）”でQoSを下げる**と解釈できる。

#### 備考（追加解析の読み）

`uccs_d4b_scan90/plots/ccs_timing_01/` では、truth遷移を基準にした 100ms 割当（event-triggered average 等）を出力している。
ただし現状のD4B run01では、**truth遷移中心の100ms配置差は大きく出ない指標もある**ため、
本文ではまず「同電力でpout/TLが改善した」という事実（D4Bの主結果）を主軸に置くのが安全。
（必要に応じて、遷移定義や“outage近傍”での再可視化に拡張する）

`uccs_d4b_scan90/plots/outage_story_01/` は、上記の「同電力なのにpoutが改善」の内訳が、
**少数のアウトエイジ（TL>1s）イベントの差**として現れていることを示すための、失敗イベント中心の可視化。
（例: transition_step=1128 は U-only でTL≈9.89sだが、Policy(U+CCS)ではTL≈0.21s）

また、チェリーピック回避のため、
`outage_story_01` は `outage_ranking.csv`（U-onlyとPolicyのoutage率差）で遷移をランキングし、
その上位から「U-onlyが悪化している遷移」を機械的に選択してストーリー図を生成する（選び方を固定）。

### Fixedとの位置づけ（S4, scan90）

`Policy(U+CCS)` は

- vs `Fixed500`
  - power: `188.1 → 200.6 mW`（`+12.5 mW`）
  - `pout_1s`: `0.130 → 0.0488`（`-62.5%`）
  - → **電力を少し足してQoSを大きく改善**する点として置ける
- vs `Fixed100`
  - power: `208.3 → 200.6 mW`（`-7.65 mW`, 約 `-3.7%`）
  - `pout_1s`: `0.0813 → 0.0488`（改善）
  - → 本runでは `Fixed100` を支配して見えるが、**環境依存はある**ので本文では言い方を調整する（例: “in this setup”）。
