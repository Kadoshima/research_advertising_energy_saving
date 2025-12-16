# uccs_d3_scan70（D3: scan duty を 90%→70% に落として適応性確認）

- 目的: `scan90`（良条件）で強い `Fixed500` が崩れる条件を作り、`Policy(100↔500)` が **必要時だけ100msに寄って耐える**ことを示す。
- スコープ: **S4のみ**（差が出やすい）
- 条件: `Fixed100 / Fixed500 / Policy(U+CCS, 100↔500)` × `n=3`
- RX設定: scan70%（interval=100ms, window=70ms）

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

