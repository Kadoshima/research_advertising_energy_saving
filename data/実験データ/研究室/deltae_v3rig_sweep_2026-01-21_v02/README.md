# ΔE v3rig sweep 2026-01-21 v02

## 目的/範囲
- ΔE v3rig sweepの生ログ回収（OFF + 100/500/1000/2000ms, 60s×10）
- RX/TXSDの受信・電力ログの健全性確認

## 入力データ（出所/版/行数/SHA256）
- 出所: SDカード `D:\logs` からコピー
- 版: 2026-01-21_v02
- 行数: RX 50 files / 7,521 rows、TXSD 50 files / 297,001 rows（data rowsのみ）
- SHA256: `RX_SHA256.txt`, `TXSD_SHA256.txt`
- シリアルログ: `logs/serial_capture/serial_COM8_20260121_001546_v02_run2.log`, `logs/serial_capture/serial_COM9_20260121_001546_v02_run2.log`

## 出力物（生成日/生成スクリプト）
- 生成日: 2026-01-21
- 生成物: `RX/*.csv`, `TXSD/*.csv`, `manifest.csv`, `RX_SHA256.txt`, `TXSD_SHA256.txt`
- 生成スクリプト: `scripts/serial_capture.py` + SDからのコピー

## 再現手順（コマンド）
1. `python scripts/serial_capture.py --ports COM8,COM9 --baud 115200 --out-dir logs/serial_capture --duration 0 --tag v02_run2`
2. SD挿入後、ログからファイル名を抽出してコピー
   - 例: `rg -o "pwr_[0-9]+_[0-9a-f]+_sweep\.csv" logs/serial_capture/serial_COM8_20260121_001546_v02_run2.log | sort -Unique`
   - 例: `rg -o "rx_[0-9]+_[0-9a-f]+\.csv" logs/serial_capture/serial_COM9_20260121_001546_v02_run2.log | sort -Unique`

## 状態（draft/frozen/obsolete）
- draft

## 関連リンク
- 作業ログ: `logs/worklog_2026-01-21_sd.txt`
- ファームウェア: `esp32_firmware/20260115_deltae_v3rig_sweep/TX_DeltaE_Sweep/TX_DeltaE_Sweep.ino`, `esp32_firmware/20260115_deltae_v3rig_sweep/RX_DeltaE_Sweep/RX_DeltaE_Sweep.ino`, `esp32_firmware/20260115_deltae_v3rig_sweep/TXSD_DeltaE_Sweep/TXSD_DeltaE_Sweep.ino`
- シリアルログ: `logs/serial_capture/serial_COM8_20260121_001546_v02_run2.log`, `logs/serial_capture/serial_COM9_20260121_001546_v02_run2.log`
- 解析結果: `results/deltae_v3rig_sweep_2026-01-21_v02_analysis.md`
- 集計CSV: `results/deltae_v3rig_sweep_2026-01-21_v02_mode_summary.csv`, `results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv`, `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv`
- 図: `results/deltae_v3rig_sweep_2026-01-21_v02_plot_e_total_mJ.png`, `results/deltae_v3rig_sweep_2026-01-21_v02_plot_deltaE_mJ.png`, `results/deltae_v3rig_sweep_2026-01-21_v02_plot_pdr.png`, `results/deltae_v3rig_sweep_2026-01-21_v02_plot_rssi_median.png`

## 更新履歴（YYYY-MM-DD）
- 2026-01-21 作成
