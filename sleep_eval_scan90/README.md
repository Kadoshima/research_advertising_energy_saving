# Sleep効果比較（scan90相当, 100ms vs 2000ms, sleep ON/OFF）

## 目的
- 最短で「sleepが効いて平均電力が下がるか」を確定する。
- オフライン評価用の固定メトリクス（scan90）を、sleep有/無で取り直す前の健全性チェック。

## ディレクトリ
- src/tx : TXファーム（基準は modeC2prime TX 1210）。
- src/txsd : 電力ロガ（TXSD, 1210）。
- src/rx : RXロガ（1210）。
- metrics/ : 計測結果CSVを置く（例: sleep_off_scan90_100ms.csv など）。
- plots/ : 波形・要約図。
- logs/ : 実験メモ・rawログ。

## 配線（最低限）
- GNDは全機器で共有。
- SYNC: TX GPIO25 → RX GPIO26 / TXSD GPIO26（現行コードのデフォルト）。
- （任意）TICK: TX GPIO27 → TXSD GPIO33（adv_count用。ただしsleep比較ステップ1ではTX側TICK出力を無効化推奨）。
  - もし配線を「同じGPIO番号同士（25→25）」で組んでいる場合は、`src/rx` と `src/txsd` の `SYNC_IN` を 25 に揃える。

## 実験デザイン（ステップ1: ダミー広告で sleep 効果最大を確認）
- 条件: 2×2 = {interval ∈ {100ms, 2000ms}} × {sleep OFF, sleep ON}（4条件）。
- ペイロード: 固定内容でOK（seqカウンタのみ）。HAR推論・U/CCS計算・センサ常時サンプリングは **無効化** する。
- 禁止: 遷移多いラベル列、頻繁なSerial print、余計な周期タスク。
- 成功判定: 2000ms+sleep ON で avg_power (または E_total/dur) が明確に低下。下がらなければ sleep 設定/PM lock/周辺周期タスクを疑う。

## 重要な注意（単位と「本当にその間隔か」）
- BLEのinterval/windowは実装によって **0.625ms単位** で解釈されることがあるため、`src/rx` は ms→0.625ms の変換を入れて設定している（例: 100ms→160, 90ms→144）。
- `src/tx` は「CPU側で100msごとにpayload更新する」のではなく、`setMinInterval/setMaxInterval` により **広告間隔をcontrollerに設定**している（sleep比較では周期起床を増やす処理が入ると結果が汚れるため）。
- `src/tx` は trial 開始/終了で `adv->start()` / `adv->stop()` と SYNC を揃える（trial外の余計な広告＝余計な消費を混ぜない）。

## 4条件を「1回の実行で」取る（sleep_eval TX）
- `src/tx` の sleep_eval 用TXは、以下の4条件を順に回す（`N_CYCLES>=2` を推奨、合計>=5分）。
  - (A) 100ms × sleep OFF（cond_id=1, label=I100_OFF）
  - (B) 100ms × sleep ON（cond_id=2, label=I100_ON）
  - (C) 2000ms × sleep OFF（cond_id=3, label=I2000_OFF）
  - (D) 2000ms × sleep ON（cond_id=4, label=I2000_ON）
- TXSDは、trial開始直後のTICKパルス数（=cond_id）を `PREAMBLE_WINDOW_MS` 内で数えて、ファイル名とmetaに反映する。
- RXは、受信したManufacturerDataのlabel（I100_OFF等）を `# condition_label=...` としてファイル先頭に書く。

## よくあるハマり（SDエラーが出る）
- `src/tx` の sleep_eval 用TXは **SDを使わない**。起動ログに `"[TX] SD init FAIL"` が出る場合、別の古いTX（SDラベル読み込み版）をフラッシュしている可能性が高い。
  - 正しいTXスケッチ: `sleep_eval_scan90/src/tx/TX_ModeC2prime_1210/TX_ModeC2prime_1210.ino`（または同内容の `sleep_eval_scan90/src/tx/TX_ModeC2prime_1210.ino`）
  - 正しいTXは BLE名が `TX_SLEEP_EVAL`、ManufacturerDataが `0000_I100_OFF` 等（条件でラベルが変わる）。

## 実験デザイン（ステップ2: 代表負荷1本で現実確認）
- 条件: 2000msで sleep ON/OFF だけを最小で撮る（必要なら100msも）。
- 追加負荷: ラベル列に合わせたペイロード更新 or HAR推論（本番想定）。sleep効果が縮むかを定量化。

## 記録フォーマット（例）
- metrics/
  - sleep_off_scan90_100ms.csv
  - sleep_on_scan90_100ms.csv
  - sleep_off_scan90_2000ms.csv
  - sleep_on_scan90_2000ms.csv
- plots/
  - power_wave_sleep_on_2000ms.png
  - summary_bar_sleep_onoff.png
- logs/
  - worklog_YYYYMMDD_sleep.txt（JSTで条件/機材/設定を明記）

## 備考
- 平均電力がフラットな場合、sleepが効いていない可能性が高い。sleep有効化後に固定メトリクスを撮り直し、オフライン評価のテーブルを差し替える想定。

## 取得データ（2025-12-13）
- 生データ: `sleep_eval_scan90/data/`（100ms/2000ms）
- 集計: `sleep_eval_scan90/analysis/summarize_txsd_power.py`
- 出力:
  - `sleep_eval_scan90/metrics/txsd_power_trials.csv`（trial単位）
  - `sleep_eval_scan90/metrics/txsd_power_summary.csv`（interval別の平均/分散）
  - `sleep_eval_scan90/plots/txsd_power_summary.png`（図）
