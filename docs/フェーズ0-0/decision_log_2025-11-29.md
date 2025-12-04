# ESP32ファームウェア 意思決定ログ (2025-11-29)

## 1. ディレクトリ構成の再編成

### 背景
- 従来の `esp32/`, `esp32_sweep/` ディレクトリ構成では、ON/OFF/CCSモードの区別が不明確
- コードの最新版管理が困難

### 決定事項
`esp32_firmware/` を新設し、以下の3分割構成を採用:

```
esp32_firmware/
├── baseline_on/      # BLE広告ON計測用
│   ├── TX_BLE_Adv.ino         # Node1: BLE TX + INA219
│   ├── TXSD_PowerLogger.ino   # Node2: Power logger (SD)
│   └── RX_BLE_to_SD.ino       # Node3: BLE RX logger (SD)
├── baseline_off/     # BLE広告OFF計測用 (ベースライン電力)
│   ├── TX_BLE_OFF.ino         # Node1: BLE無効, INA219のみ
│   └── TXSD_PowerLogger.ino   # Node2: Power logger (SD)
├── ccs_mode/         # CCS動的インターバル制御用
│   ├── TX_BLE_Adv_CCS_Mode.ino
│   ├── TXSD_PowerLogger_CCS_Mode.ino
│   ├── RX_BLE_to_SD.ino
│   └── ccs_session_data.h     # 生成されたセッションデータ
└── README.md
```

### 理由
- 計測モード別に明確に分離
- 各モードで必要なファームウェアが一目瞭然
- 新規作業者でも迷わない構成

---

## 2. INA219配線の修正

### 問題現象 (2025-11-29 作業者確認)
- 外部電源(PMM25-1TR)の電流表示が不安定 (0.02〜0.11A で変動)
- ESP32のビルド/フラッシュ時にリセットループ発生
- 再接続/再起動で一時的に安定することもあった

### 原因推定 (ChatGPT診断 + 作業者検証)
INA219のVccをVin-（負荷側）から分岐して供給していた可能性:
- ESP32起動時の突入電流でVin-側の電圧が降下
- INA219のVcc電圧も連動して低下
- INA219が不安定動作 → I2C通信エラー → ESP32リセット
- 悪循環でブラウンアウトリセットループ

**注記**: 修正前の配線状態はコード上の記録がなく、作業者の口頭確認に基づく。

### 修正前の配線 (推定・NG)
```
外部3.3V ─→ INA219 Vin+ ─→ INA219 Vin- ─┬→ ESP32 3V3
                                         └→ INA219 Vcc (NG: 負荷側からの分岐)
```

### 修正後の配線 (OK)
```
外部3.3V ─┬→ INA219 Vin+ ─→ INA219 Vin- ─→ ESP32 3V3
          └→ INA219 Vcc (OK: 安定電源に直結)
```

### 結果 (作業者確認: 「安定した！」)
- 電流表示が安定
- ビルド/フラッシュ時のリセットループ解消
- 計測値の信頼性向上

**注記**: 修正前後の定量的比較データ（電流値ログ等）は取得していない。上記は作業者の主観的報告に基づく。将来同様の問題が発生した場合のデバッグ資料として、修正前のデータ取得を推奨。

### 影響
- 配線修正前後で計測条件が異なるため、ON/OFF両方の再計測が必要
- Phase 0-0のベースラインデータ (P_off=22.106mW, ΔE/adv=2256.82µJ) は参考値として保持するが、正式な比較は再計測データ（v3 rig, Mode A/B/C…）で実施。旧数値は歴史的参照にとどめる。

---

## 3. マルチトライアル対応

### 背景
- 単一トライアルでは統計的信頼性が不足
- 平均値・標準偏差の算出には複数回計測が必須

### TX_BLE_OFF.ino (baseline_off)
マルチトライアルループを実装:
- `N_TRIALS = 10` (10回のトライアル)
- `TRIAL_DURATION_MS = 60000` (60秒/トライアル)
- `GAP_BETWEEN_TRIALS_MS = 5000` (5秒間隔)
- 総実行時間: 約11分 (60s × 10 + 5s × 9)

### TX_BLE_Adv.ino (baseline_on)
既存実装を確認・維持:
- `N_TRIALS = 10` (10回のトライアル)
- `N_ADV_PER_TRIAL = 300` (300回広告/トライアル)
- `ADV_INTERVAL_MS = 100` (変更可能: 100/500/1000/2000)
- `GAP_BETWEEN_TRIALS_MS = 5000` (5秒間隔)

