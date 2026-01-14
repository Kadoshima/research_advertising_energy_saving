# Phase0-0 ΔE再検証 計画（v3 rig）

- 更新日: 2026-01-14
- 環境: 研究室（E2, 従来条件と同一）
- 距離: 1m
- セッション長: 60 s
- 試行数: 各条件 n=10（ON: 100/500/1000/2000ms, OFF: 10本）

## 1. 目的

- Phase0-0で発生したΔE符号問題をv3 rig基準の再測定で解消する
- ON/OFFの計測系を統一し、ΔE/advの信頼性を回復させる

## 2. ディレクトリ配置（決定）

- 入口（計画・記録）:
  - `docs/フェーズ0-0/ΔE再検証_2026-01-14/`
- 実験コード参照:
  - `esp32_firmware/20260114_deltae_v3rig/README.md`
- 生データ:
  - `data/実験データ/研究室/phase0-0_deltae_v3rig_20260114/`
    - `ON_100ms/`, `ON_500ms/`, `ON_1000ms/`, `ON_2000ms/`, `OFF/`
- 結果:
  - `results/phase0-0/phase0-0_deltae_v3rig_2026-01-14.md`
- 設定（任意）:
  - `configs/phase0-0_deltae_v3rig_2026-01-14.yaml`

## 3. ファイル命名（推奨）

- ON: `trial_001_on.csv` 〜 `trial_010_on.csv`
- OFF: `trial_001_off.csv` 〜 `trial_010_off.csv`

## 4. スケッチ（確定）

- `esp32_firmware/20260114_deltae_v3rig/TX_DeltaE_V3_ON_100ms/TX_DeltaE_V3_ON_100ms.ino`
- `esp32_firmware/20260114_deltae_v3rig/TX_DeltaE_V3_ON_500ms/TX_DeltaE_V3_ON_500ms.ino`
- `esp32_firmware/20260114_deltae_v3rig/TX_DeltaE_V3_ON_1000ms/TX_DeltaE_V3_ON_1000ms.ino`
- `esp32_firmware/20260114_deltae_v3rig/TX_DeltaE_V3_ON_2000ms/TX_DeltaE_V3_ON_2000ms.ino`
- `esp32_firmware/20260114_deltae_v3rig/TX_DeltaE_V3_OFF/TX_DeltaE_V3_OFF.ino`
- `esp32_firmware/20260114_deltae_v3rig/TXSD_DeltaE_V3_ON/TXSD_DeltaE_V3_ON.ino`
- `esp32_firmware/20260114_deltae_v3rig/TXSD_DeltaE_V3_OFF/TXSD_DeltaE_V3_OFF.ino`
- `esp32_firmware/20260114_deltae_v3rig/RX_DeltaE_V3/RX_DeltaE_V3.ino`

## 5. 参照コードの所在

- Mode A〜D系: `esp32_firmware/1202/`
- Mode C2'系: `esp32_firmware/1210/`
- UCCS系: `uccs_d1_scan90/`, `uccs_d2_scan90/`, `uccs_d3_scan70/`, `uccs_d4_scan90/`, `uccs_d4b_scan70/`, `uccs_d4b_scan90/`

## 6. 次アクション

- `data/実験データ/研究室/phase0-0_deltae_v3rig_20260114/` を作成
- `scripts/compute_delta_energy_v3rig.py` で集計し結果を保存
- 記録開始時に worklog へ着手ログを残す
