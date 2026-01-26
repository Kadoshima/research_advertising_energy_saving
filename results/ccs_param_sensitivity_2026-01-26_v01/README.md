# CCSパラメータ感度（alpha, W）シミュレーション

- 生成日時: 2026-01-26 (JST)
- 生成スクリプト: `scripts/ccs_param_sensitivity.py`
- 実行コマンド: `python scripts/ccs_param_sensitivity.py`
- 位置づけ: 既存のCCS時系列（mHealth由来のTFLite推論ログ）を用いたシミュレーション。実測データの再取得は行っていない。

## 入力データ

- 入力パス: `data/ccs_sequences/subject*_ccs.csv`
- 内容: `timestamp_ms,u,s,ccs,interval_ms,pred_label,true_label_4`
- SHA256:

```
E4475B5EC8128EBE81A84D6C8D68C599DFFF4C953D1D145762B9564C404E180E  subject01_ccs.csv
06DA8B1CA67E168800DF46145D8315F967269D0A646A0952FFD175D55BCAD5E2  subject02_ccs.csv
B9F95C457D787B938920010194E61E81B3490654D1D77C3FD6EFEE5EEE5D64E9  subject03_ccs.csv
FED9ACCE36712B52DEB2856AD1074D4D8231905713B304984211259110E06E32  subject04_ccs.csv
8C929400AA41CCD6888B372ECA182809B2583A5A6EABFF8D542111C7AA2BFF31  subject05_ccs.csv
ECD1C2879927B993AAD62AB727F5BF810DA464C4A4F2CCCBC1793B797C6A67E5  subject06_ccs.csv
F9E92E6E7E0E561E879B6072F4048C4A54BB6391E6DCB65B73D4EF9B36F03E06  subject07_ccs.csv
7088F388D9F451C2306D82DE4BB37948D2296DCB361772C8AFB2CBD7C4921B2D  subject08_ccs.csv
1D95B314609938CDB8F136DC399160645C21C0C8E69B1A35B9439C888231FCEE  subject09_ccs.csv
436B08FB838CDC50AB0D4E910AFDDF3E463355305ABD2F7E0D662C44A536920F  subject10_ccs.csv
```

## パラメータ設定

- alpha: {0.6, 0.7, 0.8}
- W: {3, 5, 7} （安定度Sの窓長）
- 閾値: theta_low=0.80, theta_high=0.90
- ヒステリシス: 0.05
- 最小滞在時間: 2.0 s

## 出力

- `summary_by_subject.csv`: 被験者ごとの集計
- `summary_overall.csv`: 全被験者の集計（n_windows=6768）
- `summary_delta_vs_base.csv`: 基準 (alpha=0.7, W=5) からの差分

## 主要な観測値（summary_overall.csv より）

基準 (alpha=0.7, W=5) の集計:

- ccs_mean=0.88169
- ccs_std=0.15433
- switch_rate=0.08008
- share_100=0.25325
- share_500=0.09309
- share_2000=0.65366

パラメータ範囲内の全体レンジ:

- switch_rate: 0.068558〜0.083333
- share_100: 0.229758〜0.280437
- share_500: 0.076241〜0.105201
- share_2000: 0.642583〜0.665041
- ccs_mean: 0.868818〜0.896206
- ccs_std: 0.137962〜0.170512

数値の参照元は `results/ccs_param_sensitivity_2026-01-26_v01/summary_overall.csv`。
