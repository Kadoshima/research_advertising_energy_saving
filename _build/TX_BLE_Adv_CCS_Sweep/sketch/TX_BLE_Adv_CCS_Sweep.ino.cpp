#line 1 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
// === TX_BLE_Adv_CCS_Mode.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// CCS-driven BLE advertising with dynamic interval control.
// Supports FIXED_100/500/1000/2000 and CCS.
//
// Usage:
//   1. Generate session header: python3 scripts/convert_session_to_header.py --session 01
//   2. Confirm MODE_SEQUENCE + REPS_PER_MODE
//   3. Build and upload
//
// For CCS mode, the interval changes according to ccs_session_data.h at 1-second resolution.

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <BLEDevice.h>

// Include CCS session data (auto-generated)
#include "ccs_session_data.h"

static const char FW_TAG[] = "TX_BLE_Adv_CCS_Sweep";

// ===== Run Mode Selection =====
enum RunMode {
  MODE_FIXED_100,   // Fixed 100ms interval
  MODE_FIXED_500,   // Fixed 500ms interval
  MODE_FIXED_1000,  // Fixed 1000ms interval
  MODE_FIXED_2000,  // Fixed 2000ms interval
  MODE_CCS          // CCS-driven dynamic interval
};

// ===== Configuration =====
static const uint32_t SAMPLE_US         = 10000;  // INA219 sampling: 10ms = 100Hz
static const uint32_t SESSION_DURATION_S = 600;   // 10 minutes
// Run order: CCS only, 5 sessions.
static const RunMode  MODE_SEQUENCE[] = {
  MODE_CCS
};
static const uint8_t  REPS_PER_MODE   = 1;  // 1 boot = 1 trial
static const uint8_t  MODE_SEQUENCE_LEN =
  (uint8_t)(sizeof(MODE_SEQUENCE) / sizeof(MODE_SEQUENCE[0]));
static const uint16_t SESSION_REPEAT  = (uint16_t)(MODE_SEQUENCE_LEN * REPS_PER_MODE);
static const uint32_t GAP_BETWEEN_SESSIONS_MS = 5000;

static const bool     USE_TICK_OUT      = true;
static const esp_power_level_t TX_PWR   = ESP_PWR_LVL_N0; // 0 dBm

// Pin assignments (same as original)
static const int SYNC_OUT_PIN = 26; // START pulse
static const int SYNC_END_PIN = 25; // END pulse
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
static uint8_t sessionIndex = 0;
static uint32_t lastSessionEndMs = 0;
static RunMode currentMode = MODE_FIXED_100;

// ===== Helper Functions =====

#line 85 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
static String makeMFD(uint16_t s);
#line 91 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
static const char * getModeString(RunMode mode);
#line 102 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
static uint8_t getGroupId(RunMode mode);
#line 113 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
static uint16_t getIntervalForMode(RunMode mode, uint32_t elapsedS);
#line 130 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
static void updateBLEInterval(uint16_t intervalMs);
#line 144 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
static void syncPulse(int pin);
#line 154 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
static void startSession();
#line 193 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
static void endSession();
#line 219 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
void setup();
#line 273 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
void loop();
#line 85 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_BLE_Adv_CCS_Sweep\\TX_BLE_Adv_CCS_Sweep.ino"
static inline String makeMFD(uint16_t s) {
  char b[7];
  snprintf(b, sizeof(b), "MF%04X", (unsigned)s);
  return String(b);
}

static const char* getModeString(RunMode mode) {
  switch (mode) {
    case MODE_FIXED_100:  return "FIXED_100";
    case MODE_FIXED_500:  return "FIXED_500";
    case MODE_FIXED_1000: return "FIXED_1000";
    case MODE_FIXED_2000: return "FIXED_2000";
    case MODE_CCS:        return "CCS";
    default:              return "UNKNOWN";
  }
}

static uint8_t getGroupId(RunMode mode) {
  switch (mode) {
    case MODE_FIXED_100:  return 1;
    case MODE_FIXED_500:  return 2;
    case MODE_FIXED_1000: return 3;
    case MODE_FIXED_2000: return 4;
    case MODE_CCS:        return 5;
    default:              return 0;
  }
}

