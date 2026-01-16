# ΔE（ON/OFF）測定（V3 rig）: データ配置・命名・取り込み手順

- 更新日: 2026-01-15
- 状態: draft

## 目的/範囲

- 目的: TX/TXSD/RX（3ノード）で取得したΔE（ON−OFF）比較用ログを、リポジトリ内で再現可能に整理する。
- 範囲: 本READMEは**データの置き場所・命名規約・チェックサム記録**のみを扱う（解析は別途）。

## 入力データ（出所/版/行数/SHA256）

- 出所: 各ESP32のmicroSD `/logs/` に出力されたCSV（RX: `rx_*.csv`, TXSD: `pwr_*_{on|off}.csv`）
- 版: `esp32_firmware/20260114_deltae_v3rig/` の各 `.ino`（`PROGRAM_ID`列で識別）
- 行数/SHA256: 取り込み後に `data/実験データ/研究室/deltae_v3rig_off_2026-01-15/manifest.csv` に記録する

## データの置き場所（あて先）

- OFF: `data/実験データ/研究室/deltae_v3rig_off_2026-01-15/`
  - RXログ: `RX/`
  - TXSDログ: `TXSD/`
- ON: `data/実験データ/研究室/deltae_v3rig_on_YYYY-MM-DD/`（同形式で作成する）

## 再現手順（コマンド）

- SDカードからPCへコピー後、`manifest.csv`のSHA256を埋める（PowerShell例）:

```powershell
Get-FileHash -Algorithm SHA256 .\rx_trial_001.csv
```

## 関連リンク

- ファームウェア: `esp32_firmware/20260114_deltae_v3rig/`
- sweep（一気通貫）: `esp32_firmware/20260115_deltae_v3rig_sweep/README.md`
- フェーズ2索引: `docs/フェーズ2/README.md`

## 更新履歴

- 2026-01-15: OFFデータの配置先と命名、`manifest.csv`記録手順を追加

