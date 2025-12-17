// TX_UCCS_D4B_SCAN70.ino (uccs_d4b_scan70)
//
// Step D4B（CCSが効いている切り分け / Ablation）を scan70（RX duty 70%）で再現するためのTX。
// - S4のみを再生し、4条件×REPEAT回を自動実行する。
//   1) Fixed100
//   2) Fixed500
//   3) Policy(U+CCS, 100↔500)
//   4) Ablation_CCS_off（= U-only, 100↔500）
//
// Payload (ManufacturerData):
//   "<step_idx>_<tag>"
//     tag: "F4-<label>-<itv>" / "P4-<label>-<itv>" / "U4-<label>-<itv>"
//
// Note:
// - `stress_causal_*` の CCS は「安定度（高いほどstable）」なので、changeとして扱うため `CCS_change = 1-CCS` に変換する。
// - U-only（CCS-off）は「上げる判定/戻す判定ともUだけ」を使う（CCSで戻りをブロックしない）。

#include <Arduino.h>
#include <BLEDevice.h>
#include <math.h>

#ifdef ARDUINO_ARCH_ESP32
#include "esp_pm.h"
#endif

#include "../stress_causal_s1_s4_180s.h"

// ==== schedule ====
static const uint32_t GAP_MS = 5000;
static const uint8_t REPEAT = 3;
static const uint16_t EFFECTIVE_LEN_STEPS = 1800; // 180s @ 100ms grid

// ==== pins ====
static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN = 2;

// ==== options ====
static const bool USE_LED = false;
static const bool ENABLE_TICK_PREAMBLE = true;
static const bool ENABLE_TICK_PER_UPDATE = true;
static const bool RESTART_ADV_ON_INTERVAL_CHANGE = true;

static const uint32_t PREAMBLE_WINDOW_MS = 800; // TXSD window
static const uint32_t PREAMBLE_GUARD_MS = 100;  // after SYNC HIGH before preamble

// ==== actions（実機は100↔500に固定） ====
static const uint16_t ACTIONS[] = {100, 500};
static const uint8_t N_ACTIONS = sizeof(ACTIONS) / sizeof(ACTIONS[0]);

// ==== policy params（D4B scan90と同一） ====
static const float U_MID = 0.20f;
static const float U_HIGH = 0.35f;
static const float C_MID = 0.20f;
static const float C_HIGH = 0.35f;
static const float HYST = 0.02f;
static const float EMA_ALPHA = 0.20f;

// ==== BLE ====
static BLEAdvertising* adv = nullptr;

#ifdef ARDUINO_ARCH_ESP32
static esp_pm_lock_handle_t noLightSleepLock = nullptr;
static bool sleepBlocked = false;
#endif

enum Mode : uint8_t {
  MODE_FIXED = 0,
  MODE_POLICY = 1,
  MODE_ABL_CCS_OFF = 2,
};

struct Condition {
  uint8_t cond_id;   // TXSD preamble pulses
  Mode mode;
  uint16_t fixed_ms; // MODE_FIXED only
};

// cond_id:
//  1: S4 fixed100
//  2: S4 fixed500
//  3: S4 policy
//  4: S4 ablation_ccs_off (U-only)
static const Condition CONDS[] = {
  {1, MODE_FIXED, 100},
  {2, MODE_FIXED, 500},
  {3, MODE_POLICY, 500},
  {4, MODE_ABL_CCS_OFF, 500},
};
static const uint8_t N_CONDS = sizeof(CONDS) / sizeof(CONDS[0]);

// state
static bool trialRunning = false;
static bool pendingStart = false;
static uint32_t syncRiseMs = 0;
static uint32_t trialStartMs = 0;
static uint32_t nextUpdateMs = 0;
static uint32_t gapStartMs = 0;
static uint8_t condIndex = 0;
static uint8_t repIndex = 0;

static uint16_t stepIdx = 0;               // 100ms grid index
static uint16_t currentIntervalMs = 500;   // 100 or 500
static float uEma = 0.0f;
static float cEma = 0.0f;                  // change-CCS EMA (policy only)

