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

`TX_BLE_Adv_CCS_Mode.ino` の `RUN_MODE` を設定:
- `MODE_FIXED_100`: 100ms固定（比較用）
- `MODE_FIXED_2000`: 2000ms固定（比較用）
- `MODE_CCS`: CCS時系列に従う

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

## セッション選択ガイド

| Session | Subject | CCS Mean | Transitions | 特徴 |
|---------|---------|----------|-------------|------|
| 01 | 06 | 0.90 | 13 | 遷移少・安定 |
| 02 | 08 | 0.86 | 32 | バランス良好 |
| 05 | 07 | 0.87 | 51 | 遷移多め |
| 10 | 10 | 0.85 | 66 | 遷移最多 |

推奨: まずsession_01で動作確認、次にsession_02/10で多様なパターンを検証

---

## 注意事項

1. **BLE interval変更時の挙動**: `adv->stop()/start()` でわずかなギャップが発生する可能性あり
2. **セッション長**: mHealthデータ制約により10分（600秒）固定
3. **閾値**: θ_high=0.90, θ_low=0.80（2025-11-27調整済み）

---

*Last updated: 2025-11-28*
