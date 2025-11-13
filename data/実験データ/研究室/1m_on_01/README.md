# 1m_on_01 実験サマリー（E2, 1 m, 100 ms, ON）

- 日付: 2025-11-09
- 条件: 距離 1 m / 環境 E2 / アドバタイズ ON（100 ms, 0 dBm）
- 配線: SYNC 25→26, TICK 27→33, UART TX=4→RX=34, SD CS=5 SCK=18 MISO=19 MOSI=23
- 構成: 
  - TX+INA219（DUT）: `esp32/Combined_TX_Meter_UART_B_nonblocking.ino`
  - PowerLogger（パススルー）: `esp32/PowerLogger_UART_to_SD_SYNC_TICK_B_ON.ino`
  - RX Logger: `esp32/RxLogger_BLE_to_SD_SYNC_B.ino`

## 含まれるファイル（SHA256）

```
33497064c3d72157b13ab4435f37a9c5092389e0d87b4c189d2d3314d601d5ec  trial_001_on.csv
2a2ec69adea18946c60460ed1e7d90e558eb9e39f09e5cc537dc0b8ca67c63ab  trial_002_on.csv
6d48f5865e6415579a5b149c1e9af7044710067f53d27155fd6ed033fa21adb2  rx_trial_029.csv
77f20dac643ad1d0d0b5c08066ebc04eaea0c7e354869086a0c57d12eb280441  rx_trial_030.csv
```

## 計測結果（オフライン積分: V×I）

- trial_001_on.csv
  - ms_total=60000, samples=20001, rate_hz≈333.35
  - adv_count=599（TICK推定）
  - E_total≈14207.2 mJ, E/adv≈23718.2 μJ

- trial_002_on.csv
  - ms_total=60000, samples=20019, rate_hz≈333.65
  - adv_count=600（TICK推定）
  - E_total≈14164.4 mJ, E/adv≈23607.3 μJ

補足:
- PowerLoggerはパススルー構成のため、#summary の E_total_mJ は 0.000 固定。
- 本READMEの値は各行の `ms` 差分で `E_mJ += V[V] × I[mA] × dt[s]` を積分した結果。

## 受信ログ（PDR概算）

- rx_trial_029.csv: 516 捕捉 → PDR≈0.86（516/600）
- rx_trial_030.csv: 517 捕捉 → PDR≈0.862（517/600）

## 品質メモと留意事項

- PowerLogger側 #diag: `parse_drop=0`, `dt_ms_mean≈3.0`, `rate_hz≈333 Hz`（サンプル欠落なし）。
- 稀に数値列に文字化けが混入（例: `6#.3` や `485>0`）。下位ニブル落ちに相当する既知パターン（`!→1, "→2, #→3, $→4, %→5, &→6, '→7, (→8, )→9, 空白→0, >→.`）を補正してパース。
- 今後の堅牢化: TX送出の整数化/固定長バイナリ化、受信側のSD書込みチャンク拡大（8→16 KB）を検討。

## 参考（ΔE 確認）

- OFF_04（パススルー, 60s）: E_total≈11773.6 mJ（別フォルダ: `data/実験データ/研究室/1m_off_04`）
- 本ONデータとの比較:
  - ΔE_001 ≈ +2.43 J（14207.2 − 11773.6）
  - ΔE_002 ≈ +2.39 J（14164.4 − 11773.6）
- 期待どおり ΔE ≥ 0 を確認。

## 生成情報（再現用）

- 取得方法: PowerLogger をパススルー（`ms,raw_payload`）で記録。`#summary` の E_total は未計算。
- 解析手順: オフラインで `ms, v, i` を読み、`E_mJ += v[i]*i[mA]*dt[s]` を積分、`adv_count` はログ末尾（TICK由来）を使用。
- 集計スクリプト: `scripts/compute_power_and_pdr.py` は「summary=0 のときオフライン積分」へ修正予定。

