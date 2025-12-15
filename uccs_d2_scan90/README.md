# uccs_d2_scan90（Step D2 実機：動的QoS（TL/Pout）を“動的ログ”起点で確定）

## 目的（Gate-D2）

* D1で「100↔500 の動的切替が成立（電力も線形混合で説明可能）」まで確認できた。
* D2では **動的でもTL/Poutを評価できるログ仕様**にして、実機の `TL/Pout(τ)` を確定する。

## 方針（最小で壊れない形）

* 真値は **stress causal（100msグリッド）** を使用:
  * `Mode_C_2_シミュレート_causal/ccs/stress_causal_S1.csv`
  * `Mode_C_2_シミュレート_causal/ccs/stress_causal_S4.csv`
* TXは上記CSV由来の **label/U/CCS** をフラッシュに埋め込み、同一セッションを再生する。
* 動的でも同期が壊れないよう、広告payloadに **`step_idx`（100msグリッドの整数）**を入れる。

## スケッチ（Arduino IDE 用）

* TX: `src/tx/TX_UCCS_D2_SCAN90/TX_UCCS_D2_SCAN90.ino`
* RX: `src/rx/RX_UCCS_D2_SCAN90/RX_UCCS_D2_SCAN90.ino`
* TXSD: `src/txsd/TXSD_UCCS_D2_SCAN90/TXSD_UCCS_D2_SCAN90.ino`

## 配線（1210系と同じ）

* TX `GPIO25 (SYNC_OUT)` → RX `GPIO26 (SYNC_IN)` / TXSD `GPIO26 (SYNC_IN)`
* TX `GPIO27 (TICK_OUT)` → TXSD `GPIO33 (TICK_IN)`

## 実行（1回の起動で自動ループ）

* セッション: S1 と S4（両方）
* 条件（各セッションで3つ）:
  1. Fixed100
  2. Fixed500
  3. Policy(100↔500, u_mid=0.20,u_high=0.35,c_mid=0.20,c_high=0.35,hyst=0.02)
* 繰り返し: `REPEAT=3`（= 各条件×3）

※ trialの長さは `EFFECTIVE_LEN_STEPS`（100msグリッドの長さ）で決まる。デフォルトは 1800 (=180s)。

## TX payload仕様（ManufacturerData）

* 形式: `<step_idx>_<tag>`
  * `step_idx`: 100msグリッドの整数（0..）
  * `tag`: `F1-<label>-<itv>` / `P1-<label>-<itv>` / `F4-...` / `P4-...`
    * 先頭: `F`=fixed, `P`=policy
    * `1/4`: session id
    * `<label>`: 真値ラベル（数値）
    * `<itv>`: current interval（100 or 500）

この設計により、**動的でも `step_idx*100ms` が真値時刻として扱える**。

## TXSD cond_id（preamble TICKパルス数）

* 1: S1 fixed100
* 2: S1 fixed500
* 3: S1 policy
* 4: S4 fixed100
* 5: S4 fixed500
* 6: S4 policy

trial中は **各広告更新ごとにTICKを1発**出し、TXSD側で `adv_count=tick_count` が取れる。

## データ配置

* SDから吸い上げた `/logs/` を `data/<run>/{RX,TXSD}/` にコピーする。
* `data/<run>/README.md` に測定条件（距離/環境/電源/scan duty）をメモ。

