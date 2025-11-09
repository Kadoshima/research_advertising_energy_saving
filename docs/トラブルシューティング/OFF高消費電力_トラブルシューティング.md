# BLE OFF時の高消費電力 トラブルシューティング

- 作成日: 2025-11-09
- 目的: OFF計測（広告OFF, 60 s）で ON より大きな消費が観測される事象の原因切り分けと是正。

## 症状（Summary）
- 条件: E2（干渉強）, 距離 1 m, 窓 60 s, TxPower=0 dBm（ON時）
- ON（1m_ad, n=6）: `E_total ≈ 1.93 J/60 s`, `PDR ≈ 0.858`
- ON再試行（1m_ad_retry, n=2）: `E_total ≈ 1.66 J/60 s`
- OFF（1m_off, n=6）: `E_total ≈ 5.51 J/60 s`
- OFF_02（1m_off_02, n=2）: `E_total ≈ 11.73 J/60 s`, `mean_i ≈ 59 mA`, `rate_hz ≈ 150.8 Hz`, `wifi_mode=OFF`
- 期待に反し、OFF > ON が継続。OFF_02 はさらに増加。

## 環境・構成（現状）
- TX+INA（DUT, OFF用）: `esp32/Combined_TX_Meter_UART_B_nonblocking_OFF.ino`
  - BLE初期化なし, `WiFi.mode(WIFI_OFF)` 明示, UARTは数値行（v,i,p）のみ送出（2025-11-09修正）
- PowerLogger（OFF用）: `esp32/PowerLogger_UART_to_SD_SYNC_TICK_B_OFF.ino`
  - 受信CSV末尾に `# summary/# diag/# sys` を出力（V×I積分・dt統計・システム状態）
- 受信ロガ（共通）: `esp32/RxLogger_BLE_to_SD_SYNC_B.ino`
- 供給: DUT=3.3V_A（測定対象）, ロガ/INA=3.3V_B（GND共通）

## データ参照（Paths）
- ON: `data/実験データ/研究室/1m_ad/`（6本）, 要約 `results/フェーズ0-0_E2_1m_100ms_2025-11-09.md`
- ON再試行: `data/実験データ/研究室/1m_ad_retry/`（2本）, 要約 `results/フェーズ0-0_E2_1m_100ms_retry_latest_2025-11-09.md`
- OFF: `data/実験データ/研究室/1m_off/`（6本）, ΔE `results/フェーズ0-0_E2_1m_100ms_deltaE_2025-11-09.md`
- OFF_02: `data/実験データ/研究室/1m_off_02/`（2本）, 要約 `results/フェーズ0-0_E2_1m_100ms_off_02_2025-11-09.md`

## 仮説（Hypotheses）
1) 計測負荷（I2C/printf/UART）によるDUT側平均電流の上振れ（OFFでアイドルに入れず消費増）
2) 供給/配線の取り回し（3.3V_A/Bの混在, シャント向き, GNDループ）による見かけ電流の増加
3) INA219レンジ/オフセットのズレ（ベースの+オフセットが過大）
4) スタック停止状態の差（Wi‑Fiは停止済, BT/BLEはOFFコードで未初期化だが残留がないか）

## 暫定対策（2025-11-09）
- TX（OFF）のUARTから `# diag/# sys` を完全停止 → 数値行のみ送出
- 期待効果: `parse_drop`の桁落ち, 実効レート `rate_hz ≈ 500 Hz` へ回復, 平均電流の低下

## 検証計画（10分テスト）
1) TX（OFF）に上記修正を反映, PowerLogger（OFF）は診断付きのまま
2) 10分（600 s）取得 → PowerLogger CSV末尾の診断を確認
   - `rate_hz ≈ 500`（SAMPLE_US=2000 μs）
   - `parse_drop ≈ 0`
   - `dt_ms_mean ≈ 2.0`（±小）、`dt_ms_std`が過大でない
   - `mean_i` がON時（9–10 mA）に近づくか
3) 併せて ΔE を再集計（`scripts/compute_power_and_pdr.py`）

## 再計算コマンド（例）
- `python scripts/compute_power_and_pdr.py --data-dir data/実験データ/研究室/1m_ad_retry --off-dir data/実験データ/研究室/1m_off_02 --expected-adv-per-trial 600 --out results/summary_1m_E2_100ms_deltaE_retry_off02.md`

## 更新ルール
- 本ファイルに日付見出しで観測・対策・結果を追記していく（YYYY-MM-DD）。

