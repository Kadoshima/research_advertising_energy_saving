# まとめ（scan90 v5 / δ tight / actions={100,500}）

- 生成日: 2025-12-14 (JST)
- コンテキスト重み（mHealth合成, 有効窓のみ）: stable=0.7714 / transition=0.2286（`selected_policies.json`）
- 図: `fig_delta_band.png`

## 固定（基準点）

powerは `power_table_sleep_eval_2025-12-14_interval_sweep_sleep_on_n9_10.csv`、QoSは scan90 v5（stable→S1 / transition→S4）で合成。

| policy | avg_power_mW | pout_1s |
| --- | ---: | ---: |
| Fixed 100 | 198.56 | 0.0016 |
| Fixed 500 | 180.80 | 0.0322 |
| Fixed 1000 | 178.62 | 0.0532 |
| Fixed 2000 | 177.47 | 0.4092 |

## ルール（U+CCS, power-min, actions={100,500}）

`pareto_front_v8_power_table_scan90_v5_sleep_on_n9_10_actions_100_500/pareto_sweep.csv` から、各δで `avg_power_mW` 最小の点を選定。

| δ | avg_power_mW | pout_1s | share100 | share500 | adv_rate | switch_rate | params(u_mid,u_high,c_mid,c_high,hyst) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.02 | 188.78 | 0.020 | 0.449 | 0.551 | 5.59 | 0.037 | (0.15,0.30,0.15,0.35,0.02) |
| 0.03 | 187.36 | 0.023 | 0.369 | 0.631 | 4.96 | 0.040 | (0.20,0.35,0.20,0.35,0.02) |
| 0.04 | 187.36 | 0.023 | 0.369 | 0.631 | 4.96 | 0.040 | (0.20,0.35,0.20,0.35,0.02) |

## 読み（結論）

- `Fixed 500ms` の `pout_1s≈0.0322` が境界になる（δ<0.0322 だと Fixed500 は不可能）。
- actions={100,500} でも δ=0.03 を満たす点が存在し、power-min は `avg_power≈187.36mW` / `pout_1s≈0.0226`。
- δ=0.03（Fixed500が落ちる帯）では、ルールは `Fixed100(198.56mW)` より **約−11.20mW（約−5.6%）** 低い（かつ δ達成）。
- δ=0.04 では（本スイープ範囲では）選定点がδ=0.03と一致する（0.03以上が全点feasibleのため）。
