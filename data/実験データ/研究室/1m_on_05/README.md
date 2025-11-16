# 1m_on_05 実験サマリー計画（E2, 1 m, 100 ms, ON/OFFペア）

- 日付: 2025-11-16（予定）
- 目的: 距離 1 m / 環境 E2 / アドバタイズ間隔 100 ms 条件で、ON と OFF の消費電力差 ΔE、および ΔE/adv・PDR を評価するフェーズ1向けベースライン実験（実験1）。
- 評価指標: ΔE_total[mJ], ΔE/adv[mJ/adv], 平均電流[mA], PDR, TL分布, Pout(1 s)。

## 使用コード（予定）

- TX（DUT, ON 100 ms）: `esp32/TX_BLE_Adv_Meter_blocking.ino`
  - 100 ms 間隔で BLE アドバタイズ（TxPower=0 dBm）。
  - INA219 を 2 ms 周期（500 Hz）でサンプリングし、整数CSV `mv,uA` を UART1 (230400 bps) へ出力。
  - SYNC_OUT=25（100 ms High）、TICK_OUT=27（広告ごとにパルス出力）。

- TX（DUT, OFF ベースライン）: `esp32/TX_BLE_Adv_Meter_OFF_10ms.ino`
  - Wi‑Fi/BLE を明示的に OFF にし、広告を停止。
  - INA219 を 10 ms 周期（100 Hz）でサンプリングし、整数CSV `mv,uA,p_mW` を UART1 へ出力。
  - SYNC_OUT=25 のみ使用（TICK_OUTは未使用）。

- PowerLogger（TXSD, 共通）: `esp32/TXSD_PowerLogger_PASS_THRU_ON_v2.ino`
  - TX からの整数CSVを受信し、`ms,mv,uA,p_mW` 形式で SD `/logs/trial_XXX_on.csv` にパススルー保存。
  - 軽量パーサで `mv,uA` を取得し、`p_mW = mv*uA/1e6` として `E_total_mJ` を積分。
  - TICK_IN=33 で adv パルスをカウント（ON 時は `adv_count≈600`、OFF 時は `adv_count=0` の想定）。

- RX ロガー: `esp32/RX_BLE_to_SD_SYNC_B.ino`
  - SYNC_IN=26 でセッション開始/終了を検出し、`/logs/rx_trial_XXX.csv` に `ms,event,rssi,addr,mfd` を記録。
  - PDR/TL/Pout 計算用の受信ログを提供。

## 配線・条件（予定）

- 配線:
  - SYNC: TX GPIO25 → TXSD 26, RX 26
  - TICK: TX GPIO27 → TXSD 33（ON セッションのみ有効）
  - UART: TX UART1 TX=4 → TXSD RX=34
  - I2C: TX SDA=21, SCL=22 → INA219（`Wire.setClock(400 kHz)`）
- 条件:
  - 距離: 1 m 固定
  - 環境: E2（干渉強, 2.4 GHz Wi‑Fi 稼働）
  - 窓: SYNC 立ち上がりから 60 s 固定窓
  - TxPower: 0 dBm
  - スマホ側: フェーズ1 Runbook に準拠（LOW_LATENCY, NTP 同期, 重複除去設定など）。

## データ構成（予定）

- 本ディレクトリ:
  - `trial_XXX_on.csv`: PowerLogger 出力（ON/ OFF 両方とも `_on` 接尾辞。ON/OFF区別は README とファイル内 `# meta` で追跡）。
  - `rx_trial_XXX.csv`: RX ロガー出力（ON セッション時のみ有意）。
  - `summary.md`: `scripts/summarize_trial_directory.py` による集計サマリ（E_total_mJ, adv_count, PDR 等）。

- OFF 側ペアセット:
  - OFF ベースラインの trial は別ディレクトリ（例: `data/実験データ/研究室/1m_off_05/`）に保存し、同様に `README.md` と `summary.md` を作成予定。

## 想定する集計フロー

1. SD `/logs` から `trial_XXX_on.csv` と `rx_trial_XXX.csv` を本ディレクトリへコピーする。
2. 以下のスクリプトで電力と PDR を集計する:

   ```bash
   python3 scripts/summarize_trial_directory.py \
     --data-dir data/実験データ/研究室/1m_on_05
   ```

3. 自動生成される `summary.md` を確認し、少なくとも次をチェックする:
   - `rate_hz ≈ 100 Hz`（PowerLogger の実効サンプリングレート）
   - `dt_ms_mean ≈ 10 ms`, `dt_ms_std` が許容範囲（≲2 ms）
   - `parse_drop = 0`
   - ON セッションでは `adv_count ≈ 600`（TICK カウント）、PDR > 0.8（目安）
4. OFF 側の `summary.md` と組み合わせて、`ΔE = E_total_on − E_total_off` および `ΔE/adv = ΔE / adv_count_on` を算出し、フェーズ1 KPI（ΔE/adv, 平均電流, PDR/TL/Pout）の評価に用いる。

## まだ未確定／実験後に追記する事項

- 実際の取得日と試行数（n）、各 trial の SHA256 チェックサム。
- 実測値:
  - ON/OFF 各 trial の `E_total_mJ`, `E_per_adv_uJ`, `mean_i[mA]`
  - RX ログからの PDR, TL p95, Pout(1 s)
- ΔE/adv の結果（mJ/adv）と再現性（複数試行がある場合の平均±標準偏差）。

