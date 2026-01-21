# deltae_session_check

## 目的/範囲
- セッション冒頭の15秒ON-only健全性チェックを標準化する。
- 混雑/低混雑の2条件を必ず記録し、PDR低下の要因を分離する。

## 入力データ（出所/版/行数/SHA256）
- 出所: TX/RX/TXSDのシリアルログ（チェック実行時に生成）。
- 版: n/a
- 行数/SHA256: `logs/session_checks/manifest.csv` に記録。

## 出力物（生成日/生成スクリプト）
- 生成日: 2026-01-19
- 生成スクリプト: `scripts/session_ononly_check.py`
- 出力: `logs/session_checks/manifest.csv` と `logs/session_checks/serial_*_ononly_check_*.txt`

## 再現手順（コマンド）
- 混雑条件のチェック:
  - `python scripts/session_ononly_check.py --condition crowded --session-id 2026-01-19_crowded`
- 低混雑条件のチェック:
  - `python scripts/session_ononly_check.py --condition low --session-id 2026-01-19_low`
- 判定閾値を使う場合（根拠を明記）:
  - `python scripts/session_ononly_check.py --condition crowded --session-id 2026-01-19_crowded --name-hit-min <N> --mfd-hit-min <M>`

## 状態（draft/frozen/obsolete）
- draft

## 関連リンク
- `esp32_firmware/20260115_deltae_v3rig_sweep/TX_DeltaE_Sweep/TX_DeltaE_Sweep.ino`
- `esp32_firmware/20260115_deltae_v3rig_sweep/RX_DeltaE_Sweep/RX_DeltaE_Sweep.ino`
- `esp32_firmware/20260115_deltae_v3rig_sweep/TXSD_DeltaE_Sweep/TXSD_DeltaE_Sweep.ino`
- `logs/session_checks/manifest.csv`

## 更新履歴（YYYY-MM-DD）
- 2026-01-19: 初版（セッション健全性チェックの手順と記録先を追加）。
