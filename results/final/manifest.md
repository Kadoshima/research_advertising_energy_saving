# results/final manifest

更新日: 2025-12-18

このファイルは `results/final/` 配下の「最終成果物」が、どの入力/スクリプト/実験runに基づくかを追跡する台帳。

## 図（fig）

### 主図（scan70/scan90同一座標、bootstrap CI）

- 出力: `results/final/fig/fig_main_scan70_scan90.svg`
- 元: `uccs_d4b_scan90/plots/mainfig_scan70_scan90.svg`
- 生成:
  - `python3 uccs_d4b_scan90/analysis/plot_mainfig_scan70_scan90.py --scan90 uccs_d4b_scan90/metrics/01/per_trial.csv --scan70 uccs_d4b_scan70/metrics/01_fixed/per_trial.csv --out results/final/fig/fig_main_scan70_scan90.svg`

### 役割分離（D3/D4/D4B統合）

- 出力: `results/final/fig/fig_role_separation_d3_d4_d4b.svg`
- 元: `uccs_d4b_scan90/plots/role_separation_d3_d4_d4b.svg`
- 生成:
  - `python3 uccs_d4b_scan90/analysis/plot_role_separation_overview.py --out results/final/fig/fig_role_separation_d3_d4_d4b.svg`

### α（正規化電力）×QoS

- 出力: `results/final/fig/fig_alpha_vs_pout_overview.svg`
- 元: `uccs_d4b_scan90/plots/alpha_vs_pout_overview.svg`
- 生成:
  - `python3 uccs_d4b_scan90/analysis/plot_alpha_vs_pout.py --out results/final/fig/fig_alpha_vs_pout_overview.svg`

### 失敗イベント中心（outage story）

- 出力: `results/final/fig/fig_outage_story_01.svg`
- 元: `uccs_d4b_scan90/plots/outage_story_01/fig_outage_timeline.svg`
- 生成:
  - `python3 uccs_d4b_scan90/analysis/outage_story_trace.py ...`（詳細は `uccs_d4b_scan90/plots/outage_story_01/README.md` を参照）

## 表（tab）

### D3/D4/D4B/D4B-scan70の集約（条件別）

- 出力: `results/final/tab/tab_summary_by_condition.csv`
- 元（入力）:
  - `uccs_d3_scan70/metrics/01/summary_by_condition.csv`
  - `uccs_d4_scan90/metrics/01/summary_by_condition.csv`
  - `uccs_d4b_scan90/metrics/01/summary_by_condition.csv`
  - `uccs_d4b_scan70/metrics/01_fixed/summary_by_condition.csv`
- 生成:
  - `python3 results/final/scripts/build_tables.py --out results/final/tab/tab_summary_by_condition.csv`

