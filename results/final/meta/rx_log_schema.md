# RXログ仕様（アプリ向け・既存解析互換）

更新日: 2025-12-19

目的: 本リポジトリの既存解析（`uccs_*` の `summarize_*` / outage解析）にそのまま刺さる、受信ログ（CSV）の仕様を固定する。  
新規リポジトリ側でこの仕様どおりに出力すれば、`step_idx` 起点で TL/Pout を復元できる。

---

## 1. 設計方針（研究用途の要点）

- **1広告イベント=1行**（バッチまとめをしない）
- **foreground固定**（バックグラウンドは挙動が変わり得るためB2では原則使わない）
- **重複通知を許可**（同一Peripheralの連続広告を“できるだけ生”で記録）
- **試行メタ（端末/設定/フィルタ/ビルド）をCSV先頭に残す**

---

## 2. ファイル単位（必須）

- 1試行=1ファイル: `rx_trial_XXX.csv`
- 先頭に **コメント行（`# ...`）のメタ** → その後にCSVヘッダ → データ行

例（先頭）:

```
# meta, firmware=RX_UCCS_D4B_SCAN70
# meta, device_model=iPhone13,4
# meta, os=iOS 17.2
# meta, app_version=0.3.1
# meta, scan_interval_ms=100.0
# meta, scan_window_ms=70.0
# meta, allow_duplicates=true
# meta, foreground=true
# meta, filter_addr=e0:5a:1b:15:c4:ca
# meta, filter_name_prefix=TX_
# meta, trial_duration_s=180
# meta, session=S4
# condition_label=P4-03-100
ms,event,rssi,seq,label,addr,mfd
...
```

`condition_label` は「想定条件」のメモ（解析は基本的に各行の `label/mfd` を見るので補助）。

---

## 3. データ行（必須カラム）

既存ログ互換の最小セット（この7列があればOK）。

### 3.1 CSVヘッダ（必須）

- `ms`
- `event`
- `rssi`
- `seq`
- `label`
- `addr`
- `mfd`

### 3.2 各カラム定義（必須）

- `ms`（int推奨）
  - 試行開始を `0ms` とした **相対時刻**（単調増加）
  - 壁時計ではなく **monotonic clock** 推奨
- `event`（string）
  - `ADV` 固定でOK（将来 `SCAN_RSP` 等を増やすなら拡張）
- `rssi`（int, dBm）
  - 受信RSSI（取得不可なら空欄可）
- `seq`（int）
  - TXが送る広告内の連番（重複/欠落検知に利用）
- `label`（string）
  - 解析側がモード判定に使うタグ。既存互換は以下:
    - `F4-<truth_label>-<interval_ms>`（固定）
    - `P4-<truth_label>-<interval_ms>`（policy: U+CCS）
    - `U4-<truth_label>-<interval_ms>`（U-only / CCS-off）
  - 例: `P4-03-100`, `U4-01-500`
- `addr`（string）
  - Peripheral識別子
  - Android: MAC推奨
  - iOS: MACが出ない場合があるため、UUID文字列でも可（ただし同一試行内で一貫していること）
- `mfd`（string）
  - ManufacturerData（生文字列）
  - **必須の互換仕様**: `"<step_idx>_<tag>"` 形式
    - 例: `1128_P4-03-100`
    - `step_idx` は **100msグリッドの整数**（0..1799 等）

---

## 4. `step_idx` と `label` の取り決め（最重要）

### 4.1 `mfd` パース規則（必須）

- `mfd` は必ず `"{step_idx}_{label}"` 形式
- `step_idx` は整数
- `label` は以下の `tag` と同一文字列

### 4.2 `label` パース規則（必須）

- 先頭1文字: `F` / `P` / `U`（mode）
- 形式: `{mode}4-{truth_label}-{interval_ms}`
  - `truth_label`: 2桁を推奨（例: `03`）だが、解析は整数パースできればOK
  - `interval_ms`: 少なくとも `100` と `500`

---

## 5. 推奨の追加カラム（後方互換で追加OK）

- `uuid`（iOSのidentifierなど。`addr`と併存可）
- `tx_power`（取れる場合）
- `adv_raw_hex`（生payload全体HEX）
- `mfd_hex`（ManufacturerDataのみHEX）
- `channel`（取れる場合）
- `is_duplicate`（OS/SDKがduplicateフラグを持つ場合）

---

## 6. ファイル内ルール（地雷回避）

- CSVヘッダはファイル内で1回のみ
- `ms` は単調増加（途中でリセットしない）
- 受信できない区間は **行が無い**だけ（0埋めしない）
- ファイル名 `rx_trial_XXX.csv` と `# meta` の trial_id（書くなら）を一致させる

---

## 7. 既存解析への接続（最小チェック）

- `label` に `P4-` / `U4-` / `F4-` が入る
- `mfd` に `step_idx_` が入る（例: `1128_P4-...`）
- `ms` が 0〜180000ms 程度で増える（180s試行の例）
- `allow_duplicates=true` / `foreground=true` をメタに残す

