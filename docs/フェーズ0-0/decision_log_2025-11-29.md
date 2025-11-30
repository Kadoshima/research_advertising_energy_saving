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
- Phase 0-0のベースラインデータ (P_off=22.106mW, ΔE/adv=2256.82µJ) は参考値として保持するが、正式な比較は再計測データで実施

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
| RX_BLE_to_SD.ino | `1bfad7c308146d3c2554413f854f72381c36182ed49954926a211e688f29c097` |

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

**注**: baseline_on と ccs_mode の RX_BLE_to_SD.ino は同一ファイル

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

## 9. 関連ドキュメント

- `esp32_firmware/docs/実験装置仕様書_v2.md` - 本ログに基づく更新版仕様書
- `docs/フェーズ0-0/実験装置最終仕様書.md` - 旧版（v1.0、参照用として保持）
