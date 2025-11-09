# 1m_off_03 実験データ（E2, 1 m, OFF, TXのみ起動）

- 取得日: 2025-11-09
- 条件: E2（干渉強）, 距離 1 m, 広告OFF（無線停止）, 窓 60 s
- 含有: `trial_011_off.csv`, `trial_012_off.csv`（PowerLogger出力）

## ダイアグ要約（末尾 #diag/#sys）
- E_total_mJ 平均 ≈ 11825.47 mJ（±0.86）
- rate_hz ≈ 105.7 Hz（実効取り込み）
- mean_v ≈ 3.314 V, mean_i ≈ 59.34 mA → mean_p ≈ 196.6 mW
- dt_ms_mean ≈ 9.46 ms, dt_ms_std ≈ 7.07 ms
- parse_drop ≈ 1.40e4
- sys: cpu_mhz=240, wifi_mode=OFF

## メモ
- TX（OFF）のUARTは数値行のみ送出に修正済みだが、rate_hzが~106 Hz、parse_dropが多い。
- UART帯域/バッファやI2C周期の見直し（printfの行間隔/バッファリング）を含めて要再検討。

