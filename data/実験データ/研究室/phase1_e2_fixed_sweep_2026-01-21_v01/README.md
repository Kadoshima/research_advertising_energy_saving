# phase1_e2_fixed_sweep 2026-01-21 v01

- **目的/範囲**: ΔE sweep（TX serial無しでRX/TXSDログを回収・整理）
- **入力データ**:
  - **source_dir**: `D:\`
  - **serial_log**: `logs/serial_capture/serial_COM8_20260121_165545_e2_run1.log`
- **出力物**（生成日/生成スクリプト）: 2026-01-21 / `scripts/collect_sweep_run.py`
- **再現手順（コマンド）**:
  - `python scripts/collect_sweep_run.py --serial-log "logs/serial_capture/serial_COM8_20260121_165545_e2_run1.log" --source-dir "D:\" --date 2026-01-21 --slug phase1_e2_fixed_sweep --version v01`
- **状態**: draft
- **関連リンク**:
  - `scripts/sweep_status.py`（完走判定）
- **更新履歴**:
  - 2026-01-21: 初版（ログ抽出→必要csvのみ回収、manifest生成）
- 2026-01-21: 追記回収（serial_log=logs/serial_capture/serial_COM9_20260121_165545_e2_run1.log）
- 2026-01-21: RX missing 4本はready前の`[SD] open FAIL`由来で、今回のtrial=1..15には影響なし（serial log: `logs/serial_capture/serial_COM9_20260121_165545_e2_run1.log`）。
