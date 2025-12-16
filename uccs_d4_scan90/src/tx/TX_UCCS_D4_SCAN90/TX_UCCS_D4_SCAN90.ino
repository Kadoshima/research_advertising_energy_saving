// TX_UCCS_D4_SCAN90.ino (uccs_d4_scan90)
//
// Step D4（Uが効いている切り分け / Ablation）
// - S4のみを再生し、4条件×REPEAT回を自動実行する。
//   1) Fixed100
//   2) Fixed500
//   3) Policy(U+CCS, 100↔500)
//   4) Ablation(U-shuffle: Uの分布は同じ、時間相関だけ破壊)
//
// D2/D2bと同様に、動的でもTL/Poutが評価できるよう payload に step_idx（100msグリッド）を埋め込む。
// TXSDへは SYNC(25) + preamble TICK(27) で cond_id を通知し、trial中は更新ごとにTICKを1発出して adv_count近似とする。
//
// Payload (ManufacturerData):
//   "<step_idx>_<tag>"
//     tag: "F4-<label>-<itv>" / "P4-<label>-<itv>" / "A4-<label>-<itv>"
//
// Note:
// - `stress_causal_*` の CCS は「安定度（高いほどstable）」なので、changeとして扱うため `CCS_change = 1-CCS` に変換する。
// - U-shuffle は quantized U（uint8）列を Fisher-Yates でシャッフルしたものを使用（固定seed）。

#include <Arduino.h>
#include <BLEDevice.h>
#include <math.h>

#ifdef ARDUINO_ARCH_ESP32
#include "esp_pm.h"
#endif

#include "../stress_causal_s1_s4_180s.h"

// ==== スケジュール ====
static const uint32_t GAP_MS = 5000;
static const uint8_t REPEAT = 3;
static const uint16_t EFFECTIVE_LEN_STEPS = 1800; // 100ms grid (<=STRESS_CAUSAL_LEN)

// ==== ピン ====
static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN = 2;

// ==== オプション ====
static const bool USE_LED = false;
static const bool ENABLE_TICK_PREAMBLE = true;
static const bool ENABLE_TICK_PER_UPDATE = true;
static const bool RESTART_ADV_ON_INTERVAL_CHANGE = true;

static const uint32_t PREAMBLE_WINDOW_MS = 800; // TXSD window
static const uint32_t PREAMBLE_GUARD_MS = 100;  // wait after SYNC HIGH before preamble

// ==== actions（実機は100↔500に固定） ====
static const uint16_t ACTIONS[] = {100, 500};
static const uint8_t N_ACTIONS = sizeof(ACTIONS) / sizeof(ACTIONS[0]);

// ==== 代表ポリシー（D2bと同一） ====
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
  MODE_ABL_U_SHUF = 2,
};

struct Condition {
  uint8_t cond_id;   // TXSD preamble pulses
  Mode mode;
  uint16_t fixed_ms; // MODE_FIXED only
};

