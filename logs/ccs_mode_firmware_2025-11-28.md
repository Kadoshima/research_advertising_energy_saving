# CCSモードファームウェア実装ログ (2025-11-28)

## 概要

既存のESP32ファームウェアにCCSモード（T_adv動的変更）機能を追加。

## 変更内容

### 新規作成ファイル

| ファイル | 説明 |
|----------|------|
| `esp32_sweep/TX_BLE_Adv_CCS_Mode.ino` | CCSモード対応TXファームウェア |
| `esp32_sweep/TXSD_PowerLogger_CCS_Mode.ino` | CCSモード対応TXSDファームウェア |
| `esp32_sweep/ccs_session_data.h` | セッションデータ（自動生成） |
| `scripts/convert_session_to_header.py` | CSV→Cヘッダー変換スクリプト |

---

## TX_BLE_Adv_CCS_Mode.ino

### モード選択

```cpp
enum RunMode {
  MODE_FIXED_100,   // 100ms固定
  MODE_FIXED_2000,  // 2000ms固定
  MODE_CCS          // CCS時系列に従って動的変更
};

static const RunMode RUN_MODE = MODE_CCS;
```

### 主な機能

1. **3モード対応**: FIXED_100, FIXED_2000, CCS
2. **CCS時系列埋め込み**: `ccs_session_data.h` を `#include`
3. **1秒解像度でT_adv更新**: `getIntervalForTime(elapsedS)`
4. **BLE interval動的変更**: `adv->stop()` → `setMinInterval/setMaxInterval` → `adv->start()`
5. **拡張UART出力**: `mv,uA,interval_ms` 形式

### セッション制御

- セッション長: 600秒（10分）
- 開始: 100ms SYNCパルス
- 終了: 自動（SESSION_DURATION_S経過後）

### ピン割り当て（既存と同一）

| Pin | 機能 |
|-----|------|
| GPIO25 | SYNC_OUT |
| GPIO27 | TICK_OUT |
| GPIO2 | LED |
| GPIO21/22 | I2C (INA219) |
| GPIO4 | UART TX |

---

## TXSD_PowerLogger_CCS_Mode.ino

### 変更点

1. **パーサー拡張**: `mv,uA` または `mv,uA,interval_ms` を両対応
2. **CSV出力拡張**: `ms,mV,µA,p_mW,interval_ms`
3. **CCS統計追跡**:
   - interval別カウント (100/500/2000ms)
   - interval変更回数

### サマリー出力例

```
# summary, ms_total=600000, adv_count=XXX, E_total_mJ=XXX, E_per_adv_uJ=XXX
# ccs, interval_100ms=157 (26.2%), interval_500ms=14 (2.3%), interval_2000ms=429 (71.5%)
# ccs, interval_changes=13
```

---

## convert_session_to_header.py

### 使用方法

```bash
python3 scripts/convert_session_to_header.py --session 01
```

### 出力例 (session_01)

```
Generated: esp32_sweep/ccs_session_data.h
  Session: 01
  Duration: 600s
  Intervals: 100ms=157, 500ms=14, 2000ms=429
```

### 生成されるヘッダー構造

```cpp
static const char* CCS_SESSION_ID = "01";
static const uint16_t CCS_N_ENTRIES = 600;
static const uint32_t CCS_DURATION_S = 600;

static const uint16_t CCS_INTERVALS[600] = {
     100,  100,  100, ..., 2000, 2000, 2000
};

static inline uint16_t getIntervalForTime(uint32_t elapsed_s);
```

---

## ビルド手順

### 1. セッションヘッダー生成

```bash
cd /Users/kadoshima/Documents/research_advertising-energy_saving
python3 scripts/convert_session_to_header.py --session 01
```

### 2. TXファームウェア設定

`TX_BLE_Adv_CCS_Mode.ino` の定数を編集:

```cpp
// モード選択（27行目付近）
static const RunMode RUN_MODE = MODE_CCS;  // または MODE_FIXED_100, MODE_FIXED_2000

// 条件ID（37行目付近）- ログ識別用
static const uint8_t RUN_GROUP_ID = 5;  // 1=FIXED_100, 2=FIXED_2000, 5=CCS
```

