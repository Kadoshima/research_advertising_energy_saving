# ΔE再検証 v3 rig スケッチ一覧

- 更新日: 2026-01-14
- 目的: Phase0-0 ΔE再検証（v3 rig基準）用の新規スケッチ一式を整理する
- 条件: E2/1m, 60s, N=10, interval=100/500/1000/2000ms

## 配線メモ

- SYNC: TX(25) → TXSD(26) / RX(26)
  - 追記: TX側スケッチで `USE_SYNC_ALT_OUT=true` の場合、GPIO26にもSYNCをミラー出力する（配線の自由度/冗長化）
- TICK: TX(27) → TXSD(33)（USE_TICK_INPUT=true）

## スケッチ（v3 rig基準）

### TX（ON, interval固定）

- `esp32_firmware/20260114_deltae_v3rig/TX_DeltaE_V3_ON_100ms/TX_DeltaE_V3_ON_100ms.ino`
- `esp32_firmware/20260114_deltae_v3rig/TX_DeltaE_V3_ON_500ms/TX_DeltaE_V3_ON_500ms.ino`
- `esp32_firmware/20260114_deltae_v3rig/TX_DeltaE_V3_ON_1000ms/TX_DeltaE_V3_ON_1000ms.ino`
- `esp32_firmware/20260114_deltae_v3rig/TX_DeltaE_V3_ON_2000ms/TX_DeltaE_V3_ON_2000ms.ino`
- `esp32_firmware/20260114_deltae_v3rig/TX_Sync_Toggle/TX_Sync_Toggle.ino`
  - SYNC配線の診断用（GPIO26を0.5秒周期でトグル）

### TX（OFF）

- `esp32_firmware/20260114_deltae_v3rig/TX_DeltaE_V3_OFF/TX_DeltaE_V3_OFF.ino`

### TXSD（Power Logger）

- `esp32_firmware/20260114_deltae_v3rig/TXSD_DeltaE_V3_ON/TXSD_DeltaE_V3_ON.ino`
  - `ADV_INTERVAL_MS` はメタ情報用。必要なら interval に合わせて更新する
  - CSV先頭列に `prog_id` を付与
  - 追記: 開始側デバウンス（HIGH 100ms）/ユニークファイル名/DBG_LEVEL/`SYNC_IN || SYNC_ALT_IN` 対応
- `esp32_firmware/20260114_deltae_v3rig/TXSD_DeltaE_V3_OFF/TXSD_DeltaE_V3_OFF.ino`
  - CSV先頭列に `prog_id` を付与
- `esp32_firmware/20260114_deltae_v3rig/TXSD_Sync_Probe/TXSD_Sync_Probe.ino`
  - SYNC配線の診断用（GPIO25/26のレベルを1秒ごとに出力）

### RX（必要時のみ）

- `esp32_firmware/20260114_deltae_v3rig/RX_DeltaE_V3/RX_DeltaE_V3.ino`
  - `ADV_INTERVAL_MS` はPDR目安用。intervalと一致させる
  - CSV先頭列に `prog_id` を付与
- `esp32_firmware/20260114_deltae_v3rig/RX_Diag_Ping/RX_Diag_Ping.ino`
  - シリアル疎通確認用（1秒ごとに `[AGENT] RX_DIAG_PING` を出力）

## 関連ドキュメント

- 計画: `docs/フェーズ0-0/ΔE再検証_2026-01-14/Phase0-0_deltaE_plan_2026-01-14.md`
- v3 rig仕様: `docs/フェーズ0-0/実験装置仕様書_v3.md`
