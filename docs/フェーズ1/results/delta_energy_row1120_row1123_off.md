# ΔE/adv (flex patterns, time-scaled OFF)

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