| 実験条件 | RUN_MODE | RUN_GROUP_ID | 備考 |
|----------|----------|--------------|------|
| 固定100ms | MODE_FIXED_100 | 1 | ベースライン比較用 |
| 固定2000ms | MODE_FIXED_2000 | 2 | 省電力上限 |
| CCS制御 | MODE_CCS | 5 | CCS時系列に従う |

**注意**: RUN_GROUP_IDはTXSDログのメタデータに記録されるため、条件に応じて変更すること。

### 3. ビルド・書き込み

Arduino IDE設定:
- Board: ESP32 Dev Module
- Upload Speed: 921600
- Flash Frequency: 80MHz

書き込み順序:
1. TX: `TX_BLE_Adv_CCS_Mode.ino`
2. TXSD: `TXSD_PowerLogger_CCS_Mode.ino`
3. RX: `RX_BLE_to_SD_SYNC_B.ino`（既存のまま）

---

## セッション一覧

全10セッションの統計（ソース: `data/esp32_sessions/session_selection_report.md`）:

| Session | Subject | CCS Mean | CCS Range | Transitions | Score | 100ms% | 500ms% | 2000ms% |
|---------|---------|----------|-----------|-------------|-------|--------|--------|---------|
| 01 | 06 | 0.896 | 0.36-1.00 | 13 | 0.930 | 26.2% | 2.3% | 71.5% |
| 02 | 08 | 0.859 | 0.20-1.00 | 32 | 0.880 | 27.3% | 4.7% | 68.0% |
| 03 | 09 | 0.888 | 0.54-1.00 | 36 | 0.818 | 24.2% | 9.7% | 66.2% |
| 04 | 05 | 0.931 | 0.58-1.00 | 34 | 0.812 | 15.5% | 7.7% | 76.8% |
| 05 | 07 | 0.868 | 0.22-1.00 | 51 | 0.690 | 30.5% | 11.3% | 58.2% |
| 06 | 04 | 0.860 | 0.32-1.00 | 56 | 0.640 | 32.0% | 6.3% | 61.7% |
| 07 | 01 | 0.836 | 0.26-1.00 | 64 | 0.600 | 32.2% | 10.0% | 57.8% |
| 08 | 02 | 0.844 | 0.26-1.00 | 61 | 0.600 | 32.2% | 18.3% | 49.5% |
| 09 | 03 | 0.898 | 0.44-1.00 | 70 | 0.600 | 19.8% | 12.5% | 67.7% |
| 10 | 10 | 0.848 | 0.38-1.00 | 66 | 0.600 | 36.7% | 13.2% | 50.2% |

### 選定基準（`scripts/create_esp32_sessions.py`）

1. 遷移回数が適度（10-30回が理想、スコア加点）
2. 間隔の多様性（100/500/2000msが全て出現）
3. CCS範囲が広い

### 推奨セッション

| 用途 | Session | 理由 |
|------|---------|------|
| 動作確認 | 01 | 遷移少(13回)で安定、スコア最高(0.930) |
| バランス検証 | 02 | 遷移適度(32回)、CCS範囲広い(0.20-1.00) |
| 高遷移検証 | 08 | 500ms比率最高(18.3%)、3区間バランス良好 |
| 極端ケース | 10 | 100ms比率最高(36.7%)、遷移多(66回) |

---

## 注意事項

1. **BLE interval変更時の挙動**: `adv->stop()/start()` でわずかなギャップが発生する可能性あり
2. **セッション長**: mHealthデータ制約により10分（600秒）固定
3. **閾値**: θ_high=0.90, θ_low=0.80（2025-11-27調整済み）

---

## 修正履歴

| 日付 | 内容 |
|------|------|
| 2025-11-28 | 初版作成 |
| 2025-11-28 | 補強: (1) 全10セッションの統計表を追加, (2) 推奨セッションの選定理由を明記, (3) RUN_MODE/RUN_GROUP_ID設定手順を詳細化 |

---

*Last updated: 2025-11-28*
