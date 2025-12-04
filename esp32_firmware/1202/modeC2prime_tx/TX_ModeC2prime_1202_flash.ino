// Mode C2' フラッシュ版: subjectXX_ccs.csv を使わず、labels配列をフラッシュに埋め込む版。
// - labels_generated.h を生成して include することも可。
// - interval は ADV_MS で固定。1トライアル300 advで終了。TICK/SYNCは従来通り。
// - HAR計算なし。ラベル再生のみ。

#include <Arduino.h>

#ifndef __has_include
  #define __has_include(x) 0
#endif
#if __has_include(<NimBLEDevice.h>)
  #include <NimBLEDevice.h>
  #define USE_NIMBLE 1
#else
  #include <BLEDevice.h>
  #define USE_NIMBLE 0
#endif

// ラベル列を定義したヘッダをここで選択（例: subject05）
#include "../labels_subjects/labels_subject05.h"  // 他のsubjectに差し替える場合はここを変更

static const uint16_t ADV_MS        = 100;    // 固定間隔
static const uint16_t N_ADV_PER_TR  = 300;
static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN      = 2;

// labels_generated.h を生成して include する場合:
//   python3 scripts/gen_labels_header.py --csv <path> --label-col <col> --out esp32_firmware/1202/modeC2prime_tx/labels_generated.h
//   生成後、下の include を有効にし、手書き配列は削除/コメントアウト
//   既に用意済みの subject別ヘッダ: esp32_firmware/1202/modeC2prime_tx/labels_subjects/labels_subjectXX.h
//   例) #include "labels_subjects/labels_subject05.h"  // subject05_ccsのラベル列
// #include "labels_generated.h"

// 手書きサンプル（生成ヘッダを使う場合はこの配列を削除）
#ifndef nLabels
static const char* labels[] = { "0","0","1","1","2","2","0","1","2","0" };
static const uint16_t nLabels = sizeof(labels)/sizeof(labels[0]);
#endif

#if USE_NIMBLE
NimBLEAdvertising* adv = nullptr;
#else
BLEAdvertising* adv = nullptr;
#endif
uint32_t nextAdvMs=0;
uint16_t advCount=0;
bool trialRunning=false;

static inline String makeMFD(uint16_t seq, const char* label){
  char buf[16];
  snprintf(buf, sizeof(buf), "%04u_%s", (unsigned)seq, label);
  return String(buf);
}

void syncStart(){ digitalWrite(LED_PIN, HIGH); digitalWrite(SYNC_OUT_PIN, HIGH); }
void syncEnd(){   digitalWrite(SYNC_OUT_PIN, LOW); digitalWrite(LED_PIN, LOW); }

void startTrial(){
  advCount=0;
  nextAdvMs = millis();
  syncStart();
  trialRunning=true;
  Serial.printf("[TX] start trial interval=%ums labels=%u (flash)\n", (unsigned)ADV_MS, (unsigned)nLabels);
}
void endTrial(){
  trialRunning=false;
  syncEnd();
  Serial.printf("[TX] end trial adv_sent=%u\n", (unsigned)advCount);
}

void setup(){
  Serial.begin(115200);
  delay(50);
  pinMode(LED_PIN, OUTPUT); digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT); digitalWrite(SYNC_OUT_PIN, LOW);
  pinMode(TICK_OUT_PIN, OUTPUT); digitalWrite(TICK_OUT_PIN, LOW);

#if USE_NIMBLE
  NimBLEDevice::init("TXM_LABEL_FLASH");
  NimBLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = NimBLEDevice::getAdvertising();
#else
  BLEDevice::init("TXM_LABEL_FLASH");
  BLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = BLEDevice::getAdvertising();
#endif
  adv->setScanResponse(false);
  adv->setMinPreferred(0);

#if USE_NIMBLE
  NimBLEAdvertisementData ad;
#else
  BLEAdvertisementData ad;
#endif
  ad.setName("TXM_LABEL");
  ad.setManufacturerData(makeMFD(0, labels[0]));
  adv->setAdvertisementData(ad);
  adv->start();

  startTrial();
}

void loop(){
  if(!trialRunning){
    vTaskDelay(1000);
    return;
  }
  uint32_t nowMs = millis();
  if((int32_t)(nowMs - nextAdvMs) >= 0){
    nextAdvMs += ADV_MS;
    const char* lbl = labels[advCount % nLabels];
#if USE_NIMBLE
    NimBLEAdvertisementData ad;
#else
    BLEAdvertisementData ad;
#endif
    ad.setName("TXM_LABEL");
    ad.setManufacturerData(makeMFD(advCount, lbl));
    adv->setAdvertisementData(ad);

    digitalWrite(TICK_OUT_PIN, HIGH);
    delayMicroseconds(200);
    digitalWrite(TICK_OUT_PIN, LOW);

    advCount++;
    if((advCount % 50)==0){
      Serial.printf("[TX] adv=%u label=%s\n", (unsigned)advCount, lbl);
    }
    if(advCount >= N_ADV_PER_TR){
      endTrial();
    }
  }
  vTaskDelay(1);
}
