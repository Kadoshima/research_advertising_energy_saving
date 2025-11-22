// === RX_BLE_to_SD_SYNC_ON.ino ===
// 役割: SYNC(26)の立ち上がりでtrial開始、立ち下がりで終了。BLEパッシブスキャンを継続。
// 使い分け: ON計測向け（複数トライアルをSYNCパルスで区切る）。

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include <esp_bt.h>
#include <esp_bt_main.h>
#include <esp_gap_ble_api.h>
#include <esp_gatt_defs.h>

#ifdef USE_NIMBLE
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
static const uint16_t ADV_INTERVAL_MS = 100; // メタ用、解析側で参照可

#ifndef SCAN_MS
  #define SCAN_MS 50
#endif

volatile bool syncLvl=false, syncEdge=false;
File f;
static const char FW_TAG[] = "RX_BLE_to_SD_SYNC_ON";
static uint32_t trialIndex = 0;

static inline int nib(char c){
  if(c>='0'&&c<='9')return c-'0';
  if(c>='A'&&c<='F')return c-'A'+10;
  if(c>='a'&&c<='f')return c-'a'+10;
  return -1;
}
static bool parseMFD(const String&s, uint16_t& seq){
  if (s.length()<6) return false;
  int a=nib(s[2]), b=nib(s[3]), c=nib(s[4]), d=nib(s[5]);
  if (a<0||b<0||c<0||d<0) return false;
  seq = (a<<12)|(b<<8)|(c<<4)|d;
  return true;
}

volatile uint32_t t0Ms=0;
volatile bool trial=false;
volatile uint32_t rxCount=0;
volatile String txLock="";

void IRAM_ATTR onSync(){
  bool lvl=digitalRead(SYNC_IN);
  syncLvl=lvl; syncEdge=true;
}

static void startTrial(){
  char fname[32];
  snprintf(fname,sizeof(fname),"/logs/rx_trial_%03u.csv", (unsigned)(++trialIndex));
  f = SD.open(fname, FILE_WRITE);
  txLock = "";
  rxCount = 0;
  trial = true;
  t0Ms = millis();
  if (f){
    f.printf("# start, trial=%u\r\n", (unsigned)trialIndex);
    f.printf("# meta, adv_interval_ms=%u, fw=%s\r\n", (unsigned)ADV_INTERVAL_MS, FW_TAG);
    f.printf("ms,event,rssi,addr,mfd\r\n");
  }
}

static void endTrial(){
  if (f){
    uint32_t dur = millis() - t0Ms;
    f.printf("# summary trial=%u ms_total=%lu rx=%u\r\n",
             (unsigned)trialIndex, (unsigned long)dur, (unsigned)rxCount);
    f.close();
    f=File();
  }
  trial=false;
}

#if USE_NIMBLE
class CB: public NimBLEAdvertisedDeviceCallbacks{
  void onResult(NimBLEAdvertisedDevice* d) override {
    if (!trial) return;
    std::string md = d->getManufacturerData();
    String mfd = String(md.c_str());
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

  SPI.begin(18,19,23,SD_CS);
  if(!SD.begin(SD_CS)){ Serial.println("[SD] init FAIL"); while(1) delay(1000); }

  pinMode(SYNC_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(SYNC_IN), onSync, CHANGE);
  syncLvl=digitalRead(SYNC_IN);
  if (syncLvl) startTrial();

#if USE_NIMBLE
  NimBLEDevice::init("RX_ESP32");
  auto scan = NimBLEDevice::getScan();
  scan->setActiveScan(false);
  scan->setInterval(SCAN_MS);
  scan->setWindow(SCAN_MS);
  scan->setAdvertisedDeviceCallbacks(&cb);
  scan->start(0, false);
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

