// TX_DeltaE_Sweep.ino
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
// Role: Run OFF + ON(100/500/1000/2000ms) sequentially, drive SYNC and (ON only) TICK.

#include <Arduino.h>
#include <BLEDevice.h>

static const char FW_TAG[] = "TX_DeltaE_Sweep";
static const char PROGRAM_ID[] = "TX_DELTAE_SWEEP_20260115";

// Pins
static const int SYNC_OUT_PIN = 26;
static const int SYNC_ALT_OUT_PIN = 25; // optional mirror of SYNC_OUT
static const bool USE_SYNC_ALT_OUT = false;
static const int TICK_OUT_PIN = 27;
static const bool USE_TICK_OUT = true;
static const int LED_PIN = 2;

// Schedule
#ifndef QUICK_TEST
#define QUICK_TEST 0
#endif
#ifndef SINGLE_MODE_ONLY
#define SINGLE_MODE_ONLY 0
#endif
#if QUICK_TEST
static const uint32_t TRIAL_MS = 30000;
static const uint8_t TRIALS_PER_MODE = 3;
static const uint32_t GAP_BETWEEN_TRIALS_MS = 2000;
static const uint8_t START_MODE_INDEX = 0; // OFF
static const uint32_t STARTUP_WARMUP_MS = 20000;
#else
static const uint32_t TRIAL_MS = 60000;
static const uint8_t TRIALS_PER_MODE = 10;
static const uint32_t GAP_BETWEEN_TRIALS_MS = 5000;
static const uint8_t START_MODE_INDEX = 0; // OFF
static const uint32_t STARTUP_WARMUP_MS = 0;
#endif
static const uint8_t HOLD0 = 8; // first N advs use seq=0 to help receiver lock

// TX power
static const esp_power_level_t TX_PWR = ESP_PWR_LVL_N0; // 0 dBm

struct Mode {
  const char* name;
  bool adv_on;
  uint16_t adv_interval_ms; // valid if adv_on
};
static const Mode MODES[] = {
  {"OFF", false, 0},
  {"ON_100ms", true, 100},
  {"ON_500ms", true, 500},
  {"ON_1000ms", true, 1000},
  {"ON_2000ms", true, 2000},
};
static const uint8_t N_MODES = (uint8_t)(sizeof(MODES) / sizeof(MODES[0]));

// BLE state
BLEAdvertising* adv = nullptr;
static char g_mfd_buf[7];
static String g_mfd_str;

// Runtime state
uint8_t modeIndex = 0;
uint8_t trialIndexInMode = 0;
bool trialRunning = false;
uint32_t trialStartMs = 0;
uint32_t trialEndMs = 0;
uint32_t nextAdvMs = 0;
uint16_t seq = 0;
uint8_t hold0 = HOLD0;
uint32_t advCount = 0;

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

static inline const String& makeMFD(uint16_t s) {
  snprintf(g_mfd_buf, sizeof(g_mfd_buf), "MF%04X", (unsigned)s);
  g_mfd_str = g_mfd_buf; // reuse reserved capacity
  return g_mfd_str;
}

static void bleEnsureInit() {
  if (adv) return;
  BLEDevice::init("TX_DELTAE_SWEEP");
  BLEDevice::setPower(TX_PWR, ESP_BLE_PWR_TYPE_ADV);
  BLEAdvertising* a = BLEDevice::getAdvertising();
  a->setScanResponse(false);
  a->setMinPreferred(0);
  adv = a;
  g_mfd_str.reserve(6);
}

static void bleStopIfRunning() {
  if (!adv) return;
  adv->stop();
}

static void bleStartWithIntervalMs(uint16_t intervalMs) {
  bleEnsureInit();
  uint16_t itv = (uint16_t)lroundf(intervalMs / 0.625f);
  BLEAdvertisementData ad;
  ad.setFlags(0x06);
  ad.setName("TX_DELTAE_SWEEP");
  ad.setManufacturerData(makeMFD(0));
  adv->setAdvertisementData(ad);
  adv->setMinInterval(itv);
  adv->setMaxInterval(itv);
  adv->start();
}

static void applyMode(const Mode& m) {
  if (!m.adv_on) {
    bleStopIfRunning();
    Serial.printf("[TX] mode=%s (BLE adv stopped)\n", m.name);
    return;
  }

  bleStartWithIntervalMs(m.adv_interval_ms);
  Serial.printf("[TX] mode=%s interval=%u ms\n", m.name, (unsigned)m.adv_interval_ms);
}

