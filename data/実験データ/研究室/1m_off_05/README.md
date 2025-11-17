# 1m_off_05 実験サマリー（E2, 1 m, 広告OFF, 60 s）

- 取得日: 2025-11-16
- 距離: 1 m
- 環境: E2（干渉強）
- 条件: 広告OFF（無線停止）、TxPower設定なし、窓 60 s（SYNC立上り→固定窓）
- 目的: `1m_on_05` の ON 実験と比較し、OFF ベースラインの E_total と ΔE/adv の分母（ベースライン）の確立。

## 使用コード

- 送信/計測(OFF): `esp32/TX_BLE_Adv_Meter_OFF_10ms.ino`
  - Wi‑Fi/BLE を明示的に OFF にし、広告を停止。
  - INA219 を 10 ms 周期（100 Hz）でサンプリングし、整数CSV `mv,uA,p_mW` を UART1 に送出。
- 電力ロガ(TXSD): `esp32/TXSD_PowerLogger_PASS_THRU_ON_v2.ino`
  - TX からの整数CSVを受信し、`ms,mv,uA,p_mW` 形式で SD `/logs/trial_XXX_on.csv` に保存。
  - `p_mW = mv*uA/1e6` として `E_total_mJ` を積分。OFF のため TICK は未配線で `adv_count=0`。
- 受信ロガ: `esp32/RX_BLE_to_SD_SYNC_B.ino`
  - SYNCIN=26 でセッションを区切るが、広告OFFのため有意な受信データはほぼ無し。

## ファイル構成

- 本ディレクトリ:
  - `trial_021_on.csv`〜`trial_025_on.csv`: 電力ロガ出力（OFF ベースライン, `adv_count=0`）
  - `rx_trial_057.csv`〜`rx_trial_061.csv`: 受信ロガ出力（OFFのためヘッダ＋1行のみ）
  - `summary.md`: `scripts/summarize_trial_directory.py` による集計結果。

## 計測結果（PowerLogger, OFF 5 本）

- 共通:
  - `samples = 5999`, `rate_hz ≈ 100.0 Hz`
  - `dt_ms_mean ≈ 10.0 ms`, `dt_ms_std ≈ 1.3 ms`
  - `parse_drop = 0`
  - `adv_count = 0`

- `E_total_mJ`（trial_021〜025）:
  - trial_021_on.csv: `14878.9 mJ`
  - trial_022_on.csv: `14904.6 mJ`
  - trial_023_on.csv: `14906.5 mJ`
  - trial_024_on.csv: `14907.4 mJ`
  - trial_025_on.csv: `14904.9 mJ`

- 集計:
  - `E_total_mJ` 平均 ≈ **14900.5 mJ**（≈14.90 J/60 s）
  - 標準偏差 ≈ **10.8 mJ**（ばらつき ≈0.07%）

## 計測結果（RX, OFF 5 本）

- `rx_trial_057.csv`〜`rx_trial_061.csv`:
  - 各ファイルとも `rx_count=1` → PDR≈0.002（ほぼ 0）
  - 広告OFF条件のため、受信ログはノイズ的な 1 パケットのみであり、基本的に PDR/TL の評価対象外。

## 備考（ON_05 との比較）

- ON 側（`data/実験データ/研究室/1m_on_05` の良品セット trial_016〜019）は `E_total_mJ ≈ 17528.1 mJ`（≈17.53 J/60 s, ばらつき ≈0.5%）。
- 本 OFF_05 の平均と組み合わせると:
  - `ΔE ≈ 17528.1 − 14900.5 ≈ 2627.7 mJ`
  - `ΔE/adv ≈ 4.38 mJ/adv`（ON の `adv_count=600` を分母とした場合）
- 詳細な ON/OFF 差分は `results/summary_1m_E2_100ms_on_off_05.md` に整理。

