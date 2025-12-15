// TX_UCCS_D2_SCAN90.ino (uccs_d2_scan90)
//
// Step D2 (実機): 動的でも TL/Pout を評価できるように、広告payloadに step_idx を埋め込む。
// - stress_causal(S1/S4) の label/U/CCS をフラッシュに埋め込み、同一セッションを再生する。
// - 1回の起動で S1/S4 × {Fixed100, Fixed500, Policy(100↔500)} を自動実行（REPEAT回繰り返し）。
// - RX/TXSDへは SYNC(25) で開始/終了、TXSDへは preamble TICK(27) パルス数で cond_id を通知。
// - trial中は「広告更新」ごとに TICK を1発出し、TXSDで adv_count=tick_count として取得する（近似）。
//
// Payload (ManufacturerData):
//   "<step_idx>_<tag>"
//     step_idx: 100msグリッドの整数 (0..)
//     tag: "F1-<label>-<itv>" / "P1-<label>-<itv>" / "F4-..." / "P4-..."
//          F=Fixed, P=Policy, 1/4=session, <label>=truth label (00..), <itv>=current interval (100/500)
//
// Note:
// - 実広告イベント数を厳密に数えるわけではない（tickはpayload更新回数の近似）。
// - interval変更は確実性優先で adv stop/start を行う（RESTART_ADV_ON_INTERVAL_CHANGE=true）。

#include <Arduino.h>
#include <BLEDevice.h>
#include <math.h>

#ifdef ARDUINO_ARCH_ESP32
#include "esp_pm.h"
#endif

#include "../stress_causal_s1_s4_180s.h"

// ==== スケジュール ====
static const uint32_t GAP_MS = 5000;         // 条件間ギャップ
static const uint8_t REPEAT = 3;             // 各条件×繰り返し回数（S1/S4それぞれに適用）
static const uint16_t EFFECTIVE_LEN_STEPS = 1800; // 100msグリッド長（<=STRESS_CAUSAL_LEN）

// ==== ピン ====
static const int SYNC_OUT_PIN = 25; // TX -> RX/TXSD SYNC
static const int TICK_OUT_PIN = 27; // TX -> TXSD TICK (preamble + adv_count)
static const int LED_PIN = 2;

// ==== オプション ====
static const bool USE_LED = false;
static const bool ENABLE_TICK_PREAMBLE = true;
static const bool ENABLE_TICK_PER_UPDATE = true;
static const bool RESTART_ADV_ON_INTERVAL_CHANGE = true;

// TXSD preamble window と整合（TXSD側: 800ms）
static const uint32_t PREAMBLE_WINDOW_MS = 800;

// ==== actions（実機は 100↔500 に固定） ====
static const uint16_t ACTIONS[] = {100, 500};
static const uint8_t N_ACTIONS = sizeof(ACTIONS) / sizeof(ACTIONS[0]);

// ==== 代表ポリシー（D0確定: actions={100,500} δ=0.03 power-min） ====
static const float U_MID = 0.20f;
static const float U_HIGH = 0.35f;
static const float C_MID = 0.20f;
static const float C_HIGH = 0.35f;
static const float HYST = 0.02f;
static const float EMA_ALPHA = 0.20f; // 0..1

// ==== BLE ====
static BLEAdvertising* adv = nullptr;

#ifdef ARDUINO_ARCH_ESP32
static esp_pm_lock_handle_t noLightSleepLock = nullptr;
static bool sleepBlocked = false;
#endif

enum Session : uint8_t { SESSION_S1 = 1, SESSION_S4 = 4 };
enum Mode : uint8_t { MODE_FIXED = 0, MODE_POLICY = 1 };

struct Condition {
  uint8_t cond_id;       // TXSD: preamble pulses
  Session session;       // S1 or S4
  Mode mode;             // fixed/policy
  uint16_t fixed_ms;     // MODE_FIXED only
};

