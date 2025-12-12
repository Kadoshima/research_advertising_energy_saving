// Mode C2' flash (stress labels): play labels_stress.h (SESSIONS_STRESS) — 1210版
// Auto sweep: sessions_list × intervals_list, each REPEAT times.
// TICK/SYNC same as before. No HAR computation.

#include <Arduino.h>
#include <NimBLEDevice.h>
#include <cmath>

// Stress sessions embedded in flash
#include "../labels_stress.h"  // defines SESSIONS_STRESS[], NUM_SESSIONS_STRESS

// --- Config ---
// Sessions to sweep (0-based index into SESSIONS_STRESS). For retake: S4 only.
static const uint8_t SESS_LIST[] = {3};
static const uint8_t N_SESS = sizeof(SESS_LIST) / sizeof(SESS_LIST[0]);
// Intervals to sweep. S4 @ 2000ms only.
static const uint16_t INTERVALS[] = {2000};
static const uint8_t N_INTERVALS = sizeof(INTERVALS) / sizeof(INTERVALS[0]);
static const uint8_t REPEAT = 1;          // how many trials per (session, interval)
static const uint16_t EFFECTIVE_LEN = 6352;  // clamp to common window (100ms grid)

// Pins
static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN      = 2;

// BLE
NimBLEAdvertising* adv = nullptr;
uint32_t nextAdvMs = 0;
uint16_t advCount = 0;
bool trialRunning = false;
bool allDone = false;
uint8_t repeatIdx = 0;
uint8_t sessIdxPos = 0;
uint8_t intervalPos = 0;

const uint8_t* labels = nullptr;
uint16_t nLabels = 0;
uint16_t stepCount = 1;
uint32_t targetAdv = 0;

static inline String makeMFD(uint16_t seq, uint8_t label) {
  char buf[16];
  snprintf(buf, sizeof(buf), "%04u_%u", (unsigned)seq, (unsigned)label);
  return String(buf);
}

void syncStart() { digitalWrite(LED_PIN, HIGH); digitalWrite(SYNC_OUT_PIN, HIGH); }
void syncEnd() { digitalWrite(SYNC_OUT_PIN, LOW); digitalWrite(LED_PIN, LOW); }

void startTrial() {
  if (allDone) return;
  advCount = 0;
  nextAdvMs = millis();
  uint8_t sid = SESS_LIST[sessIdxPos];
  labels = SESSIONS_STRESS[sid].seq;
  nLabels = SESSIONS_STRESS[sid].len;
  uint16_t effectiveLen = (nLabels > EFFECTIVE_LEN) ? EFFECTIVE_LEN : nLabels;
  uint16_t intervalMs = INTERVALS[intervalPos];
  stepCount = (intervalMs + 99) / 100;              // 100→1, 2000→20
  targetAdv = (effectiveLen + stepCount - 1) / stepCount;

  if (adv) {
    uint16_t itv = (uint16_t)lroundf(intervalMs / 0.625f);
    adv->setMinInterval(itv);
    adv->setMaxInterval(itv);
  }
  syncStart();
  trialRunning = true;
  Serial.printf("[TX] start stress=%s interval=%ums repeat=%u/%u adv_target=%lu step=%u len=%u eff_len=%u\n",
                SESSIONS_STRESS[sid].id,
                (unsigned)intervalMs,
                (unsigned)(repeatIdx + 1),
                (unsigned)REPEAT,
                (unsigned long)targetAdv,
                (unsigned)stepCount,
                (unsigned)nLabels,
                (unsigned)((nLabels > EFFECTIVE_LEN) ? EFFECTIVE_LEN : nLabels));
}

void advanceOrStop() {
  repeatIdx++;
  if (repeatIdx >= REPEAT) {
    repeatIdx = 0;
    intervalPos++;
    if (intervalPos >= N_INTERVALS) {
      intervalPos = 0;
      sessIdxPos++;
    }
  }
  if (sessIdxPos >= N_SESS) {
    allDone = true;
    if (adv) adv->stop();
    Serial.println("[TX] all trials completed (stress fixed interval sweep)");
  }
}

void endTrial() {
  trialRunning = false;
  syncEnd();
  uint8_t sid = SESS_LIST[sessIdxPos];
  uint16_t intervalMs = INTERVALS[intervalPos];
  Serial.printf("[TX] end stress=%s interval=%ums adv_sent=%u step=%u\n",
                SESSIONS_STRESS[sid].id,
                (unsigned)intervalMs,
                (unsigned)advCount,
                (unsigned)stepCount);
  vTaskDelay(pdMS_TO_TICKS(1000));  // hold SYNC LOW before next
  advanceOrStop();
  if (!allDone) startTrial();
}

void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("[TX] FW=TX_ModeC2prime_1210_flash_stress (fixed interval)");
  pinMode(LED_PIN, OUTPUT); digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT); digitalWrite(SYNC_OUT_PIN, LOW);
  pinMode(TICK_OUT_PIN, OUTPUT); digitalWrite(TICK_OUT_PIN, LOW);

  NimBLEDevice::init("TXM_STRESS_FLASH");
  NimBLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = NimBLEDevice::getAdvertising();

  // seed first payload
  uint8_t sid0 = SESS_LIST[sessIdxPos];
  labels = SESSIONS_STRESS[sid0].seq;
  nLabels = SESSIONS_STRESS[sid0].len;
  NimBLEAdvertisementData ad;
  ad.setName("TXM_LABEL");
  std::string mfd0 = makeMFD(0, labels[0]).c_str();
  ad.setManufacturerData(mfd0);
  uint16_t itv0 = (uint16_t)lroundf(INTERVALS[intervalPos] / 0.625f);
  adv->setMinInterval(itv0);
  adv->setMaxInterval(itv0);
  adv->setAdvertisementData(ad);
  adv->start();

  startTrial();
}

void loop() {
  if (allDone) { vTaskDelay(1000); return; }
  if (!trialRunning) { vTaskDelay(10); return; }

  uint32_t nowMs = millis();
  if ((int32_t)(nowMs - nextAdvMs) >= 0) {
    nextAdvMs += INTERVALS[intervalPos];
    uint32_t idx = advCount * stepCount;
    uint16_t effectiveLen = (nLabels > EFFECTIVE_LEN) ? EFFECTIVE_LEN : nLabels;
    if (idx >= effectiveLen) idx = effectiveLen - 1;
    uint8_t lbl = labels[idx];

    NimBLEAdvertisementData ad;
    ad.setName("TXM_LABEL");
    std::string mfd = makeMFD(advCount, lbl).c_str();
    ad.setManufacturerData(mfd);
    adv->setAdvertisementData(ad);

    digitalWrite(TICK_OUT_PIN, HIGH);
    delayMicroseconds(200);
    digitalWrite(TICK_OUT_PIN, LOW);

    advCount++;
    if (advCount >= targetAdv) {
      endTrial();
    }
  }
  vTaskDelay(1);
}
