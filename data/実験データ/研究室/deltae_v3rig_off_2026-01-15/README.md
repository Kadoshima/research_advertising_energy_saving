# deltae_v3rig_off_2026-01-15（OFF実験データ）

- 更新日: 2026-01-15
- 状態: draft

## 目的/範囲

- 目的: ΔE（ON−OFF）比較のうち、**OFF条件**のRXログとTXSD電力ログを保管する。
- 範囲: 本フォルダは生ログの保管と、整合性（行数/SHA256）の記録のみ。

## 入力データ（出所/版/行数/SHA256）

- 出所: microSD `/logs/`（RX: `rx_*.csv`, TXSD: `pwr_*_off.csv`）
- 版: `esp32_firmware/20260114_deltae_v3rig/`（`PROGRAM_ID`列で識別）
- 行数/SHA256: `manifest.csv` に記録（未記入のままコミットしない）

## 出力物（生成日/生成スクリプト）

- 本フォルダ配下のCSV（外部生成; 生成スクリプトなし）

## 再現手順（コマンド）

- 1) SDカードから以下にコピーしてリネーム:
  - RX → `RX/`
  - TXSD → `TXSD/`
- 2) `manifest.csv`の`sha256`と`rows`を埋める（PowerShell例）:

```powershell
Get-FileHash -Algorithm SHA256 .\RX\rx_trial_001.csv
```

## 関連リンク

- 取り込み手順: `docs/フェーズ2/deltae_v3rig/README.md`

## 更新履歴

- 2026-01-15: フォルダ作成（OFF用）