// cond_id（READMEと一致）
// 1: S1 fixed100
// 2: S1 fixed500
// 3: S1 policy
// 4: S4 fixed100
// 5: S4 fixed500
// 6: S4 policy
static const Condition CONDS[] = {
  {1, SESSION_S1, MODE_FIXED, 100},
  {2, SESSION_S1, MODE_FIXED, 500},
  {3, SESSION_S1, MODE_POLICY, 500},
  {4, SESSION_S4, MODE_FIXED, 100},
  {5, SESSION_S4, MODE_FIXED, 500},
  {6, SESSION_S4, MODE_POLICY, 500},
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
static float cEma = 0.0f;

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
  // ManufacturerData only（size節約のため name は入れない）
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

static inline uint8_t getLabel(Session s, uint16_t idx) {
  if (idx >= STRESS_CAUSAL_LEN) return 0;
  if (s == SESSION_S1) return pgm_read_byte(&S1_LABEL[idx]);
  return pgm_read_byte(&S4_LABEL[idx]);
}

static inline float getU(Session s, uint16_t idx) {
  if (idx >= STRESS_CAUSAL_LEN) return 0.0f;
  uint8_t q = (s == SESSION_S1) ? pgm_read_byte(&S1_U_Q[idx]) : pgm_read_byte(&S4_U_Q[idx]);
  return q_to_f(q);
}

static inline float getCCS(Session s, uint16_t idx) {
  if (idx >= STRESS_CAUSAL_LEN) return 0.0f;
  uint8_t q = (s == SESSION_S1) ? pgm_read_byte(&S1_CCS_Q[idx]) : pgm_read_byte(&S4_CCS_Q[idx]);
  return q_to_f(q);
}

static uint16_t policyStep(uint16_t prevInterval, float u, float c) {
  // 2値（100/500）: HIGHで100へ、両方MIDより十分低いと500へ戻す（ヒステリシス）
  const float u_hi_up = U_HIGH;
  const float c_hi_up = C_HIGH;
  const float u_mid_down = U_MID - HYST;
  const float c_mid_down = C_MID - HYST;

  uint16_t next = prevInterval;
  if (prevInterval == 500) {
    if ((u >= u_hi_up) || (c >= c_hi_up)) next = 100;
  } else { // prevInterval == 100
    if ((u < u_mid_down) && (c < c_mid_down)) next = 500;
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
  // "F1-09-100" / "P4-11-500" etc.
  const char mp = (c.mode == MODE_FIXED) ? 'F' : 'P';
  const unsigned sess = (unsigned)c.session; // 1 or 4
  const unsigned lbl = (unsigned)truthLabel;
  const unsigned itv = (unsigned)intervalMs;
  snprintf(out, out_sz, "%c%u-%02u-%u", mp, sess, lbl, itv);
}

static void beginCondition(const Condition& c) {
  // per-trial init (adv is still stopped until preamble window passes)
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
  tickPreamble(c.cond_id);
  pendingStart = true;
}

static void startTrialNow(const Condition& c) {
  trialStartMs = millis();
  trialRunning = true;

  // initial payload at step=0
  const uint8_t lbl = getLabel(c.session, 0);
  char tag[16];
  makeTag(tag, sizeof(tag), c, lbl, currentIntervalMs);
  setPayload(0, tag);

  if (adv) adv->start();
  if (ENABLE_TICK_PER_UPDATE) tickPulseOnce(200);

  // advance to next step index (= time axis). Next update happens after currentIntervalMs.
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

  BLEDevice::init("TX_UCCS_D2_SCAN90");
  BLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = BLEDevice::getAdvertising();
  adv->setScanResponse(false);
  adv->setMinPreferred(0);

#ifdef ARDUINO_ARCH_ESP32
  (void)esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP, 0, "uccs_d2", &noLightSleepLock);
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
    // stop condition (time axis by stepIdx)
    if (stepIdx >= EFFECTIVE_LEN_STEPS) {
      endTrial();
      vTaskDelay(pdMS_TO_TICKS(50));
      return;
    }

    if ((int32_t)(nowMs - nextUpdateMs) >= 0) {
      // update at advertising cadence
      const uint8_t truthLabel = getLabel(c.session, stepIdx);

      if (c.mode == MODE_POLICY) {
        const float uRaw = getU(c.session, stepIdx);
        const float cRaw = getCCS(c.session, stepIdx);
        uEma = EMA_ALPHA * uRaw + (1.0f - EMA_ALPHA) * uEma;
        cEma = EMA_ALPHA * cRaw + (1.0f - EMA_ALPHA) * cEma;

        const uint16_t nextI = policyStep(currentIntervalMs, uEma, cEma);
        applyInterval(nextI);
      }

      char tag[16];
      makeTag(tag, sizeof(tag), c, truthLabel, currentIntervalMs);
      setPayload(stepIdx, tag);
      if (ENABLE_TICK_PER_UPDATE) tickPulseOnce(200);

      // advance time
      const uint16_t deltaSteps = (uint16_t)(currentIntervalMs / 100);
      stepIdx = (uint16_t)(stepIdx + deltaSteps);
      nextUpdateMs = millis() + currentIntervalMs;
    }
    vTaskDelay(1);
    return;
  }

  // gap
  if (gapStartMs == 0) gapStartMs = nowMs;
  if ((nowMs - gapStartMs) < GAP_MS) {
    vTaskDelay(pdMS_TO_TICKS(50));
    return;
  }

  // next condition
  gapStartMs = 0;
  condIndex++;
  if (condIndex >= N_CONDS) {
    condIndex = 0;
    repIndex++;
  }
  if (repIndex >= REPEAT) {
    // done
    setSleepAllowed(true);
    if (adv) adv->stop();
    syncEnd();
    vTaskDelay(pdMS_TO_TICKS(1000));
    return;
  }

  beginCondition(CONDS[condIndex]);
  vTaskDelay(pdMS_TO_TICKS(200));
}
