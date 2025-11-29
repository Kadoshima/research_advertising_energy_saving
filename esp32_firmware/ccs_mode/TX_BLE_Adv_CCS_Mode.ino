// === TX_BLE_Adv_CCS_Mode.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// CCS-driven BLE advertising with dynamic interval control.
// Supports three modes: FIXED_100, FIXED_2000, CCS
//
// Usage:
//   1. Generate session header: python3 scripts/convert_session_to_header.py --session 01
//   2. Set RUN_MODE to desired mode (MODE_FIXED_100, MODE_FIXED_2000, or MODE_CCS)
//   3. Build and upload
//
// For CCS mode, the interval changes according to ccs_session_data.h at 1-second resolution.

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <BLEDevice.h>

// Include CCS session data (auto-generated)
#include "ccs_session_data.h"

// ===== Run Mode Selection =====
enum RunMode {
  MODE_FIXED_100,   // Fixed 100ms interval
  MODE_FIXED_2000,  // Fixed 2000ms interval
  MODE_CCS          // CCS-driven dynamic interval
};

// >>> SELECT MODE HERE <<<
static const RunMode RUN_MODE = MODE_CCS;

// ===== Configuration =====
static const uint32_t SAMPLE_US         = 10000;  // INA219 sampling: 10ms = 100Hz
static const uint32_t SESSION_DURATION_S = 600;   // 10 minutes
static const uint8_t  RUN_GROUP_ID      = 5;      // Condition ID (5 = CCS mode)

static const bool     USE_TICK_OUT      = true;
static const esp_power_level_t TX_PWR   = ESP_PWR_LVL_N0; // 0 dBm

// Pin assignments (same as original)
static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN      = 2;
static const int I2C_SDA      = 21;
static const int I2C_SCL      = 22;
static const int UART_TX      = 4;
static const long UART_BAUD   = 230400;

// Shunt resistor (milliohms)
#define RSHUNT_MILLIOHM  100

// ===== Global State =====
HardwareSerial uart1(1);
Adafruit_INA219 ina;
BLEAdvertising* adv = nullptr;

uint16_t seq = 0;
uint8_t hold0 = 8;  // Hold MF0000 for first few frames after sync

// Runtime state
static uint32_t sessionStartMs = 0;
static uint32_t nextSampleUs = 0;
static uint32_t nextAdvMs = 0;
static uint16_t currentIntervalMs = 100;
static uint16_t prevIntervalMs = 100;
static bool sessionRunning = false;
static uint32_t advCount = 0;
static uint32_t intervalChangeCount = 0;

// ===== Helper Functions =====

static inline String makeMFD(uint16_t s) {
  char b[7];
  snprintf(b, sizeof(b), "MF%04X", (unsigned)s);
  return String(b);
}

static const char* getModeString() {
  switch (RUN_MODE) {
    case MODE_FIXED_100:  return "FIXED_100";
    case MODE_FIXED_2000: return "FIXED_2000";
    case MODE_CCS:        return "CCS";
    default:              return "UNKNOWN";
  }
}

static uint16_t getIntervalForMode(uint32_t elapsedS) {
  switch (RUN_MODE) {
    case MODE_FIXED_100:
      return 100;
    case MODE_FIXED_2000:
      return 2000;
    case MODE_CCS:
      return getIntervalForTime(elapsedS);  // From ccs_session_data.h
    default:
      return 1000;
  }
}

static void updateBLEInterval(uint16_t intervalMs) {
  if (adv == nullptr) return;

  // Convert ms to BLE units (0.625ms)
  uint16_t itv = (uint16_t)lroundf(intervalMs / 0.625f);

  // Stop advertising, update interval, restart
  adv->stop();
  adv->setMinInterval(itv);
  adv->setMaxInterval(itv);
  adv->start();
}

static void syncStart() {
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
}

