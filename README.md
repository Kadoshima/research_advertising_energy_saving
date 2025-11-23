# research_advertising-energy_saving

## エネルギー評価の前提
- 指標: ΔE/adv = (E_on − P_off × T_on) / N_adv。P_off は OFF 試行の平均電力（E_off / T_off）から算出し、T_on に時間スケールを合わせて差し引く。
- ON: 1 trial で ADV を 300 回送出する設計（adv_count は TXSD ログの #summary を真値として使用）。
- OFF: 60 s 固定窓（必要に応じて 120 s まで延長可）で P_off を推定。P_off_trial の median±3MAD を外れ値判定とし、manifest の include=false/high_baseline_outlier で管理する。

## 主なスクリプト
- エネルギー差分（時間スケール吸収・manifest尊重）: `scripts/compute_delta_energy_off.py`
- OFF 健全性チェック（P_off と MAD 外れ値表示）: `scripts/check_units_off.py`
- PDR 結合（TXSD+RX を join、正式指標=PDR_ms=rx_unique/(ms_rx/interval)）: `scripts/compute_pdr_join.py`（`--dedup-seq` で mfd seq 去重）

## 実験ログの配置
- ON: `data/実験データ/研究室/row_1120/TX`（TXSD）, `.../row_1120/RX`
- OFF: `data/実験データ/研究室/row_1123_off/TX`
