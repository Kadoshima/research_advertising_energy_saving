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

ΔE/adv算出時は広告回数(N_adv=300)で正規化するため、トライアル長の違いは問題にならない。

### TXSD_PowerLogger.ino
- SYNC信号の立ち上がり/立ち下がりでトライアル開始/終了を検出
- TXの複数トライアルに自動追従（変更不要）

---

## 4. 再計測計画

配線修正後の計測順序:
1. OFF計測 (BLE無効ベースライン) → P_off算出
2. ON 100ms (`ADV_INTERVAL_MS = 100`)
3. ON 500ms (`ADV_INTERVAL_MS = 500`)
4. ON 1000ms (`ADV_INTERVAL_MS = 1000`)

### 各計測で変更するパラメータ
| 計測 | ファームウェア | ADV_INTERVAL_MS | RUN_GROUP_ID |
|------|----------------|-----------------|--------------|
| OFF | TX_BLE_OFF.ino | N/A | N/A |
| ON 100ms | TX_BLE_Adv.ino | 100 | 1 |
| ON 500ms | TX_BLE_Adv.ino | 500 | 2 |
| ON 1000ms | TX_BLE_Adv.ino | 1000 | 3 |

---

## 5. ファイルハッシュ (SHA256)

作成日時: 2025-11-29

| ファイル | SHA256 (先頭16文字) | 用途 |
|----------|---------------------|------|
| baseline_on/TX_BLE_Adv.ino | `77b89bb72f34e2dc` | ON計測TX |
| baseline_on/TXSD_PowerLogger.ino | `922398b12a30f8a0` | ON計測PowerLogger |
| baseline_on/RX_BLE_to_SD.ino | `1bfad7c308146d3c` | ON計測RX |
| baseline_off/TX_BLE_OFF.ino | `9e79065ec8e223cf` | OFF計測TX |
| baseline_off/TXSD_PowerLogger.ino | `93689f503d86c975` | OFF計測PowerLogger |
| ccs_mode/TX_BLE_Adv_CCS_Mode.ino | `959f134ecde8551c` | CCSモードTX |
| ccs_mode/TXSD_PowerLogger_CCS_Mode.ino | `0e6da19c0a2ef651` | CCSモードPowerLogger |
| ccs_mode/RX_BLE_to_SD.ino | `1bfad7c308146d3c` | CCSモードRX |
| ccs_mode/ccs_session_data.h | `6224539c62880a4d` | CCSセッションデータ |

**検証コマンド**: `shasum -a 256 esp32_firmware/**/*.ino esp32_firmware/**/*.h`
