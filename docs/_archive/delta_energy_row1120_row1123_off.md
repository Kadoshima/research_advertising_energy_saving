# ΔE/adv (flex patterns, time-scaled OFF) — 旧構成 (参照用)
> 2025-12-03 注: 本ページの値は v2 rig（計測込み）＋UART化けの旧構成 (row_1120/row_1123_off) に基づく歴史的参照値です。正式な比較・設計には v3 rig 再計測（Mode A/B/C…、P_off_B≈23 mW, P_off_A≈11.8 mW, Mode C2/C2' の新ΔE/adv）を使用してください。

- ON dir: `data/実験データ/研究室/row_1120/TX`
- OFF dir: `data/実験データ/研究室/row_1123_off/TX`
- manifest: `experiments_manifest.yaml` (include=false skipped)
- MAD filter: upper = median + 3.0 * MAD on P_off_trial
- OFF trials kept: 7/7
- OFF mean E_total_mJ (raw, pre-MAD): 1326.381
- OFF mean P_mW (after filters): 22.106

|interval_ms|on_trials|P_off_mW|ΔE_per_adv_mJ_mean|ΔE_per_adv_mJ_std|ΔE_per_adv_µJ_mean|
|---|---|---|---|---|---|
|100|10|22.106|2.256817|0.162236|2256.82|
|500|10|22.106|9.760084|0.339166|9760.08|
|1000|4|22.106|19.661114|0.133517|19661.11|
|2000|2|22.106|39.481759|0.063065|39481.76|
