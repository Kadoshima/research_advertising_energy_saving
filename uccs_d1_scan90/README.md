# uccs_d1_scan90（Step D1 実機：U/CCS→interval 切替の成立確認）

## 目的（最小セット）

* **不確実性（U）+ 変化度（CCS）で adv interval を 100↔500ms 切替**し、実機ログ（RX/TXSD）で成立確認する。
* 主目的は「成立（切替できる・QoSが崩れない・Fixed100より電力が下がる）」で、**最適化ではない**。

## 代表ポリシー（D0で確定：actions={100,500}）

* `u_mid=0.20, u_high=0.35, c_mid=0.20, c_high=0.35, hyst=0.02`
* 初期 interval: 500ms
* 3値（100/500/2000）のルールを計算し、**actions={100,500} にクランプ**（2000→500）

## スケッチ（Arduino IDE 用）

* TX: `src/tx/TX_UCCS_D1_100_500/TX_UCCS_D1_100_500.ino`
* RX: `src/rx/RX_UCCS_D1_SCAN90/RX_UCCS_D1_SCAN90.ino`
* TXSD: `src/txsd/TXSD_UCCS_D1_SCAN90/TXSD_UCCS_D1_SCAN90.ino`

## 配線（1210系と同じ）

* TX `GPIO25 (SYNC_OUT)` → RX `GPIO26 (SYNC_IN)` / TXSD `GPIO26 (SYNC_IN)`
* TX `GPIO27 (TICK_OUT)` → TXSD `GPIO33 (TICK_IN)`

## 取得する条件（1回の起動で自動実行）

1. Fixed 100ms
2. Fixed 500ms
3. Policy（U/CCSで 100↔500）

* `N_CYCLES=3` なら **各条件×3回**（合計9試行）。
* 1試行 `TRIAL_DURATION_MS=60000`、試行間 `GAP_MS=5000` → 合計およそ **9分40秒**。

## ログ（SD）

* RX: `/logs/rx_trial_XXX.csv`
* TXSD: `/logs/trial_XXX_c<cond>_<tag>.csv`

### cond_id（TX→TXSD：preamble TICK パルス数）

* 1: fixed100
* 2: fixed500
* 3: policy

### TXのpayload仕様（ManufacturerData）

* 形式: `<tx_elapsed_ms>_<label>`
  * `tx_elapsed_ms`: trial開始からの経過ms（0〜65535の範囲で運用）
  * `label`:
    * fixed: `F100` / `F500`
    * policy: `P100` / `P500`（現在のinterval）

> 注: U/CCSの取得元は **現状は“疑似（synthetic）”入力**。実機HARに置き換える場合は TX の `updateSignals()` を差し替える。

## データの置き場所

* SDから吸い上げたログは `data/` 配下に日付ディレクトリを作って保存する（例: `data/2025-12-14_run01/`）。

