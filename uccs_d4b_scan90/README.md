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
  * 注意: SDコピーでmtimeが壊れることがあるため、TXSDは **cond_idでグルーピング**して割り当てる。

* 図（任意）: `uccs_d4b_scan90/analysis/plot_power_vs_pout.py`
  * 入力: `--summary-csv uccs_d4b_scan90/metrics/<run>/summary_by_condition.csv`
  * 出力: `uccs_d4b_scan90/plots/d4b_<run>_power_vs_pout.png`（PDFも同時生成）

