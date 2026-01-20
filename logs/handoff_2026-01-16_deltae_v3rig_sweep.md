# 引継ぎ: ΔE v3rig sweep (RX/TXSD/TX) — 2026-01-16

## 状況サマリ（結論）

- **データ回収・整理パイプライン**は整備済み（`D:\logs` → プロジェクト内に v01/v02…で保存、`manifest.csv` 生成、完走判定 `sweep_status.py`）。
- **v02（コード修正後の取り直し）**は **trial数は期待どおり50/50で完走**しているが、**RXのCSVがほぼ全てヘッダのみ（ADV行がほぼ入ってない）**ため、**受信が成立していない**（またはフィルタで落ちている）。
- **TXSD**はtrialによって `adv_count` が **0** になるケースがあり、**TICK配線/割り込みが不安定**な可能性が高い（E/adv やモード推定に影響）。

## 重要な根拠（runtime evidence）

### v02 sweep_status 結果

- 期待: 50 trial（OFF + 100/500/1000/2000ms 各10回）
- 実際: RX=50 / TXSD=50（完走）
- ただし RX推定intervalは全てNone（=受信間隔が取れていない/受信がほぼ無い）

### v02 RXの中身（実ファイル確認）

- `data/実験データ/研究室/deltae_v3rig_sweep_2026-01-16_v02/RX/` の `rx_*.csv` 50本中、**ADV行が入っているのは1本だけ（1行）**という集計結果（Pythonでカウント）。
  - 例: `rx_02148634_6778f04f.csv` はヘッダ+metaのみ
  - 例: `rx_00000879_5f8ff215.csv` は ADV 1行のみ

### v01について（参考）

- v01は混在（周回/複数run）で **RX/TXSDとも442本**まで膨れた。解析上 `likely_loop_or_reset=true`。
- v01もRXはほぼ空（ヘッダのみが大半）。

## 現在のデータ格納先（プロジェクト内）

- v01（混在あり）: `data/実験データ/研究室/deltae_v3rig_sweep_2026-01-16_v01/`
  - `RX/` 442, `TXSD/` 442, `manifest.csv`, `README.md`
- v02（取り直し、50本）: `data/実験データ/研究室/deltae_v3rig_sweep_2026-01-16_v02/`
  - `RX/` 50, `TXSD/` 50, `manifest.csv`, `README.md`

## 変更点（コード/スクリプト）

### RXファーム（rx=0 切り分け強化）

- 対象:
  - `esp32_firmware/20260115_deltae_v3rig_sweep/RX_DeltaE_Sweep/RX_DeltaE_Sweep.ino`
  - `esp32_firmware/20260114_deltae_v3rig/RX_DeltaE_V3/RX_DeltaE_V3.ino`
  - `esp32/RX_BLE_to_SD_SYNC_B.ino`
- 内容:
  - **ESP32 Arduino Core 3.x**互換（`String`/`std::string`）。
  - **MFD抽出**: `MFxxxx` は payload 内探索。ただし **offset 0/2限定**（誤ロック低減）。
  - **診断カウンタ**: `cbTotal`, `cbNoMfd`, `cbMfdBad/Fail`, `cbAddrMismatch`, `cbBufDrop`, `firstAddr`, `firstMfd` を endTrial で出す。
  - **SYNC安定化**: polling+debounce、dual SYNC_IN(26)/ALT(25)、ログ抑制 `DBG_LEVEL`。

### 収集/判定スクリプト

- `scripts/collect_sweep_run.py`
  - シリアルログ内の `/logs/<filename>` を抽出して **必要CSVだけ**をコピー。
  - `--serial-log -` で **stdin/clipboard**入力対応。
  - `manifest.csv` は **マージ（追記回収で上書き破壊しない）**。
- `scripts/sweep_status.py`
  - `--find <dir_name>` を追加（Windowsで日本語パスが `Path.exists()` で死ぬケース回避）。
  - NDJSONで `.cursor/debug.log` に根拠（trial数、品質カウンタ等）を出す。

## 実行コマンド（再現/運用）

### 1) SDログ回収（例: v02）

```powershell
Get-Clipboard -Raw | python scripts/collect_sweep_run.py --serial-log - --source-dir "D:\logs" --date 2026-01-16 --slug deltae_v3rig_sweep --version v02
```

### 2) sweep完走判定（例: v02）

```powershell
python scripts/sweep_status.py --find deltae_v3rig_sweep_2026-01-16_v02 run_20260116_v02
```

## 現状の主要課題

1. **RXがほぼ空**（CSVは作るがADVが入らない）
   - 可能性:
     - 本当に広告が見えていない（電源/距離/スキャン停止/干渉）
     - コールバックは来ているが `noMfd/mfdBad/addrMis` で捨てている
   - ここは **RXシリアルの `AGENT RX diag` が必要**（CSVだけでは原因分類できない）
2. **TXSDのadv_count=0が混入**
   - TICK配線なし/断線/ノイズ/割り込み不安定/プル設定など
   - `TXSD_DeltaE_Sweep.ino` は `TICK_IN=33` のRISING割り込み
3. **周回/複数run混在（v01）**
   - データ整理は v01/v02 で回避する方針

## 次にやるべき最短手順（推奨）

1. **RXの診断ログを取る（最優先）**
   - TXを ON(100ms) のみで 60s 動かす（sweep不要）
   - RXシリアルから `"[AGENT] RX diag ..."` を1回分取得
   - `cbTotal` が増えるか、`cbNoMfd/mfdBad/addrMis` のどれが支配的かで原因確定
2. TXSDの `adv_count=0` の再現条件を確認
   - TICK配線の有無（TX 27 → TXSD 33）
   - `tick_raw` 列が増えるか（ログ上の `tick_raw` を確認）

## 注意点

- `.cursor/debug.log` は環境により削除がブロックされることがある（protected）。ログクリーンが必要なら別runIdで区別する運用。

## 関連ログ

- 作業ログ: `logs/worklog_2026-01-16_deltae_v3rig_rx_txsd_reflect.txt`