**注意: トライアル長はintervalにより変動**:
| ADV_INTERVAL_MS | トライアル長 | 備考 |
|-----------------|-------------|------|
| 100 ms | 30 s | 300 × 0.1s |
| 500 ms | 150 s (2.5 min) | 300 × 0.5s |
| 1000 ms | 300 s (5 min) | 300 × 1.0s |
| 2000 ms | 600 s (10 min) | 300 × 2.0s |

**ベースライン（OFF）との比較方法**:
- OFF計測は60秒固定（トライアル長 = 60s）
- ON計測はinterval依存（30s〜600s）
- ΔE/adv算出時:
  ```
  ΔE/adv = (E_on - P_off × T_on) / N_adv

  E_on  : ON計測の総エネルギー [mJ]
  P_off : OFF計測の平均電力 [mW] ← 60s固定から算出
  T_on  : ON計測の時間 [s] ← interval依存
  N_adv : 広告回数 = 300 (固定)
  ```
- P_offは「電力」（時間あたりのエネルギー消費率）として扱うため、T_onを掛けることでOFF相当エネルギーを正しく推定
- よってOFF/ONのトライアル長が異なっても比較は妥当

### TXSD_PowerLogger.ino
- SYNC信号の立ち上がり/立ち下がりでトライアル開始/終了を検出
- TXの複数トライアルに自動追従（変更不要）

---

## 4. 再計測計画

配線修正後の計測順序:
1. OFF計測 (BLE無効ベースライン) → P_off算出
2. ON計測 (全interval自動実行)

### TX_BLE_Adv.ino 自動実行機能 (2025-11-29 実装)

マルチinterval自動実行を実装。手動でADV_INTERVAL_MSを書き換える必要なし:

```cpp
static const uint16_t intervals[]      = {100, 500, 1000, 2000};  // 自動遷移
static const uint8_t  trialsPerGroup[] = {10,  10,  5,    5};     // グループ別トライアル数
static const uint8_t  N_GROUPS         = 4;
static const uint8_t  START_GROUP_INDEX = 0;  // 開始グループ (0-3で指定可能)
```

| Group | Interval | Trials | 1トライアル長 | グループ所要時間 |
|-------|----------|--------|--------------|-----------------|
| 0 | 100 ms | 10 | 30 s | ~6 min |
| 1 | 500 ms | 10 | 150 s | ~27 min |
| 2 | 1000 ms | 5 | 300 s | ~27 min |
| 3 | 2000 ms | 5 | 600 s | ~52 min |
| **合計** | - | **30** | - | **~112 min** |

中断時は`START_GROUP_INDEX`を変更して途中再開可能。

---

## 5. UARTボーレート変更 (2025-11-29 追記)

### 問題
- 230400 bps でデータ化け発生（µA列に記号混入: `05"400`, `06#100` など）
- 約90%のサンプルがパース不可

### 原因
- 高ボーレートでのビット化け（配線長・ノイズ）

### 対策
- 全ファームウェアのUARTボーレートを **230400 → 115200** に変更
- 変更ファイル:
  - `baseline_off/TX_BLE_OFF.ino`
  - `baseline_off/TXSD_PowerLogger.ino`
  - `baseline_on/TX_BLE_Adv.ino`
  - `baseline_on/TXSD_PowerLogger.ino`

### 結果
- データ化け解消、parse_drop=0 達成

---

## 6. ハードウェア確認事項

### 使用ボード
- **ESP32-WROVER-E (ESP32-DevKitC-VE)** - Espressif純正
- PSRAM搭載のため通常のWROOMより消費電力が高い

### INA219シャント抵抗
- **R100 (0.1Ω)** を確認
- `setCalibration_16V_400mA()` で正しくキャリブレーション

### 電流計測値の差異
| 測定源 | 電流 | 備考 |
|--------|------|------|
| 外部電源表示 | 40 mA | 参考値 |
| INA219読み取り | 56 mA | 約16mAの差あり |

相対比較（ON-OFF）では相殺されるため、ΔE/adv算出には問題なし。

---

## 7. ファイルハッシュ (SHA256)

計算日時: 2025-11-29 (SYNC修正・マルチinterval自動実行実装後)

### baseline_on/
| ファイル | SHA256 |
|----------|--------|
| TX_BLE_Adv.ino | `4653cba23efd9d575e6420857a452dfc7e701ad043a0b92cd0a703f34355536a` |
| TXSD_PowerLogger.ino | `88380db88e2fc1b8ddd7d63f23492caad2300f61f4e0ffc20d50871197f37a12` |
| RX_BLE_to_SD.ino | `1e3bf8fce99a8a91944b70ecf5ec90a18c60cfc4a1bbd0953c330b1989320b46` (2025-11-30 バッファリング実装)|

