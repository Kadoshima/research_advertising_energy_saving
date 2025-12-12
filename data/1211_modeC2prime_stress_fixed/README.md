# 1211_modeC2prime_stress_fixed

ストレスラベル（S1/S4）で固定間隔 {100, 500, 1000, 2000} ms を実機取得したセット。RX/TXSD ログと manifest、解析結果の置き場。

## 実験条件
- ラベル: `labels_stress.h` の SESSIONS_STRESS（S1: idx=0, S4: idx=3）
- TX: `esp32_firmware/1210/modeC2prime_tx_stress/TX_ModeC2prime_1210_flash_stress` 固定間隔版
- RX: `esp32_firmware/1210/modeC2prime_rx/RX_ModeC2prime_1210`
- TXSD: `esp32_firmware/1210/modeC2prime_txsd/TXSD_ModeC2prime_1210`
- 環境: E1（距離/干渉は従来と同条件、SYNC/TICK配線あり）

## データ構成
- `full/RX` / `full/TX` : ストレス固定の正式データ
  - S1: 018(100), 019(500), 020(1000), 030(2000), 031(2000)  ※2000msは再取得2本
  - S4: 022(100), 023(500), 024(1000), 025(2000)           ※025は再取得分
- `full/manifest.csv` : trial ↔ session ↔ interval ↔ truth を定義
- 旧途中計測（harf/harf2000/2000s4）は参考。解析は `full/` を使用。
- 現状の解析結果（scan duty 50%）は `results/stress_causal_real_summary_1211_stress_*_scan50.csv` にアーカイブ。scan90% の再取得セットで `_scan90` を出力予定。

## 解析
```bash
python3 scripts/analyze_stress_causal_real.py \
  --rx-dir data/1211_modeC2prime_stress_fixed/full/RX \
  --txsd-dir data/1211_modeC2prime_stress_fixed/full/TX \
  --truth-dir Mode_C_2_シミュレート_causal/ccs \
  --truth-map data/1211_modeC2prime_stress_fixed/full/manifest.csv \
  --out results/stress_causal_real_summary_1211_stress_full.csv
```
集約表: `results/stress_causal_real_summary_1211_stress_modes.csv`（8行）。PDRは TXSD adv_count でクランプ済み。`pdr_raw` は重複を含み >1 になることがあるので QoS には `pdr_unique` を使用。

## 実測サマリ（pdr_unique基準, retake反映）
- S1 (平均/中央値は agg を参照; 2000ms は2本の平均):
  - 100ms: PDR 0.20, Pout1s 0.05, TL_mean 6.1s, E_per_adv ≈20.1kµJ
  - 500ms: PDR 0.50, Pout1s 0.05, TL_mean 6.16s, E_per_adv ≈99.9kµJ
  - 1000ms: PDR 0.50, Pout1s 0.22, TL_mean 7.96s, E_per_adv ≈199.3kµJ
  - 2000ms (030/031): PDR ≈0.88, Pout1s ≈0.89, TL_mean ≈33.3s (揺れ大), E_per_adv ≈361.6kµJ, avg_power ≈181mW
- S4:
  - 100ms: PDR 0.20, Pout1s 0.085, TL_mean 4.03s, E_per_adv ≈20.0kµJ
  - 500ms: PDR 0.50, Pout1s 0.057, TL_mean 2.03s, E_per_adv ≈100.8kµJ
  - 1000ms: PDR 0.50, Pout1s 0.255, TL_mean 8.84s, E_per_adv ≈198.9kµJ
  - 2000ms (025): PDR 0.86, Pout1s 0.674, TL_mean 16.6s, E_per_adv ≈359.2kµJ, avg_power ≈180mW

備考:
- 2000ms は Pout/TL が顕著に悪化し、S1/S4 とも揺れが大きい。2000msは複数 trial で平均/分散を見ること。
- RX FW ログは `RX_ModeC2prime_1202` を含む（混在時は manifest で明示し、再解析時に確認）。

備考: 2000msは Pout/TL が大きく悪化し、S4 で PDR も低下。PDRは dup受信の影響を受けるため、ユニーク基準を参照すること。データ欠落時は manifest で明示的に除外する。
