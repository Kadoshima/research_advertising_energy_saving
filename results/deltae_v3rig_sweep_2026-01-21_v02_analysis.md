# ΔE v3rig sweep 解析メモ (2026-01-21_v02)

## 生成情報
- 生成日: 2026-01-21
- 生成スクリプト: `scripts/analyze_deltae_v3rig_sweep.py`
- 参照データ: `data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02`

## 出力物
- `results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv`
- `results/deltae_v3rig_sweep_2026-01-21_v02_mode_summary.csv`
- `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv`
- `results/deltae_v3rig_sweep_2026-01-21_v02_rx_zero_check.csv`
- `results/deltae_v3rig_sweep_2026-01-21_v02_rx_zero_by_mode.csv`
- `results/deltae_v3rig_sweep_2026-01-21_v02_plot_e_total_mJ.png`
- `results/deltae_v3rig_sweep_2026-01-21_v02_plot_deltaE_mJ.png`
- `results/deltae_v3rig_sweep_2026-01-21_v02_plot_pdr.png`
- `results/deltae_v3rig_sweep_2026-01-21_v02_plot_rssi_median.png`
- `results/deltae_v3rig_sweep_2026-01-21_v02_summary.md`

## 健全性チェック
- RX 0行はOFFのみで一致（OFF=10/10, ON=0/40）: `results/deltae_v3rig_sweep_2026-01-21_v02_rx_zero_by_mode.csv`
- RX/TXSDの欠損なし（50/50）: `data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02/manifest.csv`

## ΔE / PDR / RSSI 概要
- ΔE_mJ（E_on − E_off）: 100ms=3365.609, 500ms=1514.847, 1000ms=1093.247, 2000ms=1075.129（参照: `results/deltae_v3rig_sweep_2026-01-21_v02_summary.md`）
- PDR mean: 100ms=0.933, 500ms=0.923, 1000ms=0.934, 2000ms=0.942（参照: `results/deltae_v3rig_sweep_2026-01-21_v02_mode_summary.csv`）
- RSSI median mean (dBm): 100ms=-43.90, 500ms=-43.50, 1000ms=-43.10, 2000ms=-44.00（参照: `results/deltae_v3rig_sweep_2026-01-21_v02_mode_summary.csv`）
- 95% CI / 効果量: `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv`（t分布/Welch、正規性仮定）

## 備考
- ΔEやPDRの再計算は `results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv` を起点に再現可能
- 図は `results/deltae_v3rig_sweep_2026-01-21_v02_plot_*.png` を参照
