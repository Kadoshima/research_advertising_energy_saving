# phase1_e2_baseline_debug_2026-01-22

## 目的/範囲
- Phase 1のE2（高Wi-Fi干渉）環境で、Baseline-Short(100ms) / Baseline-Long(2000ms) を取得するためのTX動作不安定問題を切り分ける
- TXの `SESSION END` が出ない/ログが止まる問題の原因を他AIへ引き継ぐ

## 入力データ（出所/版/行数/SHA256）
- シリアルログ（serial_capture）
  - `logs/serial_capture/serial_COM6_20260122_150906_phase1_e2_ccs_v04.log`
  - `logs/serial_capture/serial_COM8_20260122_150906_phase1_e2_ccs_v04.log`
  - `logs/serial_capture/serial_COM9_20260122_150906_phase1_e2_ccs_v04.log`
- 対象ファーム（TX側）
  - `C:\Users\tp240\Documents\Arduino_MCP_Sketches\TX_BLE_Adv_CCS_Sweep\TX_BLE_Adv_CCS_Sweep.ino`

## 出力物（生成日/生成スクリプト）
- 本README（2026-01-22）

## 実験の狙い（やりたいこと）
- E2環境でBaseline比較を成立させるため、
  - 100ms固定×3試行
  - 2000ms固定×3試行
  を1ブートで回し、RX/TXSDで同時ログ取得する

## 現状のコード変更（TX側）
- ファイル: `C:\Users\tp240\Documents\Arduino_MCP_Sketches\TX_BLE_Adv_CCS_Sweep\TX_BLE_Adv_CCS_Sweep.ino`
- 変更内容（要点）
  - `FW_TAG` を `TX_BLE_Adv_Baseline_E2` に変更
  - `MODE_SEQUENCE` を `{ MODE_FIXED_100, MODE_FIXED_2000 }` に変更
  - `REPS_PER_MODE = 3`（合計6セッション）
  - `SESSION_DURATION_S = 600`（10分）
- MCPでCOM6へアップロード済み

## いま起きている問題
- `SESSION START` は出るが `SESSION END` が出ない
- serial_capture ログの最終更新が 15:09:54 で停止
- TX/RX/TXSDのログにリセットが複数回混在し、どの試行が本番か判別しづらい

## 直近ログの状態（確認済み）
- COM6: `SESSION START (1/6)` のみ
- COM8/COM9: `startTrial` のみ
- `SESSION END` / `endTrial` 未出現

## 想定される原因候補
1) TX側のハングアップ（600s未到達）
2) serial_capture 停止（プロセス or COMハング）
3) 連続リセットによるログ混在

## 再現手順（現状の流れ）
1) `python scripts/serial_capture.py --ports COM6,COM8,COM9 --baud 115200 --out-dir logs/serial_capture --duration 0 --tag phase1_e2_ccs_v04`
2) TX/RX/TXSD をリセット
3) 10分待機（SESSION END を確認）
4) ログ末尾に `SESSION END` / `endTrial` が出ない

## 参考：期待動作
- 10分後にTXが `SESSION END` を出し、GPIO25でENDパルス
- RX/TXSDが `endTrial` を出す
- 5秒gap後に次セッションに進む（合計6セッション）

## 他AIへの質問ポイント
- TXログ停止の原因切り分け（ハング vs serial_capture 停止）
- COM6のserial_captureが止まらない運用（監視方法）
- 1試行だけ確実に取得するための最小手順

## 関連リンク
- `docs/フェーズ1/要件定義.md`
- `docs/フェーズ1/phase1_e2_ccs_2026-01-22/README.md`
- `logs/worklog_2026-01-22_ccs.txt`

## 更新履歴（YYYY-MM-DD）
- 2026-01-22: 初版（Baseline取得トラブルの切り分けメモ）
