// Mode C2' フラッシュ版: subjectXX_ccs.csv を使わず、labels配列をフラッシュに埋め込む版。
// - labels_generated.h を生成して include することも可。
// - interval は ADV_MS で固定。1トライアル300 advで終了。TICK/SYNCは従来通り。
// - HAR計算なし。ラベル再生のみ。

#include <Arduino.h>

#include <NimBLEDevice.h>  // ArduinoBLEと衝突しないようNimBLEを明示利用

// フラッシュ内に全セッションのラベルを持たせる
#include "../labels_all.h"

static const uint16_t ADV_MS        = 100;    // 固定間隔
static const uint16_t N_ADV_PER_TR  = 300;
static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN      = 2;

NimBLEAdvertising* adv = nullptr;
uint32_t nextAdvMs=0;
uint16_t advCount=0;
bool trialRunning=false;
uint8_t sessionIdx=0;
const uint8_t* labels=nullptr;
uint16_t nLabels=0;
uint16_t advIntervalMs = 100;
static const uint16_t ADV_LIST[] = {100, 500, 1000, 2000};
static const uint8_t NUM_ADV_LIST = sizeof(ADV_LIST)/sizeof(ADV_LIST[0]);
uint8_t advIdx = 0;

static inline String makeMFD(uint16_t seq, uint8_t label){
  char buf[16];
  snprintf(buf, sizeof(buf), "%04u_%u", (unsigned)seq, (unsigned)label);
  return String(buf);
}

void syncStart(){ digitalWrite(LED_PIN, HIGH); digitalWrite(SYNC_OUT_PIN, HIGH); }
void syncEnd(){   digitalWrite(SYNC_OUT_PIN, LOW); digitalWrite(LED_PIN, LOW); }

void startTrial(){
  advCount=0;
  nextAdvMs = millis();
  syncStart();
  trialRunning=true;
  Serial.printf("[TX] start trial session=%s interval=%ums labels=%u (flash)\n",
                SESSIONS[sessionIdx].id,
                (unsigned)advIntervalMs,
                (unsigned)nLabels);
}
void endTrial(){
  trialRunning=false;
  syncEnd();
  Serial.printf("[TX] end trial session=%s interval=%ums adv_sent=%u\n",
                SESSIONS[sessionIdx].id,
                (unsigned)advIntervalMs,
                (unsigned)advCount);
  // 次のセッションへローテート（セッション1→10の後にintervalを切り替える二重ループ）
  sessionIdx = (sessionIdx + 1) % NUM_SESSIONS;
  if (sessionIdx == 0) { // 1周終えたらintervalを次へ
    advIdx = (advIdx + 1) % NUM_ADV_LIST;
    advIntervalMs = ADV_LIST[advIdx];
  }
  labels  = SESSIONS[sessionIdx].seq;
  nLabels = SESSIONS[sessionIdx].len;
  // 次セッション用にBLE intervalを更新
  if (adv) {
    uint16_t itv = (uint16_t)lroundf(advIntervalMs / 0.625f);
    adv->setMinInterval(itv);
    adv->setMaxInterval(itv);
  }
  startTrial();
}

void setup(){
  Serial.begin(115200);
  delay(50);
  Serial.println("[TX] FW=TX_ModeC2prime_1202_flash");
  pinMode(LED_PIN, OUTPUT); digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT); digitalWrite(SYNC_OUT_PIN, LOW);
  pinMode(TICK_OUT_PIN, OUTPUT); digitalWrite(TICK_OUT_PIN, LOW);

  NimBLEDevice::init("TXM_LABEL_FLASH");
  NimBLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = NimBLEDevice::getAdvertising();

  // 最初のセッションをセット
  labels  = SESSIONS[sessionIdx].seq;
  nLabels = SESSIONS[sessionIdx].len;
  advIntervalMs = ADV_LIST[advIdx];

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

void loop(){
  if(!trialRunning){
    vTaskDelay(1000);
    return;
  }
  uint32_t nowMs = millis();
  if((int32_t)(nowMs - nextAdvMs) >= 0){
    nextAdvMs += advIntervalMs;
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
    if((advCount % 50)==0){
      Serial.printf("[TX] adv=%u label=%u\n", (unsigned)advCount, (unsigned)lbl);
    }
    if(advCount >= N_ADV_PER_TR){
      endTrial();
    }
  }
  vTaskDelay(1);
}
