# まとめ（scan90 v5 / δ tight）

- 生成日: 2025-12-14 (JST)
- コンテキスト重み（mHealth合成, 有効窓のみ）: stable=0.7714 / transition=0.2286（`selected_policies.json`）
- 図: `fig_delta_band.png`

## 固定（基準点）

powerは `power_table_sleep_eval_2025-12-13.csv`、QoSは scan90 v5（stable→S1 / transition→S4）で合成。

| policy | avg_power_mW | pout_1s |
| --- | ---: | ---: |
| Fixed 100 | 201.45 | 0.0016 |
| Fixed 500 | 182.95 | 0.0322 |
| Fixed 1000 | 180.50 | 0.0532 |
| Fixed 2000 | 179.75 | 0.4092 |

## ルール（U+CCS, power-min）

`pareto_front_v6_power_table_scan90_v5/pareto_sweep.csv` から、各δで `avg_power_mW` 最小の点を選定。

| δ | avg_power_mW | pout_1s | share100 | share500 | share2000 | adv_rate | switch_rate | params(u_mid,u_high,c_mid,c_high,hyst) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.02 | 198.91 | 0.011 | 0.865 | 0.121 | 0.014 | 8.90 | 0.026 | (0.15,0.35,0.10,0.35,0.08) |
| 0.03 | 197.85 | 0.030 | 0.816 | 0.121 | 0.063 | 8.44 | 0.029 | (0.10,0.35,0.15,0.35,0.08) |
| 0.04 | 197.69 | 0.040 | 0.813 | 0.096 | 0.092 | 8.36 | 0.028 | (0.10,0.35,0.20,0.35,0.08) |

## 読み（結論）

- `Fixed 500ms` の `pout_1s≈0.0322` が境界になる（δ<0.0322 だと Fixed500 は不可能）。
- δ=0.03（Fixed500が落ちる帯）では、ルールは `avg_power≈197.85mW` で `Fixed100(201.45mW)` より **約−3.6mW（約−1.8%）** 低い。
- δ≥0.04 では `Fixed 500ms` が（QoS/電力ともに）支配しやすく、ルールの出番が薄い。