// cond_id:
//  1: S4 fixed100
//  2: S4 fixed500
//  3: S4 policy (U+CCS)
//  4: S4 ablation (U-shuffle)
static const Condition CONDS[] = {
  {1, MODE_FIXED, 100},
  {2, MODE_FIXED, 500},
  {3, MODE_POLICY, 500},
  {4, MODE_ABL_U_SHUF, 500},
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

static uint16_t stepIdx = 0;
static uint16_t currentIntervalMs = 500;
static float uEma = 0.0f;
static float cEma = 0.0f;

// U-shuffle（quantized U列をシャッフル）
static uint8_t S4_U_SHUF_Q[STRESS_CAUSAL_LEN];
static bool uShufReady = false;
static uint32_t rngState = 0xD4B40201u;

static inline uint32_t xorshift32() {
  uint32_t x = rngState;
  x ^= x << 13;
  x ^= x >> 17;
  x ^= x << 5;
  rngState = x;
  return x;
}

static void initUShuffle() {
  // copy
  for (uint16_t i = 0; i < STRESS_CAUSAL_LEN; i++) {
    S4_U_SHUF_Q[i] = pgm_read_byte(&S4_U_Q[i]);
  }
  // Fisher-Yates
  for (int i = (int)STRESS_CAUSAL_LEN - 1; i > 0; i--) {
    uint32_t j = xorshift32() % (uint32_t)(i + 1);
    uint8_t tmp = S4_U_SHUF_Q[i];
    S4_U_SHUF_Q[i] = S4_U_SHUF_Q[j];
    S4_U_SHUF_Q[j] = tmp;
  }
  uShufReady = true;
}

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

static inline float getUShuf(uint16_t idx) {
  if (!uShufReady || idx >= STRESS_CAUSAL_LEN) return getU(idx);
  return q_to_f(S4_U_SHUF_Q[idx]);
}

static inline float getCCSStable(uint16_t idx) {
  if (idx >= STRESS_CAUSAL_LEN) return 0.0f;
  uint8_t q = pgm_read_byte(&S4_CCS_Q[idx]);
  return q_to_f(q);
}

static uint16_t policyStep(uint16_t prevInterval, float u, float c_change) {
  const float u_hi_up = U_HIGH;
  const float c_hi_up = C_HIGH;
  const float u_mid_down = U_MID - HYST;
  const float c_mid_down = C_MID - HYST;

  uint16_t next = prevInterval;
  if (prevInterval == 500) {
    if ((u >= u_hi_up) || (c_change >= c_hi_up)) next = 100;
  } else { // prevInterval == 100
    if ((u < u_mid_down) && (c_change < c_mid_down)) next = 500;
  }
  return clamp_interval(next);
}

static void applyInterval(uint16_t nextMs) {
  if (nextMs == currentIntervalMs) return;
  currentIntervalMs = nextMs;
  if (!adv) return;
  if (RESTART_ADV_ON_INTERVAL_CHANGE) {
    adv->stop();
    setAdvIntervalMs(currentIntervalMs);
    adv->start();
  } else {
    setAdvIntervalMs(currentIntervalMs);
  }
}

static void makeTag(char* out, size_t out_sz, const Condition& c, uint8_t truthLabel, uint16_t intervalMs) {
  const char mp = (c.mode == MODE_FIXED) ? 'F' : ((c.mode == MODE_POLICY) ? 'P' : 'A');
  const unsigned lbl = (unsigned)truthLabel;
  const unsigned itv = (unsigned)intervalMs;
  snprintf(out, out_sz, "%c4-%02u-%u", mp, lbl, itv);
}

static void beginCondition(const Condition& c) {
  stepIdx = 0;
  uEma = 0.0f;
  cEma = 0.0f;
  currentIntervalMs = (c.mode == MODE_FIXED) ? c.fixed_ms : 500;
  currentIntervalMs = clamp_interval(currentIntervalMs);

  if (adv) adv->stop();
  setAdvIntervalMs(currentIntervalMs);

  setSleepAllowed(true);

  syncStart();
  syncRiseMs = millis();
  delay(PREAMBLE_GUARD_MS);
  tickPreamble(c.cond_id);
  pendingStart = true;
}

static void startTrialNow(const Condition& c) {
  trialStartMs = millis();
  trialRunning = true;

  const uint8_t lbl = getLabel(0);
  char tag[20];
  makeTag(tag, sizeof(tag), c, lbl, currentIntervalMs);
  setPayload(0, tag);

  if (adv) adv->start();
  if (ENABLE_TICK_PER_UPDATE) tickPulseOnce(200);

  const uint16_t deltaSteps = (uint16_t)(currentIntervalMs / 100);
  stepIdx = (uint16_t)(stepIdx + deltaSteps);
  nextUpdateMs = millis() + currentIntervalMs;
}

static void endTrial() {
  trialRunning = false;
  pendingStart = false;
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

  initUShuffle();

  BLEDevice::init("TX_UCCS_D4_SCAN90");
  BLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = BLEDevice::getAdvertising();
  adv->setScanResponse(false);
  adv->setMinPreferred(0);

#ifdef ARDUINO_ARCH_ESP32
  (void)esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP, 0, "uccs_d4", &noLightSleepLock);
#endif

  condIndex = 0;
  repIndex = 0;
  gapStartMs = 0;
  trialRunning = false;
  pendingStart = false;

  beginCondition(CONDS[condIndex]);
}

void loop() {
  const uint32_t nowMs = millis();
  const Condition& c = CONDS[condIndex];

  if (pendingStart) {
    if ((nowMs - syncRiseMs) >= PREAMBLE_WINDOW_MS) {
      pendingStart = false;
      startTrialNow(c);
    } else {
      vTaskDelay(1);
      return;
    }
  }

  if (trialRunning) {
    if (stepIdx >= EFFECTIVE_LEN_STEPS) {
      endTrial();
      vTaskDelay(pdMS_TO_TICKS(50));
      return;
    }

    if ((int32_t)(nowMs - nextUpdateMs) >= 0) {
      const uint8_t truthLabel = getLabel(stepIdx);

      if (c.mode == MODE_POLICY || c.mode == MODE_ABL_U_SHUF) {
        const float uRaw = (c.mode == MODE_ABL_U_SHUF) ? getUShuf(stepIdx) : getU(stepIdx);
        const float cStable = getCCSStable(stepIdx);
        const float cChange = 1.0f - cStable;
        uEma = EMA_ALPHA * uRaw + (1.0f - EMA_ALPHA) * uEma;
        cEma = EMA_ALPHA * cChange + (1.0f - EMA_ALPHA) * cEma;

        const uint16_t nextI = policyStep(currentIntervalMs, uEma, cEma);
        applyInterval(nextI);
      }

      char tag[20];
      makeTag(tag, sizeof(tag), c, truthLabel, currentIntervalMs);
      setPayload(stepIdx, tag);
      if (ENABLE_TICK_PER_UPDATE) tickPulseOnce(200);

      const uint16_t deltaSteps = (uint16_t)(currentIntervalMs / 100);
      stepIdx = (uint16_t)(stepIdx + deltaSteps);
      nextUpdateMs = millis() + currentIntervalMs;
    }

    vTaskDelay(1);
    return;
  }

  if (gapStartMs == 0) gapStartMs = nowMs;
  if ((nowMs - gapStartMs) < GAP_MS) {
    vTaskDelay(pdMS_TO_TICKS(50));
    return;
  }

  gapStartMs = 0;
  condIndex++;
  if (condIndex >= N_CONDS) {
    condIndex = 0;
    repIndex++;
  }
  if (repIndex >= REPEAT) {
    setSleepAllowed(true);
    if (adv) adv->stop();
    syncEnd();
    vTaskDelay(pdMS_TO_TICKS(1000));
    return;
  }

  beginCondition(CONDS[condIndex]);
  vTaskDelay(pdMS_TO_TICKS(200));
}

