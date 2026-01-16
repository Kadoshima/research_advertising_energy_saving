# deltae_v3rig_sweep 2026-01-16 v01

- **目的/範囲**: ΔE sweep（TX serial無しでRX/TXSDログを回収・整理）
- **入力データ**:
  - **source_dir**: `D:\logs`
  - **serial_log**: `-`
- **出力物**（生成日/生成スクリプト）: 2026-01-16 / `scripts/collect_sweep_run.py`
- **再現手順（コマンド）**:
  - `python scripts/collect_sweep_run.py --serial-log "-" --source-dir "D:\logs" --date 2026-01-16 --slug deltae_v3rig_sweep --version v01`
- **状態**: draft
- **関連リンク**:
  - `scripts/sweep_status.py`（完走判定）
- **更新履歴**:
  - 2026-01-16: 初版（ログ抽出→必要csvのみ回収、manifest生成）
- 2026-01-16: 追記回収（serial_log=-）
