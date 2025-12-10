// Mode C2' flash (stress labels): play labels_stress.h (SESSIONS_STRESS) — 1210版
// Schedule: select one stress session (S_IDX) and one fixed interval (INTERVAL_MS).
// TICK/SYNC same as before. No HAR computation.

#include <Arduino.h>
#include <NimBLEDevice.h>
#include <cmath>

// Stress sessions embedded in flash
#include "../labels_stress.h"  // defines SESSIONS_STRESS[], NUM_SESSIONS_STRESS

// --- Config ---
static const uint8_t S_IDX = 0;           // 0-based index into SESSIONS_STRESS (e.g., 0=S1, 3=S4)
static const uint16_t INTERVAL_MS = 100;  // fixed interval for this build (e.g., 100 or 2000)
static const uint8_t REPEAT = 1;          // how many trials to repeat for the same session/interval
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
  labels = SESSIONS_STRESS[S_IDX].seq;
  nLabels = SESSIONS_STRESS[S_IDX].len;
  uint16_t effectiveLen = (nLabels > EFFECTIVE_LEN) ? EFFECTIVE_LEN : nLabels;
  stepCount = (INTERVAL_MS + 99) / 100;              // 100→1, 2000→20
  targetAdv = (effectiveLen + stepCount - 1) / stepCount;

  if (adv) {
    uint16_t itv = (uint16_t)lroundf(INTERVAL_MS / 0.625f);
    adv->setMinInterval(itv);
    adv->setMaxInterval(itv);
  }
  syncStart();
  trialRunning = true;
  Serial.printf("[TX] start stress=%s interval=%ums repeat=%u/%u adv_target=%lu step=%u len=%u eff_len=%u\n",
                SESSIONS_STRESS[S_IDX].id,
                (unsigned)INTERVAL_MS,
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
    allDone = true;
    if (adv) adv->stop();
    Serial.println("[TX] all trials completed (stress fixed interval)");
  }
}

void endTrial() {
  trialRunning = false;
  syncEnd();
  Serial.printf("[TX] end stress=%s interval=%ums adv_sent=%u step=%u\n",
                SESSIONS_STRESS[S_IDX].id,
                (unsigned)INTERVAL_MS,
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
  labels = SESSIONS_STRESS[S_IDX].seq;
  nLabels = SESSIONS_STRESS[S_IDX].len;
  NimBLEAdvertisementData ad;
  ad.setName("TXM_LABEL");
  std::string mfd0 = makeMFD(0, labels[0]).c_str();
  ad.setManufacturerData(mfd0);
  uint16_t itv0 = (uint16_t)lroundf(INTERVAL_MS / 0.625f);
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
    nextAdvMs += INTERVAL_MS;
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
