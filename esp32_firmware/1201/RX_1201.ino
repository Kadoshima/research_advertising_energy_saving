// === RX_1201.ino ===
// パッシブスキャン受信ロガー。SYNC_INで試行開始/終了。リングバッファでSDに書き込み。
// 100ms短パルス対策として、最短試行長 MIN_TRIAL_MS を設け、SYNCが短すぎる場合は無視。

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

static const int SD_CS    = 5;
static const int SD_SCK   = 18;
static const int SD_MISO  = 19;
static const int SD_MOSI  = 23;
static const int SYNC_IN  = 26;
static const uint16_t SCAN_MS = 50;
static const uint32_t TRIAL_MS = 660000;   // フォールバック
static const uint32_t MIN_TRIAL_MS = 1000; // 1秒未満は試行として扱わない（短パルス対策）

// リングバッファ
static const uint16_t RX_BUF_SIZE = 512;
static const uint32_t FLUSH_INTERVAL_MS = 500;
struct RxEntry { uint32_t ms; int8_t rssi; char addr[18]; char mfd[8]; };
static RxEntry rxBuf[RX_BUF_SIZE];
static volatile uint16_t rxHead=0; static uint16_t rxTail=0;
static uint32_t bufOverflow=0; static uint32_t lastFlushMs=0;

volatile bool syncLvl=false, syncEdge=false; bool trial=false; File f;
static const char FW_TAG[]="RX_1201"; static uint32_t trialIndex=0; uint32_t t0Ms=0; uint32_t rxCount=0;

// --- ユーティリティ ---
static inline int nib(char c){ if(c>='0'&&c<='9')return c-'0'; if(c>='A'&&c<='F')return c-'A'+10; if(c>='a'&&c<='f')return c-'a'+10; return -1; }
static bool parseMFD(const std::string& s){ return s.size()>=2 && s[0]=='M' && s[1]=='F' && nib(s[2])>=0 && nib(s[3])>=0 && nib(s[4])>=0 && nib(s[5])>=0; }

void IRAM_ATTR onSync(){ bool s=digitalRead(SYNC_IN); if(s!=syncLvl){ syncLvl=s; syncEdge=true; } }

static String nextPath(){ SD.mkdir("/logs"); char p[64]; for(uint32_t id=1;;++id){ snprintf(p,sizeof(p),"/logs/rx_trial_%03lu.csv",(unsigned long)id); if(!SD.exists(p)) return String(p);} }

static void flushBuffer(){ if(!f) return; uint16_t head=rxHead; while(rxTail!=head){ RxEntry& e=rxBuf[rxTail]; f.printf("%lu,ADV,%d,%s,%s\r\n", (unsigned long)e.ms,(int)e.rssi,e.addr,e.mfd); rxTail=(rxTail+1)%RX_BUF_SIZE; }}

static void startTrial(){ String path=nextPath(); f=SD.open(path, FILE_WRITE); if(f){ f.println("ms,event,rssi,addr,mfd"); trialIndex++; f.printf("# meta, firmware=%s, trial_index=%lu\r\n", FW_TAG,(unsigned long)trialIndex);} t0Ms=millis(); trial=true; rxCount=0; rxHead=rxTail=0; bufOverflow=0; lastFlushMs=millis(); Serial.printf("[RX] start %s\n", path.c_str()); }

static void endTrial(){ if(!trial) return; trial=false; flushBuffer(); if(f){ f.flush(); f.close(); }
  uint32_t t_ms = millis() - t0Ms;
  if (t_ms < MIN_TRIAL_MS){ Serial.printf("[RX] ignore short trial (%lums)\n", (unsigned long)t_ms); return; }
  double rate_hz = t_ms>0 ? (double)rxCount / (t_ms/1000.0) : 0.0;
  double pdr = (double)rxCount / ( (double)t_ms / 100.0 ); // interval=100ms想定フォールバック
  Serial.printf("[RX] summary trial=%lu ms_total=%lu, rx=%lu, rate_hz=%.2f, est_pdr_expected=%.3f, buf_overflow=%lu\n", (unsigned long)trialIndex, (unsigned long)t_ms, (unsigned long)rxCount, rate_hz, pdr, (unsigned long)bufOverflow);
  Serial.println("[RX] end");
}

