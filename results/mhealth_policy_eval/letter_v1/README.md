# letter_v1

レター用（Phase 1）の主張図を固定するための成果物。

## 図
- `fig_delta_band.png`
  - x: avg_power_mW（power table反映）
  - y: pout_1s
  - 破線: δ = 0.13 / 0.15 / 0.17
  - Fixed 100/500/1000/2000 と、ルールベース（U+CCS）の全点＋採用候補3点を同一図に表示

## 選定結果
- `selected_policies.csv`
- `selected_policies.json`（入力パスと stable/transition 重みも含む）

## 生成
```bash
MPLCONFIGDIR=sleep_eval_scan90/.mpl_cache .venv_mhealth310/bin/python scripts/plot_letter_delta_band.py
```

