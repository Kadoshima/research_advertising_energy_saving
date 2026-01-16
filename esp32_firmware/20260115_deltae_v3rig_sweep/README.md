# ΔE V3 rig sweep（OFF + ON 100/500/1000/2000ms）一気通貫テスト

- 更新日: 2026-01-15
- 状態: draft

## 目的/範囲

- 目的: 席を外している間に、TXが **OFF→ON(100/500/1000/2000ms)** を自動で順番に実行し、RX/TXSDがSYNCに追従してログを取得できるようにする。
- 範囲: ファームウェア（TX/RX/TXSD）と運用手順。解析は別。

## 入力データ（出所/版/行数/SHA256）

- 出所: 各ESP32のmicroSD `/logs/` に出力されるCSV
  - RX: `rx_*.csv`
  - TXSD: `pwr_*_{off|on}_*.csv`
- 版: 本ディレクトリ配下の `.ino`（RX/TXSDはCSV列`prog_id`で識別）

## 出力物（生成日/生成スクリプト）

- 生成物: SDカード `/logs/` 配下CSV（外部生成）

## 再現手順（コマンド）

- Arduino IDEでそれぞれ書き込み:
  - RX: `esp32_firmware/20260115_deltae_v3rig_sweep/RX_DeltaE_Sweep/RX_DeltaE_Sweep.ino`
  - TXSD: `esp32_firmware/20260115_deltae_v3rig_sweep/TXSD_DeltaE_Sweep/TXSD_DeltaE_Sweep.ino`
  - TX: `esp32_firmware/20260115_deltae_v3rig_sweep/TX_DeltaE_Sweep/TX_DeltaE_Sweep.ino`

## 完了判定（TXのシリアル無しで判定）

- TXをUSB接続していない場合、**RX/TXSDのSDカード `/logs/` のCSVだけ**で完走可否を判定する。
- 手順:
  - SDカードからCSVをPCへコピー（例）:
    - `data/実験データ/研究室/deltae_v3rig_sweep_YYYY-MM-DD/RX/` に `rx_*.csv`
    - `data/実験データ/研究室/deltae_v3rig_sweep_YYYY-MM-DD/TXSD/` に `pwr_*_sweep.csv`
  - 判定コマンド:
    - `python scripts/sweep_status.py data/実験データ/研究室/deltae_v3rig_sweep_YYYY-MM-DD`
  - 出力の見方（目安）:
    - `expected 50` に対して **RX/TXSD とも 50付近**なら完走相当
    - `drops(start_ms)` が >0 や、ファイル数が 50 を大きく超えていれば **周回/リセット**疑い
    - `adv_n<=3` が多い場合は **TICK配線/割り込み系**が怪しい（adv_countは信用しない）

### ビルド注意（text section exceeds の回避）

- もし `text section exceeds available space in board` が出た場合、Arduino IDEの
  `ツール > Partition Scheme` を **`No OTA`** または **`Huge APP`** に変更してください（アプリ領域が増えて収まります）。

## 配線（前提）

- SYNC: TX GPIO25 → RX GPIO26, TXSD GPIO26
- SYNC_ALT（任意）: TX GPIO26 → RX GPIO25, TXSD GPIO25
- TICK: TX GPIO27 → TXSD GPIO33（ON時のみパルス）

## 実行スケジュール（既定）

- 1 trial = 60 s, gap = 5 s
- モード順:
  - OFF
  - ON 100 ms
  - ON 500 ms
  - ON 1000 ms
  - ON 2000 ms
- 各モード10回（合計50 trial、約54分）
- 変更はTX側スケッチの定数で調整

## 関連リンク

- データ整理: `docs/フェーズ2/deltae_v3rig/README.md`
- 既存ファーム: `esp32_firmware/20260114_deltae_v3rig/`

## 更新履歴

- 2026-01-15: sweep用ファーム一式を追加

