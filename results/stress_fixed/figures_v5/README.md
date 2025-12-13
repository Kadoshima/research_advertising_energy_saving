# stress_fixed figures v5

- 生成日: 2025-12-13
- 生成スクリプト: `scripts/plot_stress_fixed_figures_v5.py`
- 入力（v5: TL/Pout 時間同期あり）
  - scan90: `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v5.csv`
  - scan50: `results/stress_fixed/scan50/stress_causal_real_summary_1211_stress_agg_enriched_scan50_v5.csv`

## 出力
- `fig1_scan90_metrics.png`
  - scan90（S1/S4 × interval）で `pdr_unique`, `pout_1s`, `tl_mean_s`, `E_per_adv_uJ`, `avg_power_mW` を並列に可視化。
- `fig3_scan50_vs_scan90_pdr_unique.png`
  - scan50（点）と scan90（線）で `pdr_unique` を比較（特に 100ms の差が見やすい）。

## 実行メモ（キャッシュ問題の回避）
Fontconfig / Matplotlib のキャッシュ書き込みが制限される環境では、以下のように `XDG_CACHE_HOME` と `MPLCONFIGDIR` を作業ディレクトリ配下に向ける。

```bash
XDG_CACHE_HOME=results/stress_fixed/figures_v5/.cache \
MPLCONFIGDIR=results/stress_fixed/figures_v5/.mpl_cache \
MPLBACKEND=Agg \
.venv/bin/python scripts/plot_stress_fixed_figures_v5.py --out-dir results/stress_fixed/figures_v5
```

