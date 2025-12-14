// TX_UCCS_D1_100_500.ino (uccs_d1_scan90)
//
// Step D1 (実機・最小):
// - Fixed100 / Fixed500 / Policy(100↔500) を 1回の起動で自動実行し、RX/TXSDのログで成立確認する。
// - TXSD向けに SYNC(25) と preamble TICK(27) を出す（cond_idの通知）。
// - ManufacturerData: "<tx_elapsed_ms>_<label>"
//     fixed:  F100 / F500
//     policy: P100 / P500（現在のinterval）
//
// 注: U/CCSは現状 “synthetic” 生成（実機HARに差し替える前提）。

#include <Arduino.h>
#include <BLEDevice.h>
#include <math.h>

#ifdef ARDUINO_ARCH_ESP32
#include "esp_pm.h"
#endif

// ==== 実行スケジュール ====
static const uint32_t TRIAL_DURATION_MS = 60000; // 1条件 1分
static const uint32_t GAP_MS = 5000;             // 条件間ギャップ
static const uint8_t N_CYCLES = 3;               // (3条件)×3 = 9試行

// ==== ピン ====
static const int SYNC_OUT_PIN = 25; // TX -> RX/TXSD SYNC
static const int TICK_OUT_PIN = 27; // TX -> TXSD TICK (preamble)
static const int LED_PIN = 2;

// ==== オプション ====
static const bool USE_LED = false;
static const bool ENABLE_TICK_PREAMBLE = true;
static const bool RESTART_ADV_ON_INTERVAL_CHANGE = true; // interval変更を確実に反映させたい場合はtrue

// ==== actions（実機は 100↔500 に固定） ====
static const uint16_t ACTIONS[] = {100, 500};
static const uint8_t N_ACTIONS = sizeof(ACTIONS) / sizeof(ACTIONS[0]);

// ==== 代表ポリシー（D0で確定） ====
static const float U_MID = 0.20f;
static const float U_HIGH = 0.35f;
static const float C_MID = 0.20f;
static const float C_HIGH = 0.35f;
static const float HYST = 0.02f;

// ==== synthetic U/CCS source（暫定） ====
static const uint32_t SIG_PERIOD_MS = 5000;
static const uint32_t SIG_BURST_MS = 2000;
static const float U_STABLE = 0.10f;
static const float U_BURST = 0.60f;
static const float C_STABLE = 0.10f;
static const float C_BURST = 0.60f;
static const float EMA_ALPHA = 0.20f; // 0..1

// ==== BLE ====
static BLEAdvertising* adv = nullptr;

#ifdef ARDUINO_ARCH_ESP32
static esp_pm_lock_handle_t noLightSleepLock = nullptr;
static bool sleepBlocked = false;
#endif

enum Mode : uint8_t { MODE_FIXED = 0, MODE_POLICY = 1 };

struct Condition {
  uint8_t cond_id;     // TXSD: preamble pulses
  Mode mode;
  uint16_t fixed_ms;   // MODE_FIXED のときのみ有効
  const char* label;   // 固定条件の label（例: F100）
};

// cond_id:
// 1: fixed100, 2: fixed500, 3: policy
static const Condition CONDS[] = {
  {1, MODE_FIXED, 100, "F100"},
  {2, MODE_FIXED, 500, "F500"},
  {3, MODE_POLICY, 500, "POLICY"},
};
static const uint8_t N_CONDS = sizeof(CONDS) / sizeof(CONDS[0]);

// state
static bool trialRunning = false;
static uint32_t trialStartMs = 0;
static uint32_t gapStartMs = 0;
static uint8_t condIndex = 0;
static uint8_t cycleIndex = 0;
static uint32_t nextUpdateMs = 0;
static uint16_t currentIntervalMs = 500;
static float uEma = U_STABLE;
static float cEma = C_STABLE;

static inline uint16_t ms_to_0p625(float ms) {
  long v = lroundf(ms / 0.625f);
  if (v < 0x20) v = 0x20;     // 20ms minimum
  if (v > 0x4000) v = 0x4000; // 10.24s maximum
  return (uint16_t)v;
}