### baseline_off/
| ファイル | SHA256 |
|----------|--------|
| TX_BLE_OFF.ino | `c212e8b8550b8468d6cde64248d02a33fa6baf91c7d83f616cf0ff3b359cf989` |
| TXSD_PowerLogger.ino | `952811247ec79b0495ffa3e589a1811f9a6efea826e88b41dba7ebc9da24499e` |

### ccs_mode/
| ファイル | SHA256 |
|----------|--------|
| TX_BLE_Adv_CCS_Mode.ino | `959f134ecde8551c9abcf796c51aeaf396ba3ac81390dd9c06bf18dc7e450998` |
| TXSD_PowerLogger_CCS_Mode.ino | `0e6da19c0a2ef6513bdb9683909665c14fa2ca0565c6c89c5bdc945abd6e3cb5` |
| RX_BLE_to_SD.ino | `1bfad7c308146d3c2554413f854f72381c36182ed49954926a211e688f29c097` |
| ccs_session_data.h | `6224539c62880a4d71950dd4c909136c1bd01d2303bc335519296f93b1bdc7c8` |

**注**: baseline_on/RX_BLE_to_SD.ino は2025-11-30にUSE_SYNC_END=true修正。ccs_mode版は旧ハッシュのまま。

---

## 8. SYNC信号の修正 (2025-11-29 追記)

### 問題
ON計測時にTXSDのトライアルが5msで終了してしまう:
```
[PWR] end trial=1 t=5ms N=0 E=0.000mJ (ON)
```

一方、RXは正常に60秒動作:
```
[RX] summary trial=1 ms_total=60060, rx=496, rate_hz=8.26
```

### 原因
- **TX側**: `startTrial()`で100msパルスのみ出力し、その後SYNC=LOWになっていた
- **TXSD側**: SYNC=LOWを検出するとendTrial()を呼ぶ設計
- 結果: 100ms後に即終了

### 修正
`baseline_on/TX_BLE_Adv.ino` の `startTrial()` を変更:

**修正前:**
```cpp
// 100msパルスのみ（trial中はLED/SYNCを常時OFFにする）
syncStart();
delay(100);
syncEnd();
```

**修正後:**
```cpp
// トライアル開始: SYNC=HIGH維持（endTrial()でLOWにする）
syncStart();
```

### 動作
- `startTrial()`: SYNC=HIGH（維持）
- トライアル中: SYNC=HIGH継続
- `endTrial()`: SYNC=LOW

これによりTXSDはトライアル全体を正しくログ記録できる。

---

## 10. フェーズ0-0データの信頼性検証 (2025-11-30 追記)

### 背景

2025-11-30の再計測データ（row_1130_on + row_1129_off）とフェーズ0-0データ（row_1120 + row_1123_off）を比較したところ、大きな乖離を発見。

### 比較結果

| 指標 | フェーズ0-0 | 再計測(2025-11-30) | 比率 |
|------|------------|-------------------|------|
| P_off | 22.1 mW | **183.0 mW** | **8x** |
| mean_i (OFF) | 5.6 mA | 56.3 mA | **10x** |
| mean_i (ON 100ms) | 13.4 mA | 68.8 mA | **5x** |
| mean_i (ON 500ms) | 12.3 mA | 62.0 mA | **5x** |
| mean_i (ON 1000ms) | 12.6 mA | 61.1 mA | **5x** |
| mean_i (ON 2000ms) | 12.6 mA | 60.6 mA | **5x** |

### フェーズ0-0データの問題点

#### OFFデータ (row_1123_off)

```
# diag, samples=75, rate_hz=1.25, mean_v=3.284, mean_i=5.554, mean_p_mW=18242.0
# diag, dt_ms_mean=797.253, dt_ms_std=1159.943, dt_ms_min=154, dt_ms_max=7390, parse_drop=91121
```

- **parse_drop=91,121**: 期待サンプル数の99%以上がパース失敗
- **samples=75**: 60秒×100Hz=6000期待に対し、わずか75サンプル
- **rate_hz=1.25**: 本来100Hzのはずが1.25Hz
- **原因**: 230400bpsのUARTデータ化け（`%`, `#`, `&` 混入）

#### ONデータ (row_1120)

```
# diag, samples=2213, rate_hz=99.99, mean_v=3.301, mean_i=13.468, mean_p_mW=44456.0
# diag, dt_ms_mean=10.001, dt_ms_std=2.911, dt_ms_min=0, dt_ms_max=121, parse_drop=0
```

