# 1m_on_05 実験サマリー（E2, 1 m, 100 ms, ON）

- 取得日: 2025-11-16
- 条件: 距離 1 m / 環境 E2 / アドバタイズ ON（100 ms, 0 dBm）
- 目的: OFF ベースライン（`1m_off_05`）と比較し、ON の E_total・ΔE/adv・PDR を評価する。

## 使用コード

- TX（DUT, ON 100 ms）: `esp32/TX_BLE_Adv_Meter_blocking.ino`
  - 100 ms 間隔で BLE アドバタイズ。
  - INA219 を 2 ms 周期（500 Hz）でサンプリングし、整数CSV `mv,uA` を UART1 (230400 bps) へ出力。
  - SYNC_OUT=25（100 ms High）、TICK_OUT=27（広告ごとにパルス出力）。
- PowerLogger（TXSD, パススルー）: `esp32/TXSD_PowerLogger_PASS_THRU_ON_v2.ino`
  - TX からの整数CSVを受信し、`ms,mv,uA,p_mW` 形式で SD `/logs/trial_XXX_on.csv` にパススルー保存。
  - 軽量パーサで `mv,uA` を取得し、`p_mW = mv*uA/1e6` として `E_total_mJ` を積分。
  - TICK_IN=33 で adv パルスをカウント（`adv_count≈600`）。
- RX ロガー: `esp32/RX_BLE_to_SD_SYNC_B.ino`
  - SYNC_IN=26 でセッション開始/終了を検出し、`/logs/rx_trial_XXX.csv` に `ms,event,rssi,addr,mfd` を記録。

## 実測結果（PowerLogger, ON 5 本）

- 取得ファイル: `trial_015_on.csv`〜`trial_019_on.csv`
- 共通:
  - `samples ≈ 29940〜29996`（60 s × 500 Hz）
  - `rate_hz ≈ 499〜500 Hz`
  - `adv_count = 600`
  - `parse_drop = 0`（`trial_016_on.csv` のみ 1 行落ち）

### E_total_mJ / E_per_adv_uJ（各本）

- trial_015_on.csv
  - `E_total_mJ = 23238.9` / `E_per_adv_uJ ≈ 38731.5`
  - `mean_i ≈ 116.2 mA`
  - 備考: 他 4 本と比べて平均電流が約 +30% 高く、外れ値候補。
- trial_016_on.csv
  - `E_total_mJ = 17536.7` / `E_per_adv_uJ ≈ 29227.8`
- trial_017_on.csv
  - `E_total_mJ = 17413.6` / `E_per_adv_uJ ≈ 29022.6`
- trial_018_on.csv
  - `E_total_mJ = 17504.6` / `E_per_adv_uJ ≈ 29174.3`
- trial_019_on.csv
  - `E_total_mJ = 17658.0` / `E_per_adv_uJ ≈ 29430.0`

### ON 良品セット（trial_016〜019）の統計

- `E_total_mJ` 平均 ≈ **17528.1 mJ**（≈17.53 J/60 s）
- 標準偏差 ≈ **87.5 mJ**（ばらつき ≈0.5%）
- `mean_i` は概ね **88〜89 mA** レンジ。

## 実測結果（RX, ON 5 本）

- 取得ファイル: `rx_trial_052.csv`〜`rx_trial_056.csv`
- 各本の PDR（期待 600 adv/60 s）:
  - rx_trial_052.csv: `rx=518` → PDR≈0.863 / median RSSI≈−41 dBm
  - rx_trial_053.csv: `rx=520` → PDR≈0.867 / median RSSI≈−34 dBm
  - rx_trial_054.csv: `rx=518` → PDR≈0.863 / median RSSI≈−35 dBm
  - rx_trial_055.csv: `rx=513` → PDR≈0.855 / median RSSI≈−34 dBm
  - rx_trial_056.csv: `rx=514` → PDR≈0.857 / median RSSI≈−34 dBm
- 集計:
  - `PDR` 平均 ≈ **0.861**（±0.004）
  - RSSI 中央値は −41〜−34 dBm の範囲。

## 備考（OFF_05 との比較に向けて）

- OFF 側（`data/実験データ/研究室/1m_off_05`）の `E_total_mJ` は ≈14.90 J/60 s（±0.07%）で、ON 良品セットとの ΔE は:
  - `ΔE ≈ 2.63 J/60 s`
  - `ΔE/adv ≈ 4.38 mJ/adv`（adv_count=600）
- 詳細な ON/OFF 差分と ΔE/adv のまとめは `results/summary_1m_E2_100ms_on_off_05.md` を参照。

