// === TX_BLE_OFF.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// 役割：BLE広告OFF（無線停止）でのベースライン電力測定用。
//       SYNCパルスを出してトライアル開始を通知。INA219を10ms周期（100Hz）で計測し、
//       UART(230400bps)で mv,uA をCSV送出（非ブロッキング）。
//       複数トライアルを自動実行。
//
// 配線：SYNC_OUT=GPIO25 → PowerLogger(26)
//      UART1 TX=GPIO4   → PowerLogger RX=GPIO34（クロス）
//      I2C SDA=21/SCL=22→ INA219（VCCは3.3V直結）
//      （TICK_OUTは使用しない）
// 電源：このボード(②)は PMM25の 3.3V_A（測定対象）。GNDは全台共通。

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <WiFi.h>
#include <math.h>

// ===== ユーザ設定 =====
static const uint32_t SAMPLE_US            = 10000;   // 計測周期 10ms ≒ 100Hz
static const uint32_t TRIAL_DURATION_MS    = 60000;   // 1トライアルの長さ (60秒)
static const uint8_t  N_TRIALS             = 10;      // トライアル回数
static const uint32_t GAP_BETWEEN_TRIALS_MS = 5000;   // トライアル間の待機時間

// ピンアサイン
static const int SYNC_OUT_PIN = 25;
static const int LED_PIN      = 2;
static const int I2C_SDA      = 21;
static const int I2C_SCL      = 22;
static const int UART_TX      = 4;
static const long UART_BAUD   = 230400;

// ===== グローバル =====
HardwareSerial uart1(1);
Adafruit_INA219 ina;

static uint32_t nextSampleUs = 0;
static uint8_t  trialIndex   = 0;
static bool     trialRunning = false;
static uint32_t trialStartMs = 0;
static uint32_t trialEndMs   = 0;

static inline void syncPulse() {
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
  delay(100);  // 100ms High
  digitalWrite(SYNC_OUT_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
}

static void startTrial() {
  trialRunning = true;
  trialStartMs = millis();
  nextSampleUs = micros() + SAMPLE_US;

  syncPulse();
  Serial.printf("[TX_OFF] start trial %u/%u\n", trialIndex + 1, N_TRIALS);
}

static void endTrial() {
  trialRunning = false;
  trialEndMs = millis();
  Serial.printf("[TX_OFF] end trial %u/%u, dur_ms=%lu\n",
                trialIndex + 1, N_TRIALS,
                (unsigned long)(trialEndMs - trialStartMs));
}

void setup() {
  Serial.begin(115200);

  // GPIO
  pinMode(LED_PIN, OUTPUT);       digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);  digitalWrite(SYNC_OUT_PIN, LOW);

  // 無線：広告OFF測定のため、BLE/Wi‑Fiは明示的に停止
  WiFi.persistent(false);
  WiFi.mode(WIFI_OFF);

  // INA219
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);
  ina.begin();
  ina.setCalibration_16V_400mA();

  // UART1（TX専用）
  uart1.begin(UART_BAUD, SERIAL_8N1, -1, UART_TX);

  Serial.printf("[TX_OFF] Ready. N_TRIALS=%u, TRIAL_DURATION_MS=%lu\n",
                N_TRIALS, (unsigned long)TRIAL_DURATION_MS);

  // 起動2秒後に最初のトライアル開始
  delay(2000);
  trialIndex = 0;
  startTrial();
}

void loop() {
  uint32_t nowUs = micros();
  uint32_t nowMs = millis();

  if (trialRunning) {
    // ---- 10ms周期の計測 ----
    int guard = 0;
    while ((int32_t)(nowUs - nextSampleUs) >= 0 && guard < 8) {
      nextSampleUs += SAMPLE_US;

      float v = ina.getBusVoltage_V();
      float i = ina.getCurrent_mA();

      int32_t mv = (int32_t)lroundf(v * 1000.0f);
      int32_t uA = (int32_t)lroundf(i * 1000.0f);

      char line[24];
      snprintf(line, sizeof(line), "%04ld,%06ld\n", (long)mv, (long)uA);
      uart1.print(line);

      guard++;
      nowUs = micros();
    }

    // トライアル終了チェック
    if (nowMs - trialStartMs >= TRIAL_DURATION_MS) {
      endTrial();
    }
  } else {
    // トライアル間の待機 / 次トライアル開始
    if (trialIndex + 1 < N_TRIALS) {
      if (nowMs - trialEndMs >= GAP_BETWEEN_TRIALS_MS) {
        trialIndex++;
        startTrial();
      }
    } else {
      // 全トライアル終了
      static bool done = false;
      if (!done) {
        Serial.printf("[TX_OFF] All %u trials completed.\n", N_TRIALS);
        done = true;
      }
      vTaskDelay(100);
    }
  }

  vTaskDelay(1);
}
