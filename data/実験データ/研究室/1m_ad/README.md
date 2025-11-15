# 1m_ad 実験データ（E2, 1m, 100 ms固定）

- 取得日: 2025-11-09
- 距離: 1 m
- 環境: E2（干渉強, 2.4GHz Wi‑Fi稼働）
- 条件: BLE広告間隔 100 ms, TxPower=0 dBm, 窓 60 s（SYNC立上り→固定窓）
- 使用コード（ON/OFF非分離の共通版）:
  - 送信/計測: `esp32/TX_BLE_Adv_Meter_blocking.ino`（旧 `Combined_TX_Meter_UART_B.ino`）
  - 電力ロガ: `esp32/TXSD_PowerLogger_PASS_THRU_ON_v2.ino`（旧 `PowerLogger_UART_to_SD_SYNC_TICK_B.ino`）
  - 受信ロガ: `esp32/RX_BLE_to_SD_SYNC_B.ino`（旧 `RxLogger_BLE_to_SD_SYNC_B.ino`）

## ファイル構成
- `trial_009..014.csv`: 電力ロガ出力（V×I積分, summary行あり）
- `rx_trial_010..015.csv`: 受信ロガ出力（PDR算出用）
- `../SHA256.txt`: 本ディレクトリ配下のチェックサムは `data/実験データ/SHA256.txt` に統合記録

## 既知事項
- `trial_*.csv` の `adv_count` は TICK未配線時、`t/100ms` の近似値（=600）。
- ΔE算出は ON/OFF分離版を推奨（本データはON/OFF非分離コードで取得）。
