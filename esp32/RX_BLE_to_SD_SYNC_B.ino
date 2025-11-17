// === RX_BLE_to_SD_SYNC_B.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// 機能：パッシブスキャンでTXのMFD("MFxxxx")を受信 → SDへ記録。
//       SYNC(26)で試行ファイルを開始/終了。
// 配線：SYNC_IN=26 ← ①の SYNC_OUT=25
//      SD: CS=5, SCK=18, MISO=19, MOSI=23
//
// 出力：/logs/rx_trial_XXX.csv
//   ms,event,rssi,addr,mfd

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>

#ifndef __has_include
  #define __has_include(x) 0
#endif
#if __has_include(<NimBLEDevice.h>)
  #include <NimBLEDevice.h>
  #define USE_NIMBLE 1
#else
  #include <BLEDevice.h>
  #include <BLEUtils.h>
  #include <BLEScan.h>
  #define USE_NIMBLE 0
#endif

static const int SD_CS                = 5;
static const int SYNC_IN              = 26;
static const uint16_t ADV_INTERVAL_MS = 100;
static const uint32_t TRIAL_MS        = 60000; // 旧固定窓（互換性のため残置・通常はSYNCで区切る）

#ifndef SCAN_MS
  #define SCAN_MS 50
#endif

volatile bool syncLvl=false, syncEdge=false;
File f;
static const char FW_TAG[] = "RX_BLE_to_SD_SYNC_B";
static uint32_t trialIndex = 0;

static inline int nib(char c){
  if(c>='0'&&c<='9')return c-'0';
  if(c>='A'&&c<='F')return c-'A'+10;
  if(c>='a'&&c<='f')return c-'a'+10;
  return -1;
}
static bool parseMFD(const String&s, uint16_t& seq){
  if (s.length()<6) return false;
  if (!(s[0]=='M'&&s[1]=='F')) return false;
  int n0=nib(s[2]),n1=nib(s[3]),n2=nib(s[4]),n3=nib(s[5]);
  if (n0<0||n1<0||n2<0||n3<0) return false;
  seq=(uint16_t)((n0<<12)|(n1<<8)|(n2<<4)|n3);
  return true;
}

String txLock="";             // 最初に見えた送信機にロック
uint32_t t0Ms=0; bool trial=false;
uint32_t rxCount=0;

void IRAM_ATTR onSync(){
  bool s=digitalRead(SYNC_IN);
  if (s!=syncLvl){ syncLvl=s; syncEdge=true; }
}

String nextPath(){
  SD.mkdir("/logs");
  char p[64];
  for(uint32_t id=1;;++id){
    snprintf(p,sizeof(p),"/logs/rx_trial_%03lu.csv",(unsigned long)id);
    if(!SD.exists(p)) return String(p);
  }
}

void startTrial(){
  String path=nextPath();
  f=SD.open(path, FILE_WRITE);
  if (f){
    f.println("ms,event,rssi,addr,mfd");
    trialIndex++;
    f.printf("# meta, firmware=%s, trial_index=%lu\r\n", FW_TAG, (unsigned long)trialIndex);
  }
  t0Ms=millis(); trial=true; txLock=""; rxCount=0;
  Serial.printf("[RX] start %s (trial=%lu)\n", path.c_str(), (unsigned long)trialIndex);
}

void endTrial(){
  if (trial){
    trial=false;
    if (f){ f.flush(); f.close(); }
    uint32_t t_ms = millis() - t0Ms;
    double dur_s = t_ms / 1000.0;
    double rate_hz = (dur_s>0.0)? ((double)rxCount / dur_s) : 0.0;
    double expected = (double)t_ms / (double)ADV_INTERVAL_MS;
    double pdr = (expected>0.0)? ((double)rxCount / expected) : 0.0;
    Serial.printf("[RX] summary trial=%lu ms_total=%lu, rx=%lu, rate_hz=%.2f, est_pdr=%.3f\n",
                  (unsigned long)trialIndex,
                  (unsigned long)t_ms, (unsigned long)rxCount, rate_hz, pdr);
    Serial.println("[RX] end");
  }
}

#if USE_NIMBLE
NimBLEScan* gScan=nullptr;
class CB: public NimBLEAdvertisedDeviceCallbacks{
  void onResult(NimBLEAdvertisedDevice* d) override {
    if (!trial) return;
    String mfd = String(d->getManufacturerData().c_str());
    uint16_t seq=0; if(!parseMFD(mfd,seq)) return;
    String addr = String(d->getAddress().toString().c_str());
    if (txLock.length()==0) txLock = addr;
    if (addr != txLock) return;

    uint32_t ms = millis() - t0Ms;
    if (f){
      f.printf("%lu,ADV,%d,%s,%s\r\n",
               (unsigned long)ms, d->getRSSI(), addr.c_str(), mfd.c_str());
      rxCount++;
    }
  }
};
CB cb;
#else
BLEScan* gScan=nullptr;
class CB: public BLEAdvertisedDeviceCallbacks{
  void onResult(BLEAdvertisedDevice d) override {
    if (!trial) return;
    String mfd = String(d.getManufacturerData().c_str());
    uint16_t seq=0; if(!parseMFD(mfd,seq)) return;
    String addr = String(d.getAddress().toString().c_str());
    if (txLock.length()==0) txLock = addr;
    if (addr != txLock) return;

    uint32_t ms = millis() - t0Ms;
    if (f){
      f.printf("%lu,ADV,%d,%s,%s\r\n",
               (unsigned long)ms, d.getRSSI(), addr.c_str(), mfd.c_str());
      rxCount++;
    }
  }
};
CB cb;
#endif

void setup(){
  Serial.begin(115200);

  // SD
  SPI.begin(18,19,23,SD_CS);
  if(!SD.begin(SD_CS)){ Serial.println("[SD] init FAIL"); while(1) delay(1000); }

  // SYNC
  pinMode(SYNC_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(SYNC_IN), onSync, CHANGE);
  syncLvl=digitalRead(SYNC_IN);
  if (syncLvl) startTrial();

  // BLE passive scan (rho=1)
#if USE_NIMBLE
  NimBLEDevice::init("RX_ESP32");
  gScan = NimBLEDevice::getScan();
  gScan->setActiveScan(false);
  gScan->setInterval(SCAN_MS);
  gScan->setWindow(SCAN_MS);
  gScan->setAdvertisedDeviceCallbacks(&cb);
  gScan->start(0, false);
#else
  BLEDevice::init("RX_ESP32");
  gScan = BLEDevice::getScan();
  gScan->setActiveScan(false);
  gScan->setInterval(SCAN_MS);
  gScan->setWindow(SCAN_MS);
  gScan->setAdvertisedDeviceCallbacks(&cb, true);
  gScan->start(0, nullptr, false);
#endif
  Serial.println("[RX] ready");
}

void loop(){
  if (syncEdge){
    noInterrupts(); bool s=syncLvl; syncEdge=false; interrupts();
    if (s && !trial) {
      startTrial();
    } else if (!s && trial) {
      endTrial();
    }
  }
}
