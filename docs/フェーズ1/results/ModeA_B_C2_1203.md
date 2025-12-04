# Mode A/B/C2 結果サマリ (2025-12-03)

## 概要
- Mode A (真OFF): Deep Sleep無期限、記録はTXSDのみ時間終了。
- Mode B (待機ベース): Light Sleep + 低頻度処理 (~25Hz)、BLEオフ。記録はTXSDのみ時間終了。
- Mode C2 (HAR OFF + 固定BLE広告): interval={100,500,1000,2000}、N_adv=300、TXSDはTICKで終了、RXはseqロガー。
- 解析スクリプト: `scripts/analyze_1202.py` を `--txsd-dir ... --rx-file ... --p-off ...` で実行。

## データ配置
- Mode A: `data/1202配線変更後/Mode_A/1203/` (例: trial_006_offA.csv, trial_007_offA.csv)
- Mode B: `data/1202配線変更後/Mode_B/1203/` (trial_005_offB.csv ほか)
- Mode C2 (HAR OFF): `data/1202配線変更後/1m_on_1202/` 
  - TXSD: `.../TX/trial_###_on.csv`
  - RX:   `.../RX/rx_trial_001.csv`

## Mode A (真OFF下限)
- trial_006_offA.csv, trial_007_offA.csv (各300 s)
- 平均: P_off_A ≈ 11.8 mW, I_off_A ≈ 3.51 mA, E_total ≈ 3.53 J (300 s)
- データ品質: rate=100 Hz, parse_drop=0

## Mode B (待機ベース)
- trial_005_offB.csv 〜 trial_008_offB.csv (各300 s)
- 平均（4本）: P_off_B ≈ 22.9 mW, I_off_B ≈ 6.83 mA, E_total ≈ 6.86 J (300 s)
  - うちV=3.35 V系3本平均: P ≈ 23.2 mW, I ≈ 6.95 mA
- データ品質: rate=100 Hz, parse_drop=0

## Mode C2 (HAR OFF + 固定広告) - P_off_B=23 mW を控除
- 解析コマンド例:
  ```bash
  python3 scripts/analyze_1202.py \
    --txsd-dir "data/1202配線変更後/1m_on_1202/TX" \
    --rx-file "data/1202配線変更後/1m_on_1202/RX/rx_trial_001.csv" \
    --p-off 23.0
  ```
- 区間平均 (30 trials, adv_count=300固定):
  | Interval | E/adv (mJ) | PDR | ΔE/adv (µJ, P_off=23mW) |
  |----------|------------|-----|-------------------------|
  | 100ms | 21.04 | 0.849 | 18,733 |
  | 500ms | 94.60 | 0.872 | 83,174 |
  | 1000ms | 186.87 | 0.891 | 163,977 |
  | 2000ms | 368.68 | 0.887 | 323,020 |

- 個別トライアル例 (抜粋):
  - 100ms: ms_total≈29.8 s, mean_p≈208 mW, ΔE/adv≈18.4〜20.1 mJ
  - 500ms: ms_total≈148.8 s, mean_p≈190 mW, ΔE/adv≈82.5〜85.4 mJ
  - 1000ms: ms_total≈297.7 s, mean_p≈188 mW, ΔE/adv≈162.7〜166.1 mJ
  - 2000ms: ms_total≈595.5 s, mean_p≈185–186 mW, ΔE/adv≈322–323 mJ

## メモ
- ΔE/adv は Mode B 待機電力23 mWで控除。Mode A下限11.8 mWで控除するとさらに小さくなる。
- RXはseqロガーでPDR算出（trial_001で30試行復元）。TXSDはTICK=300で終了し ms_total は壁時計差分。

