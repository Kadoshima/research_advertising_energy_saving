# uccs_d4b_scan70（Step D4B-scan70: CCS寄与をscan70で確認 / Ablation）

## 目的

`uccs_d4b_scan90` の D4B（CCS-off=U-only）に対して、**受信条件を1段悪化（scan duty 90→70%）**させた環境でも
「U-only と U+CCS が同電力（同α）なのに、U+CCS がQoS（Pout/TL）を改善する」が成立するかを確認する。

* 対象セッション: **S4のみ**
* 条件: 4条件（Fixed100 / Fixed500 / Policy(U+CCS) / U-only(CCS-off)）
* 目安: n=2〜3（時間が許す範囲で増やす）

## 真値（truth）

* `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv`（100msグリッド, n_steps=1800=180s）
* TXは上記CSV由来の `label/U/CCS` をフラッシュに埋め込み、同一セッションを再生する。

## スケッチ（Arduino IDE 用）

* TX: `uccs_d4b_scan70/src/tx/TX_UCCS_D4B_SCAN70/TX_UCCS_D4B_SCAN70.ino`
* RX: `uccs_d4b_scan70/src/rx/RX_UCCS_D4B_SCAN70/RX_UCCS_D4B_SCAN70.ino`
* TXSD: `uccs_d4b_scan70/src/txsd/TXSD_UCCS_D4B_SCAN70/TXSD_UCCS_D4B_SCAN70.ino`

## scan70 の設定（RX）

* scan interval: 100ms
* scan window: 70ms

## 配線

* TX `GPIO25 (SYNC_OUT)` → RX `GPIO26 (SYNC_IN)` / TXSD `GPIO26 (SYNC_IN)`
* TX `GPIO27 (TICK_OUT)` → TXSD `GPIO33 (TICK_IN)`

## 実行

* 1回の起動で S4 × 4条件を自動実行（`REPEAT`回数はスケッチ内）。
* trial長: 180s（`EFFECTIVE_LEN_STEPS=1800`）。

## TX payload仕様（ManufacturerData）

形式: `<step_idx>_<tag>`

* `step_idx`: 100msグリッドの整数
* `tag`: `F4-<label>-<itv>` / `P4-<label>-<itv>` / `U4-<label>-<itv>`
  * `F`: fixed, `P`: policy(U+CCS), `U`: U-only（CCS-off）
  * `<label>`: truth label
  * `<itv>`: current interval（100 or 500）

## データ配置

* SDから吸い上げた `/logs/` を `uccs_d4b_scan70/data/<run>/{RX,TX}/` にコピーする（TX=TXSDログ）。
* `uccs_d4b_scan70/data/<run>/README.md` に測定条件をメモ。

## 解析

scan90と同じスクリプトをそのまま使える（RX tag / TXSD adv_count クラスタリング）:

* `python3 uccs_d4b_scan90/analysis/summarize_d4b_run_v2.py --rx-dir uccs_d4b_scan70/data/<run>/RX --txsd-dir uccs_d4b_scan70/data/<run>/TX --out-dir uccs_d4b_scan70/metrics/<run>`

