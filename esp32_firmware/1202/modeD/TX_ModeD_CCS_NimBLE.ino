// TX_ModeD_CCS_NimBLE.ino
// Uncertainty-driven advertising: intervals follow CCS_INTERVALS[] at 1s resolution.
// Labels are pulled from labels_all.h (select SUBJECT_IDX). NimBLE advertising.
// GPIOs: SYNC_OUT=25, TICK_OUT=27, LED=2 (same as Mode C2').

#include <Arduino.h>
#include <NimBLEDevice.h>

#include "../modeC2prime_tx/labels_all.h"          // subjectXX label arrays
#include "../../ccs_mode/ccs_session_data.h"       // CCS_INTERVALS (1s resolution)

static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN      = 2;

// Select which subject labels to replay (01..10)
static const uint8_t SUBJECT_IDX = 1; // 1-based: subject01

// Derived pointers
const SessionLabels* currentSession = nullptr;
const uint8_t* labels = nullptr;
uint16_t nLabels = 0;

NimBLEAdvertising* adv = nullptr;
uint32_t nextAdvMs = 0;
uint32_t nextCcsMs = 0;
uint16_t advCount = 0;
uint16_t ccsIdx = 0;
bool running = false;

static inline String makeMFD(uint16_t seq, uint8_t label){
  char buf[16];
  snprintf(buf, sizeof(buf), "%04u_%u", (unsigned)seq, (unsigned)label);
  return String(buf);
}

void syncStart(){ digitalWrite(LED_PIN, HIGH); digitalWrite(SYNC_OUT_PIN, HIGH); }
void syncEnd(){   digitalWrite(SYNC_OUT_PIN, LOW); digitalWrite(LED_PIN, LOW); }

void applyInterval(uint16_t intervalMs){
  if (!adv) return;
  uint16_t itv = (uint16_t)lroundf(intervalMs / 0.625f);
  adv->stop();
  adv->setMinInterval(itv);
  adv->setMaxInterval(itv);
  adv->start();
}

void startRun(){
  advCount = 0;
  ccsIdx = 0;
  nextAdvMs = millis();
  nextCcsMs = millis() + 1000;
  running = true;
  syncStart();
  Serial.printf("[TX] start ModeD subject=%s interval=%ums\n",
                currentSession->id,
                (unsigned)CCS_INTERVALS[0]);
  applyInterval(CCS_INTERVALS[0]);
}

void endRun(){
  running = false;
  syncEnd();
  Serial.printf("[TX] end ModeD subject=%s adv_sent=%u\n",
                currentSession->id,
                (unsigned)advCount);
}

void setup(){
  Serial.begin(115200);
  delay(50);
  Serial.println("[TX] FW=TX_ModeD_CCS_NimBLE");
  pinMode(LED_PIN, OUTPUT); digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT); digitalWrite(SYNC_OUT_PIN, LOW);
  pinMode(TICK_OUT_PIN, OUTPUT); digitalWrite(TICK_OUT_PIN, LOW);

  NimBLEDevice::init("TXM_CCS");
  NimBLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = NimBLEDevice::getAdvertising();

  // select subject
  uint8_t idx = (SUBJECT_IDX > 0 && SUBJECT_IDX <= NUM_SESSIONS) ? (SUBJECT_IDX - 1) : 0;
  currentSession = &SESSIONS[idx];
  labels = currentSession->seq;
  nLabels = currentSession->len;

  // initial advertisement payload
  NimBLEAdvertisementData ad;
  ad.setName("TXM_LABEL");
  std::string mfd0 = makeMFD(0, labels[0]).c_str();
  ad.setManufacturerData(mfd0);
  adv->setAdvertisementData(ad);
  adv->start();

  startRun();
}

void loop(){
  if (!running){
    vTaskDelay(1000);
    return;
  }
  uint32_t nowMs = millis();

  // per-adv scheduling
  if ((int32_t)(nowMs - nextAdvMs) >= 0){
    nextAdvMs += CCS_INTERVALS[ccsIdx];
    uint8_t lbl = labels[advCount % nLabels];
    NimBLEAdvertisementData ad;
    ad.setName("TXM_LABEL");
    std::string mfd = makeMFD(advCount, lbl).c_str();
    ad.setManufacturerData(mfd);
    adv->setAdvertisementData(ad);

    digitalWrite(TICK_OUT_PIN, HIGH);
    delayMicroseconds(200);
    digitalWrite(TICK_OUT_PIN, LOW);

    advCount++;
  }

  // per-ccs interval update (1s resolution)
  if ((int32_t)(nowMs - nextCcsMs) >= 0){
    nextCcsMs += 1000;
    if (ccsIdx + 1 < CCS_N_ENTRIES){
      ccsIdx++;
      applyInterval(CCS_INTERVALS[ccsIdx]);
      Serial.printf("[TX] ccs_idx=%u interval=%u adv=%u\n",
                    (unsigned)ccsIdx,
                    (unsigned)CCS_INTERVALS[ccsIdx],
                    (unsigned)advCount);
    } else {
      endRun();
    }
  }

  vTaskDelay(1);
}