static void syncEnd() {
  digitalWrite(SYNC_OUT_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
}

// ===== Session Control =====

static void startSession() {
  advCount = 0;
  intervalChangeCount = 0;
  seq = 0;
  hold0 = 8;
  sessionRunning = true;

  sessionStartMs = millis();
  nextSampleUs = micros() + SAMPLE_US;

  // Get initial interval
  currentIntervalMs = getIntervalForMode(0);
  prevIntervalMs = currentIntervalMs;
  nextAdvMs = sessionStartMs + currentIntervalMs;

  // Set initial BLE interval
  updateBLEInterval(currentIntervalMs);

  // Sync pulse (100ms HIGH)
  syncStart();
  delay(100);
  syncEnd();

  Serial.printf("[TX] === SESSION START ===\n");
  Serial.printf("[TX] mode=%s, group=%u, session=%s\n",
                getModeString(), (unsigned)RUN_GROUP_ID,
                (RUN_MODE == MODE_CCS) ? CCS_SESSION_ID : "N/A");
  Serial.printf("[TX] duration=%us, initial_interval=%ums\n",
                (unsigned)SESSION_DURATION_S, (unsigned)currentIntervalMs);
}

static void endSession() {
  sessionRunning = false;
  syncEnd();

  uint32_t actualDurationMs = millis() - sessionStartMs;

  Serial.printf("[TX] === SESSION END ===\n");
  Serial.printf("[TX] duration_ms=%lu, adv_count=%lu, interval_changes=%lu\n",
                (unsigned long)actualDurationMs,
                (unsigned long)advCount,
                (unsigned long)intervalChangeCount);

  // Print interval distribution for CCS mode
  if (RUN_MODE == MODE_CCS) {
    Serial.printf("[TX] CCS session_id=%s\n", CCS_SESSION_ID);
  }
}

// ===== Arduino Setup/Loop =====

void setup() {
  Serial.begin(115200);
  delay(100);

  Serial.printf("\n[TX] TX_BLE_Adv_CCS_Mode initializing...\n");
  Serial.printf("[TX] Mode: %s\n", getModeString());

  // GPIO setup
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);
  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_TICK_OUT) {
    pinMode(TICK_OUT_PIN, OUTPUT);
    digitalWrite(TICK_OUT_PIN, LOW);
  }

  // BLE setup
  BLEDevice::init("TXM_ESP32");
  BLEDevice::setPower(TX_PWR);
  BLEAdvertising* a = BLEDevice::getAdvertising();
  a->setScanResponse(false);
  a->setMinPreferred(0);

  // Initial interval (will be updated when session starts)
  uint16_t itv = (uint16_t)lroundf(100 / 0.625f);
  a->setMinInterval(itv);
  a->setMaxInterval(itv);

  BLEAdvertisementData ad;
  ad.setName("TXM_ESP32");
  ad.setManufacturerData(makeMFD(0));
  a->setAdvertisementData(ad);
  a->start();
  adv = a;

  // INA219 setup
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);
  ina.begin();
  ina.setCalibration_16V_400mA();

  // UART1 setup (to PowerLogger)
  uart1.begin(UART_BAUD, SERIAL_8N1, -1, UART_TX);

  Serial.printf("[TX] Initialization complete. Starting session in 2s...\n");
  delay(2000);

  startSession();
}

void loop() {
  uint32_t nowUs = micros();
  uint32_t nowMs = millis();

  if (!sessionRunning) {
    // Session ended, idle
    vTaskDelay(100);
    return;
  }

  // Check session duration
  uint32_t elapsedMs = nowMs - sessionStartMs;
  uint32_t elapsedS = elapsedMs / 1000;

  if (elapsedS >= SESSION_DURATION_S) {
    endSession();
    return;
  }

  // ---- INA219 sampling at 10ms intervals ----
  int guard = 0;
  while ((int32_t)(nowUs - nextSampleUs) >= 0 && guard < 8) {
    nextSampleUs += SAMPLE_US;

    float v = ina.getBusVoltage_V();
    float i = ina.getCurrent_mA();

    int32_t mv = (int32_t)lroundf(v * 1000.0f);
    int32_t uA = (int32_t)lroundf(i * 1000.0f);

    // Extended format: mv,uA,interval_ms
    char line[32];
    snprintf(line, sizeof(line), "%04ld,%06ld,%04u\n",
             (long)mv, (long)uA, (unsigned)currentIntervalMs);
    uart1.print(line);

    guard++;
    nowUs = micros();
  }

  // ---- Check for interval changes (every second for CCS mode) ----
  if (RUN_MODE == MODE_CCS) {
    uint16_t newInterval = getIntervalForMode(elapsedS);
    if (newInterval != currentIntervalMs) {
      prevIntervalMs = currentIntervalMs;
      currentIntervalMs = newInterval;
      updateBLEInterval(currentIntervalMs);
      intervalChangeCount++;

      Serial.printf("[TX] t=%lus: interval %u -> %u ms\n",
                    (unsigned long)elapsedS,
                    (unsigned)prevIntervalMs,
                    (unsigned)currentIntervalMs);
    }
  }

  // ---- Advertising update at current interval ----
  if ((int32_t)(nowMs - nextAdvMs) >= 0) {
    nextAdvMs += currentIntervalMs;

    uint16_t sendSeq = (hold0 > 0) ? 0 : seq;

    BLEAdvertisementData ad;
    ad.setName("TXM_ESP32");
    ad.setManufacturerData(makeMFD(sendSeq));
    adv->setAdvertisementData(ad);

    if (hold0 > 0) {
      --hold0;
    } else {
      ++seq;
    }

    // TICK pulse for TXSD counting
    if (USE_TICK_OUT) {
      digitalWrite(TICK_OUT_PIN, HIGH);
      delayMicroseconds(200);
      digitalWrite(TICK_OUT_PIN, LOW);
    }

    advCount++;
  }

  // Yield to other tasks
  vTaskDelay(1);
}