static void startTrial(const Mode& m) {
  trialRunning = true;
  trialStartMs = millis();
  nextAdvMs = trialStartMs + (m.adv_on ? m.adv_interval_ms : 0);
  advCount = 0;
  seq = 0;
  hold0 = HOLD0;
  syncStart();
  Serial.printf("[TX] start mode=%s trial=%u/%u\n",
                m.name, (unsigned)(trialIndexInMode + 1), (unsigned)TRIALS_PER_MODE);
}

static void endTrial(const Mode& m) {
  (void)m;
  trialRunning = false;
  trialEndMs = millis();
  syncEnd();
  Serial.printf("[TX] end mode=%s trial=%u/%u adv_sent=%lu\n",
                MODES[modeIndex].name,
                (unsigned)(trialIndexInMode + 1), (unsigned)TRIALS_PER_MODE,
                (unsigned long)advCount);
}

void setup() {
  Serial.begin(115200);
  Serial.printf("[FW] %s program_id=%s build=%s %s\n", FW_TAG, PROGRAM_ID, __DATE__, __TIME__);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);
  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_SYNC_ALT_OUT) {
    pinMode(SYNC_ALT_OUT_PIN, OUTPUT);
    digitalWrite(SYNC_ALT_OUT_PIN, LOW);
  }
  if (USE_TICK_OUT) {
    pinMode(TICK_OUT_PIN, OUTPUT);
    digitalWrite(TICK_OUT_PIN, LOW);
  }

  delay(2000);

  modeIndex = START_MODE_INDEX;
  trialIndexInMode = 0;
  applyMode(MODES[modeIndex]);
  if (STARTUP_WARMUP_MS > 0) {
    Serial.printf("[TX] warmup %lu ms before first trial\n", (unsigned long)STARTUP_WARMUP_MS);
    delay(STARTUP_WARMUP_MS);
  }
  delay(500);
  startTrial(MODES[modeIndex]);
}

void loop() {
  uint32_t nowMs = millis();
  const Mode& m = MODES[modeIndex];

  if (trialRunning) {
    if (m.adv_on) {
      if ((int32_t)(nowMs - nextAdvMs) >= 0) {
        nextAdvMs += m.adv_interval_ms;
        uint16_t sendSeq = (hold0 > 0) ? 0 : seq;

        BLEAdvertisementData ad;
        ad.setFlags(0x06);
        ad.setName("TX_DELTAE_SWEEP");
        ad.setManufacturerData(makeMFD(sendSeq));
        adv->setAdvertisementData(ad);
        adv->start();

        if (hold0 > 0) {
          --hold0;
        } else {
          ++seq;
        }

        if (USE_TICK_OUT) {
          digitalWrite(TICK_OUT_PIN, HIGH);
          delayMicroseconds(200);
          digitalWrite(TICK_OUT_PIN, LOW);
        }
        advCount++;
      }
    }

    if ((nowMs - trialStartMs) >= TRIAL_MS) {
      endTrial(m);
    }
  } else {
    if (nowMs - trialEndMs < GAP_BETWEEN_TRIALS_MS) {
      vTaskDelay(1);
      return;
    }

    static bool done = false;
    if (SINGLE_MODE_ONLY) {
      if (!done) {
        done = true;
        Serial.printf("[TX] All modes completed. modes=%u trials_per_mode=%u\n",
                      (unsigned)N_MODES, (unsigned)TRIALS_PER_MODE);
        syncEnd();
        bleStopIfRunning();
      }
      vTaskDelay(100);
      return;
    }

    if (trialIndexInMode + 1 < TRIALS_PER_MODE) {
      trialIndexInMode++;
      startTrial(m);
      vTaskDelay(1);
      return;
    }

    // Next mode
    if (modeIndex + 1 < N_MODES) {
      modeIndex++;
      trialIndexInMode = 0;
      applyMode(MODES[modeIndex]);
      delay(500);
      startTrial(MODES[modeIndex]);
      vTaskDelay(1);
      return;
    }

    if (!done) {
      done = true;
      Serial.printf("[TX] All modes completed. modes=%u trials_per_mode=%u\n",
                    (unsigned)N_MODES, (unsigned)TRIALS_PER_MODE);
      syncEnd();
      bleStopIfRunning();
    }
    vTaskDelay(100);
  }

  vTaskDelay(1);
}