void setup(){
  Serial.begin(115200);
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS); if(!SD.begin(SD_CS)){ Serial.println("[SD] init FAIL"); while(1) delay(1000);}
  pinMode(SYNC_IN, INPUT_PULLDOWN); attachInterrupt(digitalPinToInterrupt(SYNC_IN), onSync, CHANGE); syncLvl=digitalRead(SYNC_IN);

#if USE_NIMBLE
  class CB: public NimBLEAdvertisedDeviceCallbacks{
    void onResult(NimBLEAdvertisedDevice* d) override {
      if (!trial) return;
      const std::string& mfd = d->getManufacturerData();
      if (!parseMFD(mfd)) return;
      const std::string addr = d->getAddress().toString();
      uint16_t nextH = (rxHead + 1) % RX_BUF_SIZE; if (nextH == rxTail){ bufOverflow++; return; }
      RxEntry& e = rxBuf[rxHead];
      e.ms = millis() - t0Ms; e.rssi = (int8_t)d->getRSSI();
      strncpy(e.addr, addr.c_str(), sizeof(e.addr)-1); e.addr[sizeof(e.addr)-1]='\0';
      strncpy(e.mfd, mfd.c_str(), sizeof(e.mfd)-1); e.mfd[sizeof(e.mfd)-1]='\0';
      rxHead = nextH; rxCount++;
    }
  };

  NimBLEDevice::init("RX_ESP32");
  NimBLEScan* scan=NimBLEDevice::getScan();
  scan->setActiveScan(false);
  scan->setInterval(SCAN_MS);
  scan->setWindow(SCAN_MS);
  scan->setAdvertisedDeviceCallbacks(new CB());
  scan->start(0,false);
#else
  class CB: public BLEAdvertisedDeviceCallbacks{
    void onResult(BLEAdvertisedDevice d) override {
      if (!trial) return;
      String mfdStr = d.getManufacturerData();
      if (mfdStr.length() < 6 || mfdStr[0]!='M' || mfdStr[1]!='F') return;
      String addrStr = d.getAddress().toString();
      uint16_t nextH = (rxHead + 1) % RX_BUF_SIZE; if (nextH == rxTail){ bufOverflow++; return; }
      RxEntry& e = rxBuf[rxHead];
      e.ms = millis() - t0Ms; e.rssi = (int8_t)d.getRSSI();
      strncpy(e.addr, addrStr.c_str(), sizeof(e.addr)-1); e.addr[sizeof(e.addr)-1]='\0';
      strncpy(e.mfd, mfdStr.c_str(), sizeof(e.mfd)-1); e.mfd[sizeof(e.mfd)-1]='\0';
      rxHead = nextH; rxCount++;
    }
  };

  BLEDevice::init("RX_ESP32");
  BLEScan* scan = BLEDevice::getScan();
  scan->setActiveScan(false);
  scan->setInterval(SCAN_MS);
  scan->setWindow(SCAN_MS);
  scan->setAdvertisedDeviceCallbacks(new CB(), true);
  scan->start(0, nullptr, false);
#endif

  if (syncLvl) startTrial();
  Serial.printf("[RX] ready (buf=%u, flush=%lums)\n", (unsigned)RX_BUF_SIZE, (unsigned long)FLUSH_INTERVAL_MS);
}

void loop(){
  if (syncEdge){ noInterrupts(); bool s=syncLvl; syncEdge=false; interrupts(); if (s && !trial) startTrial(); else if (!s && trial) endTrial(); }
  if (trial){ uint32_t now=millis(); if (now - lastFlushMs >= FLUSH_INTERVAL_MS){ flushBuffer(); lastFlushMs=now; }
    if ((millis()-t0Ms) >= TRIAL_MS) endTrial();
  }
  vTaskDelay(1);
}
