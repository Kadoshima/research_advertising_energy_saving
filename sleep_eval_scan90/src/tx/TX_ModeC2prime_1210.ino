// TX_ModeC2prime_1210.ino (sleep_eval_scan90, standalone)
// NOTE: Arduino IDEで単体オープンできるよう、`src/tx/TX_ModeC2prime_1210/` と同内容を置いている。

#include <Arduino.h>
#include <BLEDevice.h>
#include <math.h>

#ifdef ARDUINO_ARCH_ESP32
#include "esp_pm.h"
#endif

static const uint32_t TRIAL_DURATION_MS = 60000;
static const uint32_t GAP_MS = 5000;
static const uint8_t N_CYCLES = 2;

static const bool USE_LED = false;
static const bool ENABLE_TICK_PREAMBLE = true;

static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN = 2;

static BLEAdvertising* adv = nullptr;
static bool trialRunning = false;
static uint32_t trialStartMs = 0;
static uint32_t gapStartMs = 0;
static uint8_t condIndex = 0;
static uint8_t cycleIndex = 0;

#ifdef ARDUINO_ARCH_ESP32
static esp_pm_lock_handle_t noLightSleepLock = nullptr;
static bool sleepBlocked = false;
#endif

struct Condition {
  uint16_t adv_ms;
  bool sleep_on;
  uint8_t cond_id;
  const char* label;
};

static const Condition CONDS[] = {
  {100,  false, 1, "I100_OFF"},
  {100,  true,  2, "I100_ON"},
  {2000, false, 3, "I2000_OFF"},
  {2000, true,  4, "I2000_ON"},
};
static const uint8_t N_CONDS = sizeof(CONDS) / sizeof(CONDS[0]);

static inline uint16_t ms_to_0p625(float ms) {
  long v = lroundf(ms / 0.625f);
  if (v < 0x20) v = 0x20;
  if (v > 0x4000) v = 0x4000;
  return (uint16_t)v;
}

static void syncStart() {
  if (USE_LED) digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
}

static void syncEnd() {
  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_LED) digitalWrite(LED_PIN, LOW);
}

static void setSleepAllowed(bool allowSleep) {
#ifdef ARDUINO_ARCH_ESP32
  if (!noLightSleepLock) return;
  if (allowSleep) {
    if (sleepBlocked) {
      esp_pm_lock_release(noLightSleepLock);
      sleepBlocked = false;
    }
  } else {
    if (!sleepBlocked) {
      esp_pm_lock_acquire(noLightSleepLock);
      sleepBlocked = true;
    }
  }
#else
  (void)allowSleep;
#endif
}

static void tickPreamble(uint8_t nPulses) {
  if (!ENABLE_TICK_PREAMBLE) return;
  for (uint8_t i = 0; i < nPulses; i++) {
    digitalWrite(TICK_OUT_PIN, HIGH);
    delayMicroseconds(200);
    digitalWrite(TICK_OUT_PIN, LOW);
    delay(20);
  }
}

static void configureAdvertising(const Condition& c) {
  const uint16_t adv_units = ms_to_0p625((float)c.adv_ms);
  adv->setMinInterval(adv_units);
  adv->setMaxInterval(adv_units);

  BLEAdvertisementData ad;
  ad.setName("TX_SLEEP_EVAL");
  String mfd = String("0000_") + String(c.label);
  ad.setManufacturerData(mfd);
  adv->setAdvertisementData(ad);
}

static void startTrial(const Condition& c) {
  trialStartMs = millis();
  trialRunning = true;

  setSleepAllowed(c.sleep_on);
  configureAdvertising(c);

  syncStart();
  if (adv) adv->start();
  tickPreamble(c.cond_id);
}

static void endTrial() {
  trialRunning = false;
  if (adv) adv->stop();
  syncEnd();
  gapStartMs = millis();
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);
  digitalWrite(SYNC_OUT_PIN, LOW);
  pinMode(TICK_OUT_PIN, OUTPUT);
  digitalWrite(TICK_OUT_PIN, LOW);

  BLEDevice::init("TX_SLEEP_EVAL");
  BLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = BLEDevice::getAdvertising();
  adv->setScanResponse(false);
  adv->setMinPreferred(0);

#ifdef ARDUINO_ARCH_ESP32
  (void)esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP, 0, "sleep_eval", &noLightSleepLock);
#endif

  condIndex = 0;
  cycleIndex = 0;
  gapStartMs = 0;
  startTrial(CONDS[condIndex]);
}

void loop() {
  const uint32_t nowMs = millis();

  if (trialRunning) {
    if ((nowMs - trialStartMs) >= TRIAL_DURATION_MS) {
      endTrial();
    }
    vTaskDelay(pdMS_TO_TICKS(500));
    return;
  }

  if (gapStartMs == 0) gapStartMs = nowMs;
  if ((nowMs - gapStartMs) < GAP_MS) {
    vTaskDelay(pdMS_TO_TICKS(200));
    return;
  }

  condIndex++;
  if (condIndex >= N_CONDS) {
    condIndex = 0;
    cycleIndex++;
  }
  if (cycleIndex >= N_CYCLES) {
    setSleepAllowed(true);
    vTaskDelay(pdMS_TO_TICKS(1000));
    return;
  }

  gapStartMs = 0;
  startTrial(CONDS[condIndex]);
  vTaskDelay(pdMS_TO_TICKS(200));
}

