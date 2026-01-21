# Phase 0-0 KPIレポート: ΔE v3rig sweep 2026-01-21 v02

## 目的/範囲
- Phase 0-0 のKPI確定（ΔE / PDR / RSSI / 完走）
- ΔE v3rig sweep 2026-01-21 v02 の結果整理

## 入力データ（出所/版/行数/SHA256）
- 出所: `data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02`
- 版: 2026-01-21_v02
- 行数: RX 50 files / 7,521 rows、TXSD 50 files / 297,001 rows（data rowsのみ）
- SHA256: `data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02/RX_SHA256.txt`, `data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02/TXSD_SHA256.txt`

## 出力物（生成日/生成スクリプト）
- 生成日: 2026-01-21
- 生成スクリプト: `scripts/analyze_deltae_v3rig_sweep.py`
- 生成物: `results/deltae_v3rig_sweep_2026-01-21_v02_analysis.md`, `results/deltae_v3rig_sweep_2026-01-21_v02_mode_summary.csv`, `results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv`, `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv`

## KPIサマリ
- 完走: RX/TXSD 各50（欠損0）  
  参照: `data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02/manifest.csv`
- RX 0行: OFFのみ一致（OFF 10/10, ON 0/40）  
  参照: `results/deltae_v3rig_sweep_2026-01-21_v02_rx_zero_by_mode.csv`

### モード別（mean±std）
| モード | n | E_total (mJ) | E_per_adv (µJ) | PDR | RSSI median (dBm) |
| --- | --- | --- | --- | --- | --- |
| OFF | 10 | 15755.413±16.483 | - | - | - |
| 100 | 10 | 19121.022±1237.185 | 32136.160±2079.297 | 0.933±0.042 | -43.90±0.70 |
| 500 | 10 | 17270.260±228.245 | 143918.830±1902.046 | 0.923±0.030 | -43.50±0.81 |
| 1000 | 10 | 16848.659±133.481 | 276207.520±2188.219 | 0.934±0.035 | -43.10±0.30 |
| 2000 | 10 | 16830.542±63.117 | 542920.710±2036.040 | 0.942±0.038 | -44.00±0.77 |

参照: `results/deltae_v3rig_sweep_2026-01-21_v02_mode_summary.csv`

### ΔE（E_on − E_off, Welch 95% CI）
| モード | ΔE_mJ | 95% CI | Cohen's d |
| --- | --- | --- | --- |
| 100 | 3365.609 | [2432.674, 4298.544] | 3.649 |
| 500 | 1514.847 | [1342.561, 1687.133] | 8.881 |
| 1000 | 1093.247 | [992.286, 1194.207] | 10.906 |
| 2000 | 1075.129 | [1026.821, 1123.437] | 22.112 |

参照: `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv`

## 再現手順（コマンド）
1. `python scripts/analyze_deltae_v3rig_sweep.py --run-dir data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02 --out-dir results`
2. 95% CI / ΔE は `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv` を確認

## 状態（draft/frozen/obsolete）
- frozen

## 関連リンク
- 解析メモ: `results/deltae_v3rig_sweep_2026-01-21_v02_analysis.md`
- 図: `results/deltae_v3rig_sweep_2026-01-21_v02_plot_e_total_mJ.png`, `results/deltae_v3rig_sweep_2026-01-21_v02_plot_deltaE_mJ.png`, `results/deltae_v3rig_sweep_2026-01-21_v02_plot_pdr.png`, `results/deltae_v3rig_sweep_2026-01-21_v02_plot_rssi_median.png`
- 作業ログ: `logs/worklog_2026-01-21_sd.txt`

## 更新履歴（YYYY-MM-DD）
- 2026-01-21 作成
