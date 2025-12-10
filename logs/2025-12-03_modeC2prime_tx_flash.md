# 2025-12-03 作業ログ (Mode C2' TXフラッシュ版)

- 目的: SDなしでラベル再生を行う Mode C2' TX のビルド/配布用に、NimBLE固定・ラベルヘッダ選択方式を整理。

## 実施内容

1. ラベル配列の自動生成スクリプト追加
   - `scripts/gen_labels_header.py` を作成。
   - 例: `python3 scripts/gen_labels_header.py --csv data/ccs_sequences/subject05_ccs.csv --label-col true_label_4 --out esp32_firmware/1202/modeC2prime_tx/labels_generated.h`
   - 出力: `static const char* labels[] ...; static const uint16_t nLabels = N;`

2. subject別ヘッダを一括生成
   - コマンド: `for i in 01..10` を回して `esp32_firmware/1202/modeC2prime_tx/labels_subjects/labels_subjectXX.h` を生成済み。
   - 例: subject05 → nLabels=669。

3. TXフラッシュ版の整備
   - ファイル: `esp32_firmware/1202/modeC2prime_tx/TX_ModeC2prime_1202_flash/TX_ModeC2prime_1202_flash.ino`
   - NimBLEを明示的に使用（ArduinoBLEとの衝突回避）。
   - ラベル配列はヘッダ側のみで定義。多重定義を解消（手書きサンプルを削除）。
   - デフォルトで `labels_subject05.h` を include（別subjectを使う場合は該当行を差し替え）。
   - ADV_MS固定、TICK(27)/SYNC(25)出力、300 advで1トライアル終了。

4. 使い方メモ
   - ラベルを差し替える場合: 冒頭の include を `labels_subjectXX.h` に変更。
   - 任意CSVを使う場合: `scripts/gen_labels_header.py` でヘッダ生成→`#include "labels_generated.h"` に切り替え。
   - TXにSDは不要。TXSD/RXは従来のC2構成で計測可。

## 所感
- SDをTXに載せずとも、フラッシュ埋め込みで十分。NimBLE固定でArduinoBLEとの衝突も解消。
- ラベル切替はヘッダ差し替えで済むため、ビルド手順はシンプル。
