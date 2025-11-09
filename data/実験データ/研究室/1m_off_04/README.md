# 1m_off_04 実験データ（E2, 1 m, OFF, パススルー版）

- 取得日: 2025-11-09
- 条件: E2（干渉強）, 距離 1 m, 広告OFF（無線停止）, 窓 60 s
- 含有: `trial_013_off.csv`, `trial_014_off.csv`（PowerLogger出力; ms,raw_payload 形式）

## ダイアグ要約（末尾 #diag/#sys）
- rate_hz ≈ 339.6 Hz（実効取り込み; 2本平均）
- dt_ms_mean ≈ 2.94 ms, dt_ms_std ≈ 1.08 ms, parse_drop ≈ 0
- sys: wifi_mode=OFF, cpu_mhz=240

## オフライン積分（V×I; ロガ付与のmsで dt 算出）
- E_total_mJ: [11774.171, 11773.026] → 平均 ≈ 11773.599 mJ（±0.573）

## メモ
- パススルー化で parse_drop は 0 に改善、レートは ~340 Hz まで回復。目標の ~500 Hz には未達のため、受信/SDパスの更なる調整（SD_CHUNK/flush間隔/行処理の見直し、あるいはTX側の送信周期や整数化/バイナリ化）を検討。

