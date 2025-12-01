// === RX_1201.ino ===
// パッシブスキャン受信ロガー。SYNCは使わず、MFDのseqからsoft_trialを生成してCSVに記録。
// セッション全体を1ファイルに出力: ms,event,rssi,seq,soft_trial,addr,mfd

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
static const int SYNC_IN  = 26;  // 未使用だがPulldown
static const uint16_t SCAN_MS = 50;

// リングバッファ
static const uint16_t RX_BUF_SIZE = 512;
static const uint32_t FLUSH_INTERVAL_MS = 500;
struct RxEntry { uint32_t ms; int8_t rssi; uint16_t seq; uint16_t trialSoft; char addr[18]; char mfd[8]; };
static RxEntry rxBuf[RX_BUF_SIZE];
static volatile uint16_t rxHead=0; static uint16_t rxTail=0;
static uint32_t bufOverflow=0; static uint32_t lastFlushMs=0;

volatile bool syncLvl=false, syncEdge=false; bool trial=false; File f;
static const char FW_TAG[]="RX_1201"; static uint32_t trialIndex=0; uint32_t t0Ms=0; uint32_t rxCount=0;
static uint16_t lastSeq=0; static bool haveLastSeq=false; static uint32_t softTrialIndex=1;

// --- ユーティリティ ---
static inline int nib(char c){ if(c>='0'&&c<='9')return c-'0'; if(c>='A'&&c<='F')return c-'A'+10; if(c>='a'&&c<='f')return c-'a'+10; return -1; }
static bool parseMFD(const std::string& s, uint16_t& seq){
  if (s.size()<6) return false;
  if (s[0]!='M' || s[1]!='F') return false;
  int n0=nib(s[2]),n1=nib(s[3]),n2=nib(s[4]),n3=nib(s[5]);
  if (n0<0||n1<0||n2<0||n3<0) return false;
  seq = (uint16_t)((n0<<12)|(n1<<8)|(n2<<4)|n3);
  return true;
}
static bool parseMFD(const String& s, uint16_t& seq){
  if (s.length()<6) return false;
  if (s[0]!='M' || s[1]!='F') return false;
  int n0=nib(s[2]),n1=nib(s[3]),n2=nib(s[4]),n3=nib(s[5]);
  if (n0<0||n1<0||n2<0||n3<0) return false;
  seq = (uint16_t)((n0<<12)|(n1<<8)|(n2<<4)|n3);
  return true;
}

// SYNCは使用しないが、ピンは安全のためPulldownに設定するのみ
static void IRAM_ATTR onSync(){ /* no-op */ }

static String nextPath(){ SD.mkdir("/logs"); char p[64]; for(uint32_t id=1;;++id){ snprintf(p,sizeof(p),"/logs/rx_trial_%03lu.csv",(unsigned long)id); if(!SD.exists(p)) return String(p);} }

static void flushBuffer(){
  if(!f) return;
  uint16_t head=rxHead;
  while(rxTail!=head){
    RxEntry& e=rxBuf[rxTail];
    f.printf("%lu,ADV,%d,%u,%u,%s,%s\r\n",
             (unsigned long)e.ms,(int)e.rssi,(unsigned)e.seq,(unsigned)e.trialSoft,e.addr,e.mfd);
    rxTail=(rxTail+1)%RX_BUF_SIZE;
  }
}

static void startTrial(){
  String path=nextPath();
  f=SD.open(path, FILE_WRITE);
  if(f){
    f.println("ms,event,rssi,seq,soft_trial,addr,mfd");
    trialIndex++;
    f.printf("# meta, firmware=%s, trial_index=%lu\r\n", FW_TAG,(unsigned long)trialIndex);
  }
  t0Ms=millis(); trial=true; rxCount=0; rxHead=rxTail=0; bufOverflow=0; lastFlushMs=millis();
  haveLastSeq=false; softTrialIndex=1;
  Serial.printf("[RX] start %s\n", path.c_str());
}

static void endTrial(){
  if(!trial) return;
  trial=false;
  flushBuffer();
  if(f){ f.flush(); f.close(); }
  uint32_t t_ms = millis() - t0Ms;
  double rate_hz = t_ms>0 ? (double)rxCount / (t_ms/1000.0) : 0.0;
  Serial.printf("[RX] summary trial=%lu ms_total=%lu, rx=%lu, rate_hz=%.2f, buf_overflow=%lu\n",
                (unsigned long)trialIndex, (unsigned long)t_ms, (unsigned long)rxCount, rate_hz, (unsigned long)bufOverflow);
  Serial.println("[RX] end");
}

void setup(){
  Serial.begin(115200);
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if(!SD.begin(SD_CS)){ Serial.println("[SD] init FAIL"); while(1) delay(1000);}
  pinMode(SYNC_IN, INPUT_PULLDOWN); // SYNCは使用しない

#if USE_NIMBLE
  class CB: public NimBLEAdvertisedDeviceCallbacks{
    void onResult(NimBLEAdvertisedDevice* d) override {
      if (!trial) return;
      const std::string& mfd = d->getManufacturerData();
      uint16_t seq;
      if (!parseMFD(mfd, seq)) return;
      if (!haveLastSeq){ haveLastSeq=true; lastSeq=seq; softTrialIndex=1; }
      else { if (seq < lastSeq) softTrialIndex++; lastSeq=seq; }
      const std::string addr = d->getAddress().toString();
      uint16_t nextH = (rxHead + 1) % RX_BUF_SIZE; if (nextH == rxTail){ bufOverflow++; return; }
      RxEntry& e = rxBuf[rxHead];
      e.ms = millis() - t0Ms; e.rssi = (int8_t)d->getRSSI();
      e.seq = seq; e.trialSoft = (uint16_t)softTrialIndex;
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
      uint16_t seq;
      if (!parseMFD(mfdStr, seq)) return;
      if (!haveLastSeq){ haveLastSeq=true; lastSeq=seq; softTrialIndex=1; }
      else { if (seq < lastSeq) softTrialIndex++; lastSeq=seq; }
      String addrStr = d.getAddress().toString();
      uint16_t nextH = (rxHead + 1) % RX_BUF_SIZE; if (nextH == rxTail){ bufOverflow++; return; }
      RxEntry& e = rxBuf[rxHead];
      e.ms = millis() - t0Ms; e.rssi = (int8_t)d.getRSSI();
      e.seq = seq; e.trialSoft = (uint16_t)softTrialIndex;
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

  // SYNCなし運用: 起動時に1本だけログを開始し、セッション全体を記録
  startTrial();
  Serial.printf("[RX] ready (buf=%u, flush=%lums)\n", (unsigned)RX_BUF_SIZE, (unsigned long)FLUSH_INTERVAL_MS);
}

void loop(){
  if (trial){
    uint32_t now=millis(); if (now - lastFlushMs >= FLUSH_INTERVAL_MS){ flushBuffer(); lastFlushMs=now; }
  }
  vTaskDelay(1);
}
