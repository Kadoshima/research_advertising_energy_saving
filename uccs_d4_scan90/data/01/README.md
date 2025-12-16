# uccs_d4_scan90 data/01

- run_id: `01`
- 目的: Step D4（U ablation / U-shuffle）S4のみ・scan90で取得
- 取得日: 2025-12-16（JST）
- データ配置:
  - `RX/` : RX SD `/logs/rx_trial_*.csv`
  - `TX/` : TXSD SD `/logs/trial_*.csv`

## メモ（取得時に追記）

- 環境: （例: 研究室/E? 距離/干渉/配置）
- scan duty: 90%（interval=100ms, window=90ms）
- 条件: S4 × {Fixed100, Fixed500, Policy(U+CCS), Ablation(U-shuffle)} × n=3（自動実行）
- firmware:
  - TX: `TX_UCCS_D4_SCAN90`
  - RX: `RX_UCCS_D4_SCAN90`
  - TXSD: `TXSD_UCCS_D4_SCAN90`

