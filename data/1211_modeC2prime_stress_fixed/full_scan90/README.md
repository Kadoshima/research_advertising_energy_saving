# 1211_modeC2prime_stress_fixed / full_scan90

scan duty を 90%（SCAN_INTERVAL=100ms, SCAN_WINDOW=90ms）に上げたストレス固定フルセット。S1/S4 × {100,500,1000,2000}ms の8本。

## トライアル対応
- S1: 042(100ms), 043(500ms), 044(1000ms), 045(2000ms)
- S4: 046(100ms), 047(500ms), 048(1000ms), 049(2000ms)

## RX/TX 設定
- RX: `RX_ModeC2prime_1210` with SCAN_INTERVAL=100ms, SCAN_WINDOW=90ms (passive scan), buf=512, flush=500ms
- TX: `TX_ModeC2prime_1210_flash_stress` (S1/S4 × 100/500/1000/2000, REPEAT=1)
- TXSD: `TXSD_ModeC2prime_1210`

## ファイル
- RX: `full_scan90/RX/rx_trial_042..049.csv`
- TXSD: `full_scan90/TX/trial_048_on..055_on.csv`
- manifest: `full_scan90/manifest.csv`

## 解析コマンド
```bash
python3 scripts/analyze_stress_causal_real.py \
  --rx-dir data/1211_modeC2prime_stress_fixed/full_scan90/RX \
  --txsd-dir data/1211_modeC2prime_stress_fixed/full_scan90/TX \
  --manifest data/1211_modeC2prime_stress_fixed/full_scan90/manifest.csv \
  --truth-dir Mode_C_2_シミュレート_causal/ccs \
  --truth-map data/1211_modeC2prime_stress_fixed/full_scan90/manifest.csv \
  --out results/stress_causal_real_summary_1211_stress_full_scan90.csv
```
- per-trial: `..._full_scan90.csv`
- 集約: `..._modes_scan90.csv`, `..._agg_scan90.csv`, `..._agg_enriched_scan90.csv`

## 簡易サマリ（pdr_unique）
- S1: 100ms 0.80 / 500ms 1.0 / 1000ms 1.0 / 2000ms 1.0
- S4: 100ms 0.81 / 500ms 1.0 / 1000ms 1.0 / 2000ms 1.0
  - Pout/TL は100msでまだ大きめ（例: S1 Pout1s=0.10, S4 Pout1s≈0.305）。2000msは Pout1s≥0.5 が理論下限。

補足: scan50版の結果は `results/*_scan50.csv` にアーカイブ済み。比較表は `results/compare_scan50_vs_scan90_stress_fixed.csv`（pdr改善が視覚化できるテキストバー `..._pdr.txt` もあり）。
