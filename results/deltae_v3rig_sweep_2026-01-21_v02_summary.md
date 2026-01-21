# ΔE v3rig sweep まとめ (deltae_v3rig_sweep_2026-01-21_v02)

## 生成情報
- 生成日: 2026-01-21
- 生成スクリプト: `scripts/analyze_deltae_v3rig_sweep.py`
- 参照データ: `data\実験データ\研究室\deltae_v3rig_sweep_2026-01-21_v02`

## 収集状況
- RX: 50 files (0行=10)
- TXSD: 50 files

## モード別サマリ（mean±std）
- 詳細: `results/deltae_v3rig_sweep_2026-01-21_v02_mode_summary.csv`

## ΔE（E_on − E_off）
- OFF平均E_total_mJ: 15755.413
- 100ms: ΔE_mJ=3365.609 (n=10)
- 500ms: ΔE_mJ=1514.847 (n=10)
- 1000ms: ΔE_mJ=1093.247 (n=10)
- 2000ms: ΔE_mJ=1075.129 (n=10)

## PDR/RSSI
- PDR/RSSIのモード別集計は `results/deltae_v3rig_sweep_2026-01-21_v02_mode_summary.csv` を参照

## 備考
- RX 0行ファイルは主にOFFモードと一致する可能性が高い（trial一覧で要確認）
- 95% CIは `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv` を参照（t分布/正規性仮定）