static inline uint16_t ms_to_0p625(float ms) {
  long v = lroundf(ms / 0.625f);
  if (v < 0x20) v = 0x20;     // 20ms minimum
  if (v > 0x4000) v = 0x4000; // 10.24s maximum
  return (uint16_t)v;
}

static uint16_t clamp_interval(uint16_t interval_ms) {
  uint16_t best = ACTIONS[0];
  uint32_t bestDist = (uint32_t)abs((int)interval_ms - (int)best);
  for (uint8_t i = 1; i < N_ACTIONS; i++) {
    uint16_t a = ACTIONS[i];
    uint32_t d = (uint32_t)abs((int)interval_ms - (int)a);
    if (d < bestDist || (d == bestDist && a < best)) {
      best = a;
      bestDist = d;
    }
  }
  return best;
}

static void syncStart() {
  if (USE_LED) digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
  syncRiseMs = millis();
}

static void syncEnd() {
  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_LED) digitalWrite(LED_PIN, LOW);
}

static void tickPulseOnce(uint16_t high_us = 200) {
  digitalWrite(TICK_OUT_PIN, HIGH);
  delayMicroseconds(high_us);
  digitalWrite(TICK_OUT_PIN, LOW);
}

static void tickPreamble(uint8_t nPulses) {
  if (!ENABLE_TICK_PREAMBLE) return;
  for (uint8_t i = 0; i < nPulses; i++) {
    tickPulseOnce(200);
    delay(20);
  }
}

static void setAdvIntervalMs(uint16_t ms) {
  if (!adv) return;
  uint16_t units = ms_to_0p625((float)ms);
  adv->setMinInterval(units);
  adv->setMaxInterval(units);
}

static void setPayload(uint16_t step_idx, const char* tag) {
  if (!adv) return;
  BLEAdvertisementData ad;
  String mfd = String((unsigned)step_idx) + "_" + String(tag);
  ad.setManufacturerData(mfd);
  adv->setAdvertisementData(ad);
}

static void setSleepAllowed(bool allowLightSleep) {
#ifdef ARDUINO_ARCH_ESP32
  if (!noLightSleepLock) return;
  if (allowLightSleep) {
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
  (void)allowLightSleep;
#endif
}

static inline uint8_t getLabel(uint16_t idx) {
  if (idx >= STRESS_CAUSAL_LEN) return 0;
  return pgm_read_byte(&S4_LABEL[idx]);
}

static inline float getU(uint16_t idx) {
  if (idx >= STRESS_CAUSAL_LEN) return 0.0f;
  uint8_t q = pgm_read_byte(&S4_U_Q[idx]);
  return q_to_f(q);
}

static inline float getCCSStable(uint16_t idx) {
  if (idx >= STRESS_CAUSAL_LEN) return 0.0f;
  uint8_t q = pgm_read_byte(&S4_CCS_Q[idx]);
  return q_to_f(q);
}

static void makeTag(char* out, size_t out_sz, const Condition& c, uint8_t truthLabel, uint16_t intervalMs) {
  const char mp = (c.mode == MODE_FIXED) ? 'F' : (c.mode == MODE_POLICY ? 'P' : 'U');
  const unsigned lbl = (unsigned)truthLabel;
  const unsigned itv = (unsigned)intervalMs;
  snprintf(out, out_sz, "%c4-%02u-%u", mp, lbl, itv);
}

static uint16_t policyStep_U_CCS(uint16_t prevInterval, float u, float c_change) {
  const float u_hi_up = U_HIGH;
  const float c_hi_up = C_HIGH;
  const float u_mid_down = U_MID - HYST;
  const float c_mid_down = C_MID - HYST;

  uint16_t next = prevInterval;
  if (prevInterval == 500) {
    if (u >= u_hi_up || c_change >= c_hi_up) next = 100;
  } else { // prev=100
    // return condition: do not block by CCS (avoid sticky-100)
    if (u < u_mid_down) next = 500;
  }
  return clamp_interval(next);
}

static uint16_t policyStep_U_only(uint16_t prevInterval, float u) {
  const float u_hi_up = U_HIGH;
  const float u_mid_down = U_MID - HYST;
  uint16_t next = prevInterval;
  if (prevInterval == 500) {
    if (u >= u_hi_up) next = 100;
  } else {
    if (u < u_mid_down) next = 500;
  }
  return clamp_interval(next);
}

static void startTrial(const Condition& c) {
  trialRunning = true;
  pendingStart = false;
  trialStartMs = millis();
  nextUpdateMs = trialStartMs;
  stepIdx = 0;
  currentIntervalMs = clamp_interval(c.fixed_ms ? c.fixed_ms : 500);
  uEma = 0.0f;
  cEma = 0.0f;

  // sleep allowed (no busy prints)
  setSleepAllowed(true);

  syncStart();
  adv->start();

  delay(PREAMBLE_GUARD_MS);
  tickPreamble(c.cond_id);
}

static void endTrial() {
  trialRunning = false;
  adv->stop();
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

  BLEDevice::init("TX_UCCS_D4B70");
  BLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = BLEDevice::getAdvertising();
  adv->setScanResponse(false);
  adv->setMinPreferred(0);

#ifdef ARDUINO_ARCH_ESP32
  (void)esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP, 0, "uccs_d4b70", &noLightSleepLock);
  // allow sleep by default
  setSleepAllowed(true);
#endif

  condIndex = 0;
  repIndex = 0;
  gapStartMs = 0;

  startTrial(CONDS[condIndex]);
}

