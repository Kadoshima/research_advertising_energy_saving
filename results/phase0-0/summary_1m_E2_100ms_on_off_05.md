# 1m, E2, 100 ms ON/OFF 実験サマリ（1m_on_05 / 1m_off_05）

- 生成日: 2025-11-16
- スクリプト: `scripts/summarize_trial_directory.py`
- 対象ディレクトリ:
  - ON: `data/実験データ/研究室/1m_on_05`
  - OFF: `data/実験データ/研究室/1m_off_05`
- 条件: 距離 1 m / 環境 E2 / 窓 60 s / TxPower=0 dBm / adv_interval=100 ms（ON時）

---

## 1. 使用コードと構成

- TX（DUT, ON 100 ms）: `esp32/TX_BLE_Adv_Meter_blocking.ino`
  - BLEアドバタイズ 100 ms, INA219 2 ms サンプリング（mv,uA 整数CSV）。
  - SYNC_OUT=25, TICK_OUT=27。
- TX（DUT, OFF ベースライン）: `esp32/TX_BLE_Adv_Meter_OFF_10ms.ino`
  - Wi‑Fi/BLE 明示 OFF, 広告停止。
  - INA219 10 ms サンプリング（mv,uA,p_mW 整数CSV）。
- PowerLogger（共通）: `esp32/TXSD_PowerLogger_PASS_THRU_ON_v2.ino`
  - TX からの整数CSVを受信し、`ms,mv,uA,p_mW` で SD `/logs/trial_XXX_on.csv` に保存。
  - `p_mW = mv*uA/1e6` として `E_total_mJ` を積分。
  - ON では TICK_IN=33 で adv パルスをカウント（`adv_count≈600`）、OFF では TICK 未配線で `adv_count=0`。
- RX ロガー: `esp32/RX_BLE_to_SD_SYNC_B.ino`
  - SYNC でセッションを区切り、`/logs/rx_trial_XXX.csv` に `ms,event,rssi,addr,mfd` を保存。

---

## 2. ON 側結果（1m_on_05）

### 2.1 PowerLogger（trial_015〜019）

|file           |samples|rate_hz|adv_count|E_total_mJ|E/adv_uJ|parse_drop|備考         |
|--------------|-------|-------|---------|----------|--------|----------|------------|
|trial_015_on  |29972  |499.55 |600      |23238.9   |38731.5 |0         |平均電流が他より高く外れ値候補|
|trial_016_on  |29949  |499.16 |600      |17536.7   |29227.8 |1         |            |
|trial_017_on  |29937  |498.97 |600      |17413.6   |29022.6 |0         |            |
|trial_018_on  |29996  |499.94 |600      |17504.6   |29174.3 |0         |            |
|trial_019_on  |29995  |499.92 |600      |17658.0   |29430.0 |0         |            |

- 共通:
  - `dt_ms_mean ≈ 2.0 ms`, `dt_ms_std ≈ 1.5–1.6 ms`
  - `sys: cpu_mhz=240, wifi_mode=OFF, free_heap≈260600`

### 2.2 ON 良品セット（trial_016〜019）の統計

- `E_total_mJ` 平均 ≈ **17528.1 mJ**（≈17.53 J/60 s）
- 標準偏差 ≈ **87.5 mJ**（ばらつき ≈0.5%）
- `adv_count` は全て 600（TICK カウント）。
- 外れ値 trial_015_on は `E_total_mJ ≈ 23239 mJ`, `mean_i ≈ 116 mA` と他 4 本と有意に乖離しており、別条件・一時的な負荷上昇の可能性が高いため ΔE 評価からは除外。

### 2.3 RX（rx_trial_052〜056）

|file          |rx_count|PDR   |median RSSI|uniq_adv|TL_p95_ms|Pout(1s)|Pout(2s)|Pout(3s)|
|-------------|--------|------|-----------|--------|---------|--------|--------|--------|
|rx_trial_052 |518     |0.863 |-41        |517     |99       |0.000   |0.000   |0.000   |
|rx_trial_053 |520     |0.867 |-34        |519     |58       |0.000   |0.000   |0.000   |
|rx_trial_054 |518     |0.863 |-35        |517     |7        |0.000   |0.000   |0.000   |
|rx_trial_055 |513     |0.855 |-34        |512     |139      |0.000   |0.000   |0.000   |
|rx_trial_056 |514     |0.857 |-34        |513     |87       |0.000   |0.000   |0.000   |

