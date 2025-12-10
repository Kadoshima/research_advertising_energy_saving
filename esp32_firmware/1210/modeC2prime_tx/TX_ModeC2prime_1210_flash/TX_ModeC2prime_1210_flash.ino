// Mode C2' flash: play labels from labels_all.h (embedded) — 1210版
// Schedule: subjects range × INTERVALS (100/500/1000/2000 ms) × REPEAT_PER_INTERVAL.
// Each trial length = subject timeline (100 ms grid) sampled at interval_ms.
//   target_adv = ceil(nLabels / stepCount) where stepCount = ceil(interval_ms/100).
// TICK/SYNC same as before. No HAR computation.

#include <Arduino.h>
#include <NimBLEDevice.h>  // Explicit NimBLE use (avoid ArduinoBLE)
#include <cmath>

// All subjects are embedded in flash via labels_all.h
#include "../labels_all.h"

static const uint16_t N_ADV_PER_TR = 300;
static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN = 2;

// Intervals to sweep per subject
static const uint16_t INTERVALS[] = {100, 500, 1000, 2000};
static const uint8_t NUM_INTERVALS = sizeof(INTERVALS) / sizeof(INTERVALS[0]);
static const uint8_t REPEAT_PER_INTERVAL = 1;   // per interval
static const uint8_t SUBJECT_START = 0;         // inclusive index into SESSIONS
static const uint8_t SUBJECT_END = NUM_SESSIONS; // exclusive upper bound
static const uint16_t EFFECTIVE_LEN = 6352;     // clamp subject length to common window (100ms grid)

NimBLEAdvertising* adv = nullptr;
uint32_t nextAdvMs = 0;
uint16_t advCount = 0;
bool trialRunning = false;
bool allDone = false;

uint8_t subjectIdx = SUBJECT_START;
uint8_t intervalIdx = 0;
uint8_t repeatIdx = 0;
uint16_t advIntervalMs = INTERVALS[0];
const uint8_t* labels = nullptr;
uint16_t nLabels = 0;
uint16_t stepCount = 1;      // interval_ms / 100ms
uint32_t targetAdv = 0;      // ceil(nLabels / stepCount)

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
  labels = SESSIONS[subjectIdx].seq;
  nLabels = SESSIONS[subjectIdx].len;
  uint16_t effectiveLen = (nLabels > EFFECTIVE_LEN) ? EFFECTIVE_LEN : nLabels;
  advIntervalMs = INTERVALS[intervalIdx];
  // stepCount: how many 100ms ticks we skip per packet
  stepCount = (advIntervalMs + 99) / 100;  // expect 1,5,10,20
  targetAdv = (effectiveLen + stepCount - 1) / stepCount;  // ceil division
  if (adv) {
    uint16_t itv = (uint16_t)lroundf(advIntervalMs / 0.625f);
    adv->setMinInterval(itv);
    adv->setMaxInterval(itv);
  }
  syncStart();
  trialRunning = true;
  Serial.printf("[TX] start subj=%s interval=%ums repeat=%u/%u adv_target=%lu step=%u len=%u\n",
                SESSIONS[subjectIdx].id,
                (unsigned)advIntervalMs,
                (unsigned)(repeatIdx + 1),
                (unsigned)REPEAT_PER_INTERVAL,
                (unsigned long)targetAdv,
                (unsigned)stepCount,
                (unsigned)nLabels);
}

void advanceScheduleOrStop() {
  repeatIdx++;
  if (repeatIdx >= REPEAT_PER_INTERVAL) {
    repeatIdx = 0;
    intervalIdx++;
    if (intervalIdx >= NUM_INTERVALS) {
      intervalIdx = 0;
      subjectIdx++;
    }
  }

  if (subjectIdx >= NUM_SESSIONS) {
    allDone = true;
    if (adv) adv->stop();
    Serial.println("[TX] all trials completed");
  }
}

void endTrial() {
  trialRunning = false;
  syncEnd();
  Serial.printf("[TX] end subj=%s interval=%ums adv_sent=%u step=%u\n",
                SESSIONS[subjectIdx].id,
                (unsigned)advIntervalMs,
                (unsigned)advCount,
                (unsigned)stepCount);

  // Hold SYNC LOW before starting the next trial so RX/TXSD can detect the boundary.
  vTaskDelay(pdMS_TO_TICKS(1000));

  advanceScheduleOrStop();
  if (!allDone) startTrial();
}

void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("[TX] FW=TX_ModeC2prime_1210_flash (fixed intervals sweep)");
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);
  digitalWrite(SYNC_OUT_PIN, LOW);
  pinMode(TICK_OUT_PIN, OUTPUT);
  digitalWrite(TICK_OUT_PIN, LOW);

  NimBLEDevice::init("TXM_LABEL_FLASH");
  NimBLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = NimBLEDevice::getAdvertising();

  // seed with first subject/interval
  labels = SESSIONS[subjectIdx].seq;
  nLabels = SESSIONS[subjectIdx].len;
  advIntervalMs = INTERVALS[intervalIdx];

  NimBLEAdvertisementData ad;
  ad.setName("TXM_LABEL");
  std::string mfd0 = makeMFD(0, labels[0]).c_str();
  ad.setManufacturerData(mfd0);
  uint16_t itv0 = (uint16_t)lroundf(advIntervalMs / 0.625f);
  adv->setMinInterval(itv0);
  adv->setMaxInterval(itv0);
  adv->setAdvertisementData(ad);
  adv->start();

  startTrial();
}

void loop() {
  if (allDone) {
    vTaskDelay(1000);
    return;
  }
  if (!trialRunning) {
    vTaskDelay(10);
    return;
  }

  uint32_t nowMs = millis();
  if ((int32_t)(nowMs - nextAdvMs) >= 0) {
    nextAdvMs += advIntervalMs;
    uint32_t idx = advCount * stepCount;
    uint16_t effectiveLen = (nLabels > EFFECTIVE_LEN) ? EFFECTIVE_LEN : nLabels;
    if (idx >= effectiveLen) idx = effectiveLen - 1;  // clamp to last label
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