void loop() {
  uint32_t nowMs = millis();

  if (!trialRunning) {
    if ((nowMs - gapStartMs) < GAP_MS) {
      vTaskDelay(pdMS_TO_TICKS(50));
      return;
    }
    condIndex++;
    if (condIndex >= N_CONDS) {
      condIndex = 0;
      repIndex++;
    }
    if (repIndex >= REPEAT) {
      vTaskDelay(pdMS_TO_TICKS(1000));
      return;
    }
    startTrial(CONDS[condIndex]);
    vTaskDelay(pdMS_TO_TICKS(20));
    return;
  }

  if ((nowMs - trialStartMs) >= (uint32_t)EFFECTIVE_LEN_STEPS * 100) {
    endTrial();
    return;
  }

  if ((int32_t)(nowMs - nextUpdateMs) < 0) {
    vTaskDelay(pdMS_TO_TICKS(5));
    return;
  }
  nextUpdateMs += 100; // 100ms grid
  if (stepIdx >= EFFECTIVE_LEN_STEPS) {
    endTrial();
    return;
  }

  const Condition& c = CONDS[condIndex];
  const uint8_t lbl = getLabel(stepIdx);
  const float u = getU(stepIdx);
  const float ccsStable = getCCSStable(stepIdx);
  const float ccsChange = 1.0f - ccsStable;

  // EMA
  uEma = EMA_ALPHA * u + (1.0f - EMA_ALPHA) * uEma;
  cEma = EMA_ALPHA * ccsChange + (1.0f - EMA_ALPHA) * cEma;

  uint16_t nextItv = currentIntervalMs;
  if (c.mode == MODE_FIXED) {
    nextItv = clamp_interval(c.fixed_ms);
  } else if (c.mode == MODE_POLICY) {
    nextItv = policyStep_U_CCS(currentIntervalMs, uEma, cEma);
  } else {
    nextItv = policyStep_U_only(currentIntervalMs, uEma);
  }

  char tag[24];
  makeTag(tag, sizeof(tag), c, lbl, nextItv);
  setPayload(stepIdx, tag);

  if (nextItv != currentIntervalMs) {
    currentIntervalMs = nextItv;
    setAdvIntervalMs(currentIntervalMs);
    if (RESTART_ADV_ON_INTERVAL_CHANGE) {
      adv->stop();
      delay(10);
      adv->start();
    }
  } else {
    setAdvIntervalMs(currentIntervalMs);
  }

  if (ENABLE_TICK_PER_UPDATE) tickPulseOnce(200);
  stepIdx++;
}

