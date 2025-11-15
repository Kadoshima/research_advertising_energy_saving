# 1m_off 実験データ（E2, 1 m, 広告OFF, 60 s）

- 取得日: 2025-11-09
- 距離: 1 m
- 環境: E2（干渉強）
- 条件: 広告OFF（無線停止）、TxPower設定なし、窓 60 s（SYNC立上り→固定窓）
- 使用コード（分離版）:
  - 送信/計測(OFF): `esp32/TX_BLE_Adv_Meter_OFF_10ms.ino`（旧 `Combined_TX_Meter_UART_B_nonblocking_OFF.ino`）
  - 電力ロガ(OFF): `esp32/TXSD_PowerLogger_SYNC_TICK_OFF.ino`（旧 `PowerLogger_UART_to_SD_SYNC_TICK_B_OFF.ino`）
  - 受信ロガ: `esp32/RX_BLE_to_SD_SYNC_B.ino`（旧 `RxLogger_BLE_to_SD_SYNC_B.ino`）

## ファイル構成
- `trial_001_off..006_off.csv`: 電力ロガ出力（V×I積分, summary行に `adv_count=0`）
- `rx_trial_016..021.csv`: 受信ロガ出力（OFFのため有意データは無）
- チェックサム: `data/実験データ/SHA256.txt` に統合記録

## 備考
- ΔE 算出用のベースライン。ONデータと同条件（E2/1 m/60 s）で比較。
- 本セットでは `E_total_mJ ≈ 5.5 J/60 s` と見積られており、ONデータ（≈1.93 J/60 s）より大きい値となっているため、配線/レンジ/供給系の再点検を推奨（例：INA219レンジ・シャント向き・3.3V_A/B混在・BLEタスク停止確認）。