static uint16_t getIntervalForMode(RunMode mode, uint32_t elapsedS) {
  switch (mode) {
    case MODE_FIXED_100:
      return 100;
    case MODE_FIXED_500:
      return 500;
    case MODE_FIXED_1000:
      return 1000;
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

static const uint16_t SYNC_PULSE_MS = 50;
static void syncPulse(int pin) {
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(pin, HIGH);
  delay(SYNC_PULSE_MS);
  digitalWrite(pin, LOW);
  digitalWrite(LED_PIN, LOW);
}

// ===== Session Control =====

static void startSession() {
  if (sessionIndex >= SESSION_REPEAT) {
    return;
  }
  sessionIndex++;
  uint8_t modeIdx = (uint8_t)((sessionIndex - 1) / REPS_PER_MODE);
  if (modeIdx >= MODE_SEQUENCE_LEN) {
    modeIdx = (uint8_t)(MODE_SEQUENCE_LEN - 1);
  }
  currentMode = MODE_SEQUENCE[modeIdx];
  advCount = 0;
  intervalChangeCount = 0;
  seq = 0;
  hold0 = 8;
  sessionRunning = true;

  sessionStartMs = millis();
  nextSampleUs = micros() + SAMPLE_US;

  // Get initial interval
  currentIntervalMs = getIntervalForMode(currentMode, 0);
  prevIntervalMs = currentIntervalMs;
  nextAdvMs = sessionStartMs + currentIntervalMs;

  // Set initial BLE interval
  updateBLEInterval(currentIntervalMs);

  // Start pulse (GPIO26)
  syncPulse(SYNC_OUT_PIN);

  Serial.printf("[TX] === SESSION START (%u/%u) ===\n",
                (unsigned)sessionIndex, (unsigned)SESSION_REPEAT);
  Serial.printf("[TX] mode=%s, group=%u, session=%s\n",
                getModeString(currentMode), (unsigned)getGroupId(currentMode),
                (currentMode == MODE_CCS) ? CCS_SESSION_ID : "N/A");
  Serial.printf("[TX] duration=%us, initial_interval=%ums\n",
                (unsigned)SESSION_DURATION_S, (unsigned)currentIntervalMs);
}

static void endSession() {
  sessionRunning = false;
  // End pulse (GPIO25)
  syncPulse(SYNC_END_PIN);
  if (adv != nullptr) {
    adv->stop();
  }
  lastSessionEndMs = millis();

  uint32_t actualDurationMs = millis() - sessionStartMs;

  Serial.printf("[TX] === SESSION END (%u/%u) ===\n",
                (unsigned)sessionIndex, (unsigned)SESSION_REPEAT);
  Serial.printf("[TX] duration_ms=%lu, adv_count=%lu, interval_changes=%lu\n",
                (unsigned long)actualDurationMs,
                (unsigned long)advCount,
                (unsigned long)intervalChangeCount);

  // Print interval distribution for CCS mode
  if (currentMode == MODE_CCS) {
    Serial.printf("[TX] CCS session_id=%s\n", CCS_SESSION_ID);
  }
}

// ===== Arduino Setup/Loop =====

void setup() {
  Serial.begin(115200);
  delay(100);

  Serial.printf("\n[TX] TX_BLE_Adv_CCS_Mode initializing...\n");
  Serial.printf("[TX] fw=%s\n", FW_TAG);
  // GPIO setup
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);
  pinMode(SYNC_END_PIN, OUTPUT);
  digitalWrite(SYNC_OUT_PIN, LOW);
  digitalWrite(SYNC_END_PIN, LOW);
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

  Serial.printf("[TX] Initialization complete. sessions=%u, gap_ms=%lu\n",
                (unsigned)SESSION_REPEAT, (unsigned long)GAP_BETWEEN_SESSIONS_MS);
  Serial.printf("[TX] Starting session in 2s...\n");
  delay(2000);

  startSession();
}

void loop() {
  uint32_t nowUs = micros();
  uint32_t nowMs = millis();

  if (!sessionRunning) {
    if (sessionIndex < SESSION_REPEAT &&
        (nowMs - lastSessionEndMs) >= GAP_BETWEEN_SESSIONS_MS) {
      startSession();
    }
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
  if (currentMode == MODE_CCS) {
    uint16_t newInterval = getIntervalForMode(currentMode, elapsedS);
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

