// === TX_BLE_Adv_Meter_OFF_10ms.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// 役割：BLE広告OFF（無線停止）でのベースライン電力測定用。
//       SYNCパルスのみを出し、TICKは無効化。INA219を10ms周期（100Hz）で計測し、
//       UART(230400bps)で v,i,p をCSV送出（非ブロッキング）。
//
// 配線：SYNC_OUT=GPIO25 → PowerLogger(26) & RX Logger(26)
//      UART1 TX=GPIO4   → PowerLogger RX=GPIO34（クロス）
//      I2C SDA=21/SCL=22→ INA219（VCCは3.3V_B推奨）
//      （TICK_OUTは使用しない）
// 電源：このボード(②)は PMM25の 3.3V_A（測定対象）。GNDは全台共通。
//
// 注意：UARTへは数値行（v,i,p）のみ送信（PowerLogger側のパーサ互換）。

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <WiFi.h>

// ===== ユーザ設定 =====
static const uint32_t SAMPLE_US       = 10000;   // 計測周期 10ms ≒ 100Hz

// ピンアサイン
static const int SYNC_OUT_PIN = 25;  // 100ms High を1回だけ出す
static const int LED_PIN      = 2;   // オンボードLED
static const int I2C_SDA      = 21;
static const int I2C_SCL      = 22;
static const int UART_TX      = 4;   // UART1 TX → PowerLogger RX=34
static const long UART_BAUD   = 230400;

// ===== グローバル =====
HardwareSerial uart1(1);
Adafruit_INA219 ina;

static inline void syncPulse() {
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
  delay(100);                         // 100ms High（取りこぼしに強い）
  digitalWrite(SYNC_OUT_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
}

// タイマ（非ブロッキング）
static uint32_t nextSampleUs;

void setup() {
  // Serial.begin(115200); // デバッグ時のみ

  // GPIO
  pinMode(LED_PIN, OUTPUT);       digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);  digitalWrite(SYNC_OUT_PIN, LOW);

  // 無線：広告OFF測定のため、BLE/Wi‑Fiは明示的に停止
  WiFi.persistent(false);
  WiFi.mode(WIFI_OFF);

  // INA219
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);             // 400kHz I2C で計測遅延を低減
  ina.begin();
  ina.setCalibration_16V_400mA();   // 代表レンジ（必要に応じ変更）

  // UART1（TX専用）
  uart1.begin(UART_BAUD, SERIAL_8N1, -1, UART_TX);

  // 起動2秒後に同期パルス
  delay(2000);
  syncPulse();

  // タイマ開始
  nextSampleUs = micros() + SAMPLE_US;
}

void loop() {
  // ---- 10ms周期の計測（追いつき処理あり・非ブロッキング）----
  uint32_t nowUs = micros();
  int guard = 0; // 1ループでの最大サンプル数（暴走防止）
  while ((int32_t)(nowUs - nextSampleUs) >= 0 && guard < 8) {
    nextSampleUs += SAMPLE_US;
    // センサ取得
    float v = ina.getBusVoltage_V();
    float i = ina.getCurrent_mA();
    float p = ina.getPower_mW();

    // UARTへCSV吐き（短めのフォーマットで帯域節約）
    uart1.printf("%.3f,%.1f,%.1f\n", v, i, p);

    guard++;
    nowUs = micros();
  }

  // 他タスクに譲る
  delay(0);

  // 数値行のみ送出（診断の#行は送らない）
}
