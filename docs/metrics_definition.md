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
- 下限について: interval=2000ms, τ=1s の場合、受信100%でも遅延は [0, 2s] に分布するため **Pout(1s) の理論下限は 0.5**。実機でこれを上回る分が「追加ロス/空白」に相当。

## EFFECTIVE_LEN / 末端遷移
- TX は `EFFECTIVE_LEN=6352` ステップ（約10.6分）でクランプ。  
- truth も同じ長さにクリップして末端遷移のズレを防ぐ。  
- abort試行（短時間）は manifest から除外する。

## ファイル
- per-trial: `results/stress_causal_real_summary_1211_stress_full.csv`（pdr_raw/pdr_unique/TL/Pout/E/Power）  
- per-trial抜粋: `results/stress_causal_real_summary_1211_stress_modes.csv`  
- 集約: `results/stress_causal_real_summary_1211_stress_agg.csv`（mean/median/std）  
- 比較: `results/compare_real_vs_sim_stress_fixed.csv`（PDR近似マッチで実測vsシミュ）

## 補足
- RX FW は一部 `RX_ModeC2prime_1202` ログが混在。解析時は manifest で trialごとに明示。  
- 2000ms は Pout/TL が大きく揺れるため、複数trialで平均・分散を見ること。  
- エネルギー: TXSD summary の `E_per_adv_uJ`, `E_total_mJ` を使用。平均電力は `E_total_mJ / duration`.
