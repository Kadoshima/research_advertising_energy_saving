# Metrics Definition (ストレス固定 / CCS 評価用)

本ドキュメントでは、実機ログ解析で用いる主要指標の定義を明文化する。PDR/遅延系の解釈がブレないように、分母・分子の取り方や下限値をここで固定する。

## PDR
- `adv_count`: TXSD summary (`# summary` の `adv_count`) を真値とし、RX由来で再計算しない。
- `pdr_raw = rx_count / adv_count`  
  - `rx_count`: RX行数（重複含む）。  
  - `adv_count`: TXSD基準でクランプ（min(rx_count, adv_count) を使う実装）。
- `pdr_unique = rx_unique_seq / adv_count`  
  - `rx_unique_seq`: `seq`（MFD 先頭の数値）でユニーク化した件数。  
  - カバレッジ指標に近い（「広告イベントの何割を一度でも拾えたか」）。  
  - QoS比較にはこちらを使用。  
- 注意: 重複受信が多いと `pdr_raw` は >1 になりうるので、QoS用途には `pdr_unique` を参照する。

## TL / Pout
- 真値: `truth` CSV の `idx,label`（EFFECTIVE_LEN=6352 を基準。末尾遷移が TX 再生範囲外に出ないようクリップ）。  
- 遅延: 各遷移時刻 `t_event` から最初に正しいラベルを観測するまでの時間。  
  - `tl_mean`, `tl_p95`: 遷移ごとの遅延の平均 / 95%点。  
  - `Pout(τ)`: 遷移のうち、遅延 > τ の割合。  

### 時間同期（重要）
TL/Pout は **RXログの `ms` と truth の時間軸が一致している**前提で計算する必要がある。実機では開始タイミングのズレ（例: RX開始が遅れる、TXが先に進む）が入りやすく、ズレを補正しないと **TL/Pout が不自然に小さく見える**（特に長間隔側）ことがある。

本リポジトリでは、固定間隔リプレイ（seqが単調増加）を前提に、次の「定数オフセット」で同期する（`scripts/analyze_stress_causal_real.py` の実装）。

- 各 `seq` の最初の観測時刻を `first_ms(seq)` とする（RXログ由来）。
- 期待される真値時刻は `seq * interval_ms` とみなす。
- `offset_ms = median_{seq>0}( seq*interval_ms - first_ms(seq) )`
- TL/Pout 計算では `ms_aligned = ms + offset_ms` を用いる。

出力CSVでは以下で確認できる。
- `tl_time_offset_ms`: 推定したオフセット（ms）
- `tl_time_offset_n`: 推定に使ったseq数

### 下限（参考）
一般に、τ < interval のとき、受信100%でも遅延の量子化により `Pout(τ)` は 0 にならない（例: interval=2000ms, τ=1s なら 0.5 が目安）。
ただし、実際の `Pout(τ)` の下限は「遷移時刻の分布」と「開始位相」に依存するため、**一律の下限値を前提にせず**、上記の時間同期を行った上で実測値で議論する。

## EFFECTIVE_LEN / 末端遷移
- TX は `EFFECTIVE_LEN=6352` ステップ（約10.6分）でクランプ。  
- truth も同じ長さにクリップして末端遷移のズレを防ぐ。  
- abort試行（短時間）は manifest から除外する。

## ファイル
- scan90（固定フルセット, v5）:
  - per-trial: `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_full_scan90_v5.csv`
  - per-trial抜粋: `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_modes_scan90_v5.csv`
  - 集約: `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_scan90_v5.csv`
  - 集約+派生: `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_agg_enriched_scan90_v5.csv`
  - インデックス: `results/stress_fixed/scan90/index.md`

## 補足
- RX FW は一部 `RX_ModeC2prime_1202` ログが混在。解析時は manifest で trialごとに明示。  
- 2000ms は Pout/TL が大きく揺れるため、複数trialで平均・分散を見ること。  
- エネルギー: TXSD summary の `E_per_adv_uJ`, `E_total_mJ` を使用。平均電力は `E_total_mJ / duration`.