static uint16_t clamp_interval(uint16_t interval_ms) {
  // nearest; tie-break smaller
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

static void tickPreamble(uint8_t nPulses) {
  if (!ENABLE_TICK_PREAMBLE) return;
  for (uint8_t i = 0; i < nPulses; i++) {
    digitalWrite(TICK_OUT_PIN, HIGH);
    delayMicroseconds(200);
    digitalWrite(TICK_OUT_PIN, LOW);
    delay(20);
  }
}

static void setAdvIntervalMs(uint16_t ms) {
  if (!adv) return;
  uint16_t units = ms_to_0p625((float)ms);
  adv->setMinInterval(units);
  adv->setMaxInterval(units);
}

static void setPayload(uint32_t elapsed_ms, const char* label) {
  if (!adv) return;
  BLEAdvertisementData ad;
  ad.setName("TX_UCCS_D1");
  String mfd = String((unsigned long)elapsed_ms) + "_" + String(label);
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

static void updateSignals(uint32_t elapsed_ms) {
  // synthetic: periodic burst
  const uint32_t t = (SIG_PERIOD_MS > 0) ? (elapsed_ms % SIG_PERIOD_MS) : 0;
  const bool burst = (t < SIG_BURST_MS);
  const float uRaw = burst ? U_BURST : U_STABLE;
  const float cRaw = burst ? C_BURST : C_STABLE;
  uEma = EMA_ALPHA * uRaw + (1.0f - EMA_ALPHA) * uEma;
  cEma = EMA_ALPHA * cRaw + (1.0f - EMA_ALPHA) * cEma;
}

static uint16_t policyStep(uint16_t prevInterval, float u, float c) {
  // Mirror scripts/sweep_policy_pareto.py (then clamp to actions).
  const float u_hi_up = U_HIGH;
  const float u_hi_down = U_HIGH - HYST;
  const float u_mid_down = U_MID - HYST;
  const float c_hi_up = C_HIGH;
  const float c_hi_down = C_HIGH - HYST;
  const float c_mid_down = C_MID - HYST;

  uint16_t next = prevInterval;
  if (prevInterval == 500) {
    if ((u >= u_hi_up) || (c >= c_hi_up)) {
      next = 100;
    } else if ((u < u_mid_down) && (c < c_mid_down)) {
      next = 2000;
    }
  } else { // prevInterval == 100
    if ((u < u_mid_down) && (c < c_mid_down)) {
      next = 500;
    }
    if ((u < u_hi_down) && (c < c_hi_down) && (u < u_mid_down) && (c < c_mid_down)) {
      next = 2000;
    }
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

static void startTrial(const Condition& c) {
  trialStartMs = millis();
  trialRunning = true;

  // D1は原則 sleep ON で運用（必要ならここを変える）
  setSleepAllowed(true);

  // init per-trial state
  uEma = U_STABLE;
  cEma = C_STABLE;
  currentIntervalMs = (c.mode == MODE_FIXED) ? c.fixed_ms : 500;
  currentIntervalMs = clamp_interval(currentIntervalMs);

  setAdvIntervalMs(currentIntervalMs);
  setPayload(0, (c.mode == MODE_FIXED) ? c.label : (currentIntervalMs == 100 ? "P100" : "P500"));

  syncStart();
  if (adv) adv->start();

  // TXSD/RXがSYNC立上りを検出する猶予
  delay(200);
  tickPreamble(c.cond_id);

  nextUpdateMs = millis();
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

  BLEDevice::init("TX_UCCS_D1");
  BLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = BLEDevice::getAdvertising();
  adv->setScanResponse(false);
  adv->setMinPreferred(0);

#ifdef ARDUINO_ARCH_ESP32
  (void)esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP, 0, "uccs_d1", &noLightSleepLock);
#endif

  condIndex = 0;
  cycleIndex = 0;
  gapStartMs = 0;

  startTrial(CONDS[condIndex]);
}

void loop() {
  const uint32_t nowMs = millis();

  if (trialRunning) {
    const uint32_t elapsed = nowMs - trialStartMs;
    if (elapsed >= TRIAL_DURATION_MS) {
      endTrial();
      vTaskDelay(pdMS_TO_TICKS(200));
      return;
    }

    if ((int32_t)(nowMs - nextUpdateMs) >= 0) {
      const Condition& c = CONDS[condIndex];

      uint32_t t_ms = nowMs - trialStartMs;
      if (t_ms > 65535UL) t_ms = 65535UL; // RX側のseq(uint16)互換のため（trialは60s想定）

      if (c.mode == MODE_POLICY) {
        updateSignals(t_ms);
        uint16_t nextI = policyStep(currentIntervalMs, uEma, cEma);
        applyInterval(nextI);
        const char* lbl = (currentIntervalMs == 100) ? "P100" : "P500";
        setPayload(t_ms, lbl);
      } else {
        // fixed
        setPayload(t_ms, c.label);
      }

      // update cadence follows (possibly updated) currentIntervalMs
      nextUpdateMs = millis() + currentIntervalMs;
    }
    vTaskDelay(1);
    return;
  }

  // gap中
  if (gapStartMs == 0) gapStartMs = nowMs;
  if ((nowMs - gapStartMs) < GAP_MS) {
    vTaskDelay(pdMS_TO_TICKS(50));
    return;
  }

  // 次条件へ
  condIndex++;
  if (condIndex >= N_CONDS) {
    condIndex = 0;
    cycleIndex++;
  }
  if (cycleIndex >= N_CYCLES) {
    // 完了（広告停止、SYNC LOW）
    setSleepAllowed(true);
    vTaskDelay(pdMS_TO_TICKS(1000));
    return;
  }

  gapStartMs = 0;
  startTrial(CONDS[condIndex]);
  vTaskDelay(pdMS_TO_TICKS(200));
}
