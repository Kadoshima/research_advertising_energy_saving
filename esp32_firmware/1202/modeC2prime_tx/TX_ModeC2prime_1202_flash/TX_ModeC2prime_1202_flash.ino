// Mode C2' フラッシュ版: subjectXX_ccs.csv を使わず、labels配列をフラッシュに埋め込む版。
// - 下の labels[] に必要なラベル列をハードコードする。
// - interval は ADV_MS で固定。1トライアル300 advで終了。TICK/SYNCは従来通り。
// - HAR計算なし。ラベル再生のみ。

#include <Arduino.h>
#include <BLEDevice.h>

static const uint16_t ADV_MS        = 100;    // 固定間隔
static const uint16_t N_ADV_PER_TR  = 300;
static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN      = 2;

// ここにラベル列を埋め込む（例として 10 件）
static const char* labels[] = {
  "0","0","1","1","2","2","0","1","2","0"
};
static const uint16_t nLabels = sizeof(labels)/sizeof(labels[0]);

BLEAdvertising* adv = nullptr;
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

  BLEDevice::init("TXM_LABEL_FLASH");
  BLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = BLEDevice::getAdvertising();
  adv->setScanResponse(false);
  adv->setMinPreferred(0);

  BLEAdvertisementData ad;
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
    BLEAdvertisementData ad;
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
