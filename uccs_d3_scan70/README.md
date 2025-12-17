# uccs_d3_scan70（D3: scan duty を 90%→70% に落として適応性確認）

- 目的: `scan90`（良条件）で強い `Fixed500` が崩れる条件を作り、`Policy(100↔500)` が **必要時だけ100msに寄って耐える**ことを示す。
- スコープ: **S4のみ**（差が出やすい）
- 条件: `Fixed100 / Fixed500 / Policy(U+CCS, 100↔500)` × `n=3`
- RX設定: scan70%（interval=100ms, window=70ms）

## 結論（レター用の置き方）

scan70 / S4 では **Fixed500 がQoSで崩れる**一方、`Policy` は **Fixed500よりQoSを改善しつつ、Fixed100より低電力**という「中間解」を維持できた。

- Fixed500 がQoSで崩れる: `pout_1s = 0.2846 ± 0.0614`
- Policy は Fixed500 より改善: `pout_1s = 0.0894 ± 0.0373`
- Policy は Fixed100 より省電力（ただし Fixed500 より高電力）
  - power: Fixed100 `209.9±0.5` → Policy `202.1±0.1`（`-7.8 mW`, 約 `-3.7%`）
  - Fixed500 `189.5±0.5` → Policy（Fixed500比 `+12.6 mW`）

制約として `δ=0.1`（例: `Pout(1s) ≤ 0.1`）を置くと、scan70では

- Fixed500 は **不適**（`pout_1s > 0.1`）
- Fixed100 は **適**だが高電力
- Policy は **適**かつ Fixed100 より低電力

→ D3の価値は「悪条件で Fixed500 が使えない状況を作って、policy が“100ms張り付きではない中間解”として意味を持つ」ことを実機で示せた点。

## ディレクトリ構成

- `uccs_d3_scan70/src/`
  - `tx/` : `TX_UCCS_D3_SCAN70`（Arduino）
  - `rx/` : `RX_UCCS_D3_SCAN70`（Arduino）
  - `txsd/`: `TXSD_UCCS_D3_SCAN70`（Arduino）
- `uccs_d3_scan70/data/01/`
  - `RX/` と `TX/`（TXSDのSD `/logs/` を `TX/` にコピー）

## 配線（D2/D4と同じ）

- TX GPIO25 → RX GPIO26（SYNC）
- TX GPIO25 → TXSD GPIO26（SYNC）
- TX GPIO27 → TXSD GPIO33（TICK）

## 実行手順（ME）

1. Arduino IDEで書き込み（フォルダ名=スケッチ名）
   - TX: `uccs_d3_scan70/src/tx/TX_UCCS_D3_SCAN70/TX_UCCS_D3_SCAN70.ino`
   - RX: `uccs_d3_scan70/src/rx/RX_UCCS_D3_SCAN70/RX_UCCS_D3_SCAN70.ino`
   - TXSD: `uccs_d3_scan70/src/txsd/TXSD_UCCS_D3_SCAN70/TXSD_UCCS_D3_SCAN70.ino`
2. 自動で `S4 × (Fixed100 → Fixed500 → Policy) × 3回` が流れる。
3. SDカードの `/logs/` を回収し、以下へコピー
   - RX側: `uccs_d3_scan70/data/01/RX/`
   - TXSD側: `uccs_d3_scan70/data/01/TX/`

## 期待される結果（成功条件）

- `Fixed500` の `pout_1s` / `tl_mean_s` が scan90 より悪化
- `Policy` が `Fixed500` よりQoSを改善しつつ、`Fixed100` より平均電力が下がる（または同程度）

## 出力（run01）

- 集計: `uccs_d3_scan70/metrics/01/summary.md`
- 図: `uccs_d3_scan70/plots/d3_01_power_vs_pout.png`

### share100 推定の注意（scan70では重要）

scan70では 100ms 側の取りこぼしが増えるため、`share100_time_est (RX tags)` は **系統的に過小評価**になりやすい。

そのため本実験では、`TXSD avg_power_mW` から **power-mix** で `share100_power_mix` を推定して併記している。

- 推定式（S4_policy）: `share100_power_mix ≈ (P_policy - P_500) / (P_100 - P_500)`
- run01の結果: `share100_power_mix≈0.618`（RX tags推定 `≈0.420` より大きい）

