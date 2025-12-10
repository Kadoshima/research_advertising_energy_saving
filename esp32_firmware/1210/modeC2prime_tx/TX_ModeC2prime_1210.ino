// Mode C2' (HARラベル再生 + 固定広告間隔) 1210版
// - subjectXX_ccs.csv を SD から順に読み込み（1行1ラベル; 先頭フィールドを使用）
// - interval は ADV_MS で固定（例: 100ms or 2000ms）
// - 300 adv で1トライアル終了。TICK(27) と SYNC(25) を出力。ManufacturerData に label と seq を載せる。
// - HAR計算は行わず、ラベル再生のみ。
// - SDは TX 側に挿入する想定（TXSDとは別）。もしTXにSDを載せない場合は、labelsをフラッシュ配列に焼く実装に切り替えること。

#include <Arduino.h>
#include <BLEDevice.h>
#include <SPI.h>
#include <SD.h>

// --- 設定 ---
static const uint16_t ADV_MS        = 100;    // 固定広告間隔をここで切替 (100/500/1000/2000など)
static const uint16_t N_ADV_PER_TR  = 300;    // 1トライアルの広告回数
static const uint8_t  MAX_LABELS    = 400;    // 最大読み込み数
static const uint8_t  N_FILES       = 10;     // subject01_ccs.csv 〜 subject10_ccs.csv

// --- ピン ---
static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN      = 2;
static const int SD_CS        = 5;
static const int SD_SCK       = 18;
static const int SD_MISO      = 19;
static const int SD_MOSI      = 23;

// --- BLE ---
BLEAdvertising* adv = nullptr;
uint32_t nextAdvMs=0;
uint16_t advCount=0;
bool trialRunning=false;
uint8_t fileIndex=0; // 0〜N_FILES-1 を巡回

// --- ラベルバッファ ---
String labels[MAX_LABELS];
uint16_t nLabels=0;

// --- 助手 ---
static inline String makeMFD(uint16_t seq, const String& label){
  // 4桁のseq + '_' + label を載せる (最大12〜14文字程度)
  char buf[16];
  snprintf(buf, sizeof(buf), "%04u_%s", (unsigned)seq, label.c_str());
  return String(buf);
}

void syncStart(){
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
}
void syncEnd(){
  digitalWrite(SYNC_OUT_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
}

String makePath(){
  char p[32];
  snprintf(p,sizeof(p),"/subject%02u_ccs.csv",(unsigned)(fileIndex+1));
  return String(p);
}

bool loadLabels(){
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if(!SD.begin(SD_CS)){
    Serial.println("[TX] SD init FAIL");
    return false;
  }
  // SDカードはTX側に挿入し、TXSDとは別。ファイルは /subjectXX_ccs.csv の形式。
  File f = SD.open(makePath(), FILE_READ);
  if(!f){
    Serial.printf("[TX] open %s FAIL\n", makePath().c_str());
    return false;
  }
  nLabels=0;
  String line;
  while(f.available() && nLabels < MAX_LABELS){
    line = f.readStringUntil('\n');
    line.trim();
    if(line.length()==0) continue;
    int comma = line.indexOf(',');
    if(comma>0) line = line.substring(0, comma);
    labels[nLabels++] = line;
  }
  f.close();
  Serial.printf("[TX] labels loaded from %s: %u\n", makePath().c_str(), (unsigned)nLabels);
  return nLabels>0;
}

void startTrial(){
  advCount=0;
  nextAdvMs = millis();
  syncStart();
  trialRunning=true;
  Serial.printf("[TX] start trial interval=%ums labels=%u file=%s\n", (unsigned)ADV_MS, (unsigned)nLabels, makePath().c_str());
}
void endTrial(){
  trialRunning=false;
  syncEnd();
  Serial.printf("[TX] end trial adv_sent=%u\n", (unsigned)advCount);
  // 次ファイルへ
  fileIndex = (fileIndex + 1) % N_FILES;
}

void setup(){
  Serial.begin(115200);
  delay(50);
  pinMode(LED_PIN, OUTPUT); digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT); digitalWrite(SYNC_OUT_PIN, LOW);
  pinMode(TICK_OUT_PIN, OUTPUT); digitalWrite(TICK_OUT_PIN, LOW);

  if(!loadLabels()){
    Serial.println("[TX] label load failed; halt");
    while(1) delay(1000);
  }

  BLEDevice::init("TXM_LABEL");
  BLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = BLEDevice::getAdvertising();
  adv->setScanResponse(false);
  adv->setMinPreferred(0);

  // 初期広告データ
  BLEAdvertisementData ad;
  ad.setName("TXM_LABEL");
  ad.setManufacturerData(makeMFD(0, labels[0 % nLabels]));
  adv->setAdvertisementData(ad);
  adv->start();

  startTrial();
}

void loop(){
  if(!trialRunning){
    // 次ファイルをロードして再開
    if(loadLabels()){
      startTrial();
    }
    vTaskDelay(1000);
    return;
  }
  uint32_t nowMs = millis();
  if((int32_t)(nowMs - nextAdvMs) >= 0){
    nextAdvMs += ADV_MS;

    // set payload
    String lbl = labels[advCount % nLabels];
    BLEAdvertisementData ad;
    ad.setName("TXM_LABEL");
    ad.setManufacturerData(makeMFD(advCount, lbl));
    adv->setAdvertisementData(ad);

    // TICK pulse
    digitalWrite(TICK_OUT_PIN, HIGH);
    delayMicroseconds(200);
    digitalWrite(TICK_OUT_PIN, LOW);

    advCount++;
    if((advCount % 50)==0){
      Serial.printf("[TX] adv=%u label=%s\n", (unsigned)advCount, lbl.c_str());
    }
    if(advCount >= N_ADV_PER_TR){
      endTrial();
    }
  }
  vTaskDelay(1);
}
