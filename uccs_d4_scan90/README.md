# uccs_d4_scan90（Step D4: Uが効いている切り分け / Ablation）

## 目的

実機D2bで得られた「Fixed100より省電力、Fixed500よりQoS良」の“程よい点”が **U（不確実度）**に依存しているかを、Ablationで切り分ける。

* 対象セッション: **S4のみ**（差が出やすい）
* 条件: 4条件 × n=3（最小セット）
  1. Fixed100
  2. Fixed500
  3. Policy（U+CCS）
  4. Ablation（**U-shuffle**: Uの分布は同じ、時間相関だけ破壊）

## 真値（truth）

* `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv`（100msグリッド, n_steps=1800=180s）
* TXは上記CSV由来の `label/U/CCS` をフラッシュに埋め込み、同一セッションを再生する。

## スケッチ（Arduino IDE 用）

* TX: `uccs_d4_scan90/src/tx/TX_UCCS_D4_SCAN90/TX_UCCS_D4_SCAN90.ino`
* RX: `uccs_d4_scan90/src/rx/RX_UCCS_D4_SCAN90/RX_UCCS_D4_SCAN90.ino`
* TXSD: `uccs_d4_scan90/src/txsd/TXSD_UCCS_D4_SCAN90/TXSD_UCCS_D4_SCAN90.ino`

## 配線

* TX `GPIO25 (SYNC_OUT)` → RX `GPIO26 (SYNC_IN)` / TXSD `GPIO26 (SYNC_IN)`
* TX `GPIO27 (TICK_OUT)` → TXSD `GPIO33 (TICK_IN)`

## 実行

* 1回の起動で S4 × 4条件を自動実行（`REPEAT=3`）。
* trial長: 180s（`EFFECTIVE_LEN_STEPS=1800`）。

## TX payload仕様（ManufacturerData）

形式: `<step_idx>_<tag>`

* `step_idx`: 100msグリッドの整数（0..）
* `tag`: `F4-<label>-<itv>` / `P4-<label>-<itv>` / `A4-<label>-<itv>`
  * `F`: fixed, `P`: policy, `A`: ablation（U-shuffle）
  * `<label>`: truth label（2桁）
  * `<itv>`: current interval（100 or 500）

## TXSD cond_id（preamble TICKパルス数）

* 1: S4 fixed100
* 2: S4 fixed500
* 3: S4 policy
* 4: S4 ablation_u_shuf

trial中は「広告更新」ごとにTICKを1発出し、TXSD側で `adv_count=tick_count` を記録する（近似）。

## データ配置

* SDから吸い上げた `/logs/` を `uccs_d4_scan90/data/<run>/{RX,TX}/` にコピーする（TX=TXSDログ）。
* `uccs_d4_scan90/data/<run>/README.md` に測定条件をメモ。

## 解析

* 集計スクリプト: `uccs_d4_scan90/analysis/summarize_d4_run.py`
  * 入力: `--rx-dir .../RX --txsd-dir .../TX`
  * 出力: `per_trial.csv`, `summary_by_condition.csv`, `summary.md`

* 図（任意）: `uccs_d4_scan90/analysis/plot_power_vs_pout.py`
  * 入力: `--summary-csv uccs_d4_scan90/metrics/<run>/summary_by_condition.csv`
  * 出力: `uccs_d4_scan90/plots/d4_<run>_power_vs_pout.png`（PDFも同時生成）
  * 実行例（matplotlibは `.venv_mhealth310` 推奨）:
    - `.venv_mhealth310/bin/python uccs_d4_scan90/analysis/plot_power_vs_pout.py --summary-csv uccs_d4_scan90/metrics/01/summary_by_condition.csv --out uccs_d4_scan90/plots/d4_01_power_vs_pout.png`
