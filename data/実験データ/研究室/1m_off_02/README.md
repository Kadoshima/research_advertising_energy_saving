# 1m_off_02 実験データ（E2, 1 m, 広告OFF, 60 s）

- 取得日: 2025-11-09
- 条件: E2（干渉強）, 距離 1 m, 広告OFF（無線停止）, 窓 60 s
- 含有ファイル: `trial_009_off.csv`, `trial_010_off.csv`（電力ロガ）, `rx_trial_*.csv`（受信ロガ）

## ダイアグ要約（ファイル末尾 #diag/#sys より）
- E_total_mJ 平均 ≈ 11732.93 mJ（±9.26）
- rate_hz ≈ 150.8 Hz（数値サンプルの実効取り込み）
- mean_v ≈ 3.300 V, mean_i ≈ 59.18 mA → mean_p ≈ 195 mW
- dt_ms_mean ≈ 6.64 ms, dt_ms_std ≈ 4.12 ms, dt_ms_min = 0, dt_ms_max ≈ 35 ms
- parse_drop ≈ 1.1e4（数値化できなかった行数；#行や破片を含む）
- sys: cpu_mhz=240, wifi_mode=OFF, free_heap≈276 kB

## メモ
- OFF>ON（ON≈1.66 J/60 s, OFF≈11.7 J/60 s）。現状ではOFFで平均電流が大きいため、
  ① サンプル/printf負荷（I2C/printf） ② 供給/配線（3.3V_A/B・シャント向き） ③ INA219レンジ/オフセット ④ スタック停止状態
  の順に点検を推奨。