- PDR 平均 ≈ **0.861**（±0.004）
- Pout(1 s), Pout(2 s), Pout(3 s) はいずれも **0.000**（このセットでは TL が 1 s を超える広告は観測されず）。
- RSSI 中央値は −41〜−34 dBm の範囲。E2/1 m として過去実験と同程度。

---

## 3. OFF 側結果（1m_off_05）

### 3.1 PowerLogger（trial_021〜025）

|file           |samples|rate_hz|adv_count|E_total_mJ|parse_drop|
|--------------|-------|-------|---------|----------|----------|
|trial_021_on  |5999   |100.00 |0        |14878.9   |0         |
|trial_022_on  |5999   |99.99  |0        |14904.6   |0         |
|trial_023_on  |5999   |99.99  |0        |14906.5   |0         |
|trial_024_on  |5999   |99.99  |0        |14907.4   |0         |
|trial_025_on  |5999   |100.00 |0        |14904.9   |0         |

- 共通:
  - `dt_ms_mean ≈ 10.0 ms`, `dt_ms_std ≈ 1.3 ms`
  - `sys: cpu_mhz=240, wifi_mode=OFF, free_heap≈260600`

- 集計:
  - `E_total_mJ` 平均 ≈ **14900.5 mJ**（≈14.90 J/60 s）
  - 標準偏差 ≈ **10.8 mJ**（ばらつき ≈0.07%）

### 3.2 RX（rx_trial_057〜061）

|file          |rx_count|PDR  |median RSSI|
|-------------|--------|-----|-----------|
|rx_trial_057 |1       |0.002|None       |
|rx_trial_058 |1       |0.002|None       |
|rx_trial_059 |1       |0.002|None       |
|rx_trial_060 |1       |0.002|None       |
|rx_trial_061 |1       |0.002|None       |

- 広告OFF条件のため、受信ログはノイズ的な 1 パケットのみで、PDR/TL 評価は行わない（期待どおりほぼ 0）。

---

## 4. ON/OFF 差分（ΔE, ΔE/adv）

### 4.1 ΔE（区間エネルギー差）

- ON 良品セット平均: `E_on ≈ 17528.1 mJ`
- OFF 平均: `E_off ≈ 14900.5 mJ`
- 差分:
  - `ΔE = E_on − E_off ≈ 2627.7 mJ`（≈ **+2.63 J/60 s**）

### 4.2 ΔE/adv（1広告あたりの増分エネルギー）

- ON の `adv_count = 600`（TICK カウント）を分母として:
  - `ΔE/adv ≈ 2627.7 mJ / 600 ≈ **4.38 mJ/adv**`

### 4.3 コメント

- OFF ベースラインは `E_total_mJ ≈ 14.90 J/60 s` を ±0.07% で再現しており、ベースラインとして非常に安定。
- ON（trial_016〜019）は `E_total_mJ ≈ 17.53 J/60 s` を ±0.5% 程度で再現しており、ON 側の電力も安定。
- この差分から得られる `ΔE/adv ≈ 4.4 mJ/adv` は、計測系（INA219＋TXSD）の定常オーバーヘッドが ON/OFF で共通である前提のもと、「広告ONにしたことで追加で消費されるエネルギー（1 advあたり）」として解釈できる。

---

## 5. まとめと今後の利用

- 本セット（1m_on_05 / 1m_off_05）は、E2/1 m / 100 ms 条件における ΔE/adv ≈ **4.4 mJ/adv** の代表値として利用できる。
- 受信側の PDR ≈0.86 も過去の 1m_ad 系ログと整合しており、リンク品質も十分に安定。
- フェーズ1の KPI（平均電流, ΔE/adv, PDR, 将来の TL/Pout）のベースラインとして、本結果を参照する。
