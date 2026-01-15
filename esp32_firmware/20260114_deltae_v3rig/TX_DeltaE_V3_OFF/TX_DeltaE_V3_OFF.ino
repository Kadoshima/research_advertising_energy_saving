// TX_DeltaE_V3_OFF.ino
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
// Role: BLE/Wi-Fi OFF baseline with SYNC timing.

#include <Arduino.h>
#include <WiFi.h>

static const char FW_TAG[] = "TX_DeltaE_V3_OFF";
static const char PROGRAM_ID[] = "TX_DELTAE_V3_OFF_20260114";

static const uint32_t TRIAL_MS = 60000;
static const uint8_t N_TRIALS = 10;
static const uint32_t GAP_BETWEEN_TRIALS_MS = 5000;

static const int SYNC_OUT_PIN = 25;
static const int SYNC_ALT_OUT_PIN = 26; // optional mirror of SYNC_OUT
static const bool USE_SYNC_ALT_OUT = true;
static const int LED_PIN = 2;

uint32_t trialStartMs = 0;
uint32_t trialEndMs = 0;
uint8_t trialIndex = 0;
bool trialRunning = false;

static inline void syncStart() {
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
  if (USE_SYNC_ALT_OUT) digitalWrite(SYNC_ALT_OUT_PIN, HIGH);
}

static inline void syncEnd() {
  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_SYNC_ALT_OUT) digitalWrite(SYNC_ALT_OUT_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
}

static void startTrial() {
  trialRunning = true;
  trialStartMs = millis();
  syncStart();
  Serial.printf("[TX_OFF] start trial %u/%u\n", (unsigned)(trialIndex + 1), (unsigned)N_TRIALS);
}

static void endTrial() {
  trialRunning = false;
  trialEndMs = millis();
  syncEnd();
  Serial.printf("[TX_OFF] end trial %u/%u\n", (unsigned)(trialIndex + 1), (unsigned)N_TRIALS);
}

void setup() {
  Serial.begin(115200);
  Serial.printf("[FW] %s program_id=%s\n", FW_TAG, PROGRAM_ID);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);
  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_SYNC_ALT_OUT) {
    pinMode(SYNC_ALT_OUT_PIN, OUTPUT);
    digitalWrite(SYNC_ALT_OUT_PIN, LOW);
  }

  WiFi.persistent(false);
  WiFi.mode(WIFI_OFF);

  delay(2000);
  trialIndex = 0;
  startTrial();
}

void loop() {
  uint32_t nowMs = millis();

  if (trialRunning) {
    if ((nowMs - trialStartMs) >= TRIAL_MS) {
      endTrial();
    }
  } else {
    if (trialIndex + 1 < N_TRIALS) {
      if (nowMs - trialEndMs >= GAP_BETWEEN_TRIALS_MS) {
        trialIndex++;
        startTrial();
      }
    } else {
      static bool done = false;
      if (!done) {
        done = true;
        Serial.printf("[TX_OFF] All %u trials completed.\n", (unsigned)N_TRIALS);
      }
      vTaskDelay(100);
    }
  }

  vTaskDelay(1);
}