- **parse_drop=0** だが、raw dataには `05&100`, `07#400` など化け文字が混入
- **mean_i=13.4mA**: ESP32+BLE ONで期待される60-70mAに対し異常に低い
- **推定原因**:
  1. 化けた値が解析に含まれた（部分的に数字が読めるケース）
  2. INA219の接続位置またはシャント抵抗の違い

### 再計測データ (2025-11-30) の品質

| ファイル | samples | parse_drop | rate_hz |
|----------|---------|------------|---------|
| row_1129_off | ~5980 | **0** | 100 Hz |
| row_1130_on | ~2200-59000 | **0** | 100 Hz |

- 全トライアルで parse_drop=0
- サンプリングレート 100Hz 安定
- mean_i 値がESP32の仕様と一致（56-69mA）

### 結論

**フェーズ0-0のデータ（row_1120, row_1123_off）は信頼性が低く、破棄を推奨。**

| 問題 | 影響 |
|------|------|
| UARTデータ化け (230400bps) | P_off, ΔE/advの計算基盤が不正確 |
| 低い電流値 (5-13mA vs 56-69mA) | 測定系自体に問題があった可能性 |
| OFFの91% parse_drop | 統計的に無意味なサンプルサイズ |

### 新ベースライン値 (row_1130_on + row_1129_off)

| 指標 | 値 | 備考 |
|------|-----|------|
| P_off | 183.05 ± 0.22 mW | 10トライアル平均 |
| mean_i (OFF) | 56.30 ± 0.04 mA | BLE無効時のidle電流 |
| ΔE/adv 100ms | 4,318 µJ | |
| ΔE/adv 500ms | 10,841 µJ | |
| ΔE/adv 1000ms | 19,003 µJ | |
| ΔE/adv 2000ms | 35,205 µJ | |

**注意**: ΔE/advがintervalに比例して増加するのは、BLE有効化によるidle電力増加（~5-13mA）を反映。純粋な広告送信コストではなく、BLEスタック維持コストを含む。

### PDR (Packet Delivery Rate)

| Interval | Trials | RX count (avg) | PDR |
|----------|--------|----------------|-----|
| 100ms | 10 | 103.5 | 0.345 |
| 500ms | 10 | 227.0 | 0.757 |
| 1000ms | 6 | 220.8 | 0.736 |
| 2000ms | 4 | 261.5 | 0.872 |

**計測環境**: RX側もESP32（RX_BLE_to_SD.ino）でパッシブスキャン。Androidスマホは未使用。

**100msのPDR低下について**:
- 100ms interval (10Hz送信) ではRX ESP32のスキャン処理が追いつかない可能性
- NimBLE/BLEスタックのスキャンウィンドウ設定（SCAN_MS=50）との兼ね合い
- 長いintervalほどPDRが高いのは、受信側の処理余裕が増えるため

### RXファームウェア バッファリング実装 (2025-11-30)

100ms PDR低下（0.345）の原因がSD書き込みボトルネックと判明したため、バッファリングを実装。

**変更内容** (`RX_BLE_to_SD.ino` → `RX_BLE_to_SD_SYNC_C`):

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| SD書き込み | コールバック内で即時 | リングバッファ経由 |
| バッファサイズ | なし | 512エントリ (~24KB) |
| フラッシュ間隔 | 毎回 | 500ms毎 |
| オーバーフロー検出 | なし | `buf_overflow` カウント |

**リングバッファ構造**:
```cpp
struct RxEntry {
  uint32_t ms;      // タイムスタンプ
  int8_t rssi;      // RSSI
  char addr[18];    // MACアドレス
  char mfd[8];      // MFD ("MFxxxx")
};
static RxEntry rxBuf[512];
```

**期待効果**:
- コールバック処理時間: ~10-20ms → ~1µs（SD書き込みなし）
- 100ms interval でも取りこぼしが大幅減少

**確認ポイント**:
- `buf_overflow` が0であることを確認
- PDRが改善されているか（目標: 0.8以上）

### 解析スクリプト修正 (2025-11-30)

`scripts/analyze_baseline_v2.py` に以下の修正を適用:

1. **interval推定**: meta行の`adv_interval_ms`が固定値(100)の場合、`ms_total/adv_count`から推定
2. **mean_p_mW補正**: ファームウェアバグで1000倍されている場合の自動補正（>10000mWなら/1000）
3. **PDR計算修正**: `rx_count / 300` 固定（interval非依存）

---

## 11. 関連ドキュメント

- `esp32_firmware/docs/実験装置仕様書_v2.md` - 本ログに基づく更新版仕様書
- `docs/フェーズ0-0/実験装置最終仕様書.md` - 旧版（v1.0、参照用として保持）
- `results/baseline_analysis_1130.md` - 2025-11-30 再計測の解析結果
