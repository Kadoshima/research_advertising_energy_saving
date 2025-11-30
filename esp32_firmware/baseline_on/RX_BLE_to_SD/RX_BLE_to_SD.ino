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
//
// 2025-11-30: バッファリング実装（SD書き込みボトルネック対策）
//   - コールバックではリングバッファに書き込み（高速）
//   - loop()で定期的にSDへフラッシュ

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
static const uint32_t TRIAL_MS        = 660000; // フォールバック用（11分 = 2000ms×300+α）
static const bool USE_SYNC_END        = true;   // ON向け: SYNC立ち下がりで終了（TX/TXSDと同期）

#ifndef SCAN_MS
  #define SCAN_MS 50
#endif

// ===== リングバッファ設定 =====
// 100ms interval で 300回 = 最大300エントリ
// 余裕を見て512エントリ、各48バイト → 約24KB
static const uint16_t RX_BUF_SIZE = 512;
static const uint32_t FLUSH_INTERVAL_MS = 500;  // 500ms毎にSDへフラッシュ

struct RxEntry {
  uint32_t ms;
  int8_t rssi;
  char addr[18];  // "xx:xx:xx:xx:xx:xx" + null
  char mfd[8];    // "MFxxxx" + null
};

static RxEntry rxBuf[RX_BUF_SIZE];
static volatile uint16_t rxBufHead = 0;  // 書き込み位置（コールバック）
static uint16_t rxBufTail = 0;           // 読み出し位置（loop）
static uint32_t lastFlushMs = 0;
static uint32_t bufOverflow = 0;         // オーバーフローカウント

volatile bool syncLvl=false, syncEdge=false;
File f;
static const char FW_TAG[] = "RX_BLE_to_SD_SYNC_C";  // バージョンアップ
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

char txLockAddr[18] = "";  // 最初に見えた送信機にロック
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

// バッファをSDにフラッシュ
void flushBuffer(){
  if (!f) return;

  uint16_t head = rxBufHead;  // volatile読み出し
  while (rxBufTail != head) {
    RxEntry& e = rxBuf[rxBufTail];
    f.printf("%lu,ADV,%d,%s,%s\r\n",
             (unsigned long)e.ms, (int)e.rssi, e.addr, e.mfd);
    rxBufTail = (rxBufTail + 1) % RX_BUF_SIZE;
  }
}

void startTrial(){
  String path=nextPath();
  f=SD.open(path, FILE_WRITE);
  if (f){
    f.println("ms,event,rssi,addr,mfd");
    trialIndex++;
    f.printf("# meta, firmware=%s, trial_index=%lu, adv_interval_ms=%u, buf_size=%u\r\n",
             FW_TAG, (unsigned long)trialIndex, (unsigned)ADV_INTERVAL_MS, (unsigned)RX_BUF_SIZE);
  }
  t0Ms=millis();
  trial=true;
  txLockAddr[0]='\0';
  rxCount=0;
  rxBufHead=0;
  rxBufTail=0;
  bufOverflow=0;
  lastFlushMs=millis();
  Serial.printf("[RX] start %s (trial=%lu)\n", path.c_str(), (unsigned long)trialIndex);
}

void endTrial(){
  if (trial){
    trial=false;

    // 残りバッファをフラッシュ
    flushBuffer();

    if (f){ f.flush(); f.close(); }
    uint32_t t_ms = millis() - t0Ms;
    double dur_s = t_ms / 1000.0;
    double rate_hz = (dur_s>0.0)? ((double)rxCount / dur_s) : 0.0;
    double expected = (double)t_ms / (double)ADV_INTERVAL_MS;
    double pdr = (expected>0.0)? ((double)rxCount / expected) : 0.0;
    Serial.printf("[RX] summary trial=%lu ms_total=%lu, rx=%lu, rate_hz=%.2f, est_pdr_expected=%.3f, buf_overflow=%lu\n",
                  (unsigned long)trialIndex,
                  (unsigned long)t_ms, (unsigned long)rxCount, rate_hz, pdr,
                  (unsigned long)bufOverflow);
    Serial.println("[RX] end");
  }
}

#if USE_NIMBLE
NimBLEScan* gScan=nullptr;
class CB: public NimBLEAdvertisedDeviceCallbacks{
  void onResult(NimBLEAdvertisedDevice* d) override {
    if (!trial) return;

    // MFDパース
    std::string mfdStd = d->getManufacturerData();
    if (mfdStd.length() < 6) return;
    if (mfdStd[0] != 'M' || mfdStd[1] != 'F') return;

    // アドレス取得
    std::string addrStd = d->getAddress().toString();

    // 最初のTXにロック
    if (txLockAddr[0] == '\0') {
      strncpy(txLockAddr, addrStd.c_str(), sizeof(txLockAddr)-1);
      txLockAddr[sizeof(txLockAddr)-1] = '\0';
    }
    if (strncmp(txLockAddr, addrStd.c_str(), sizeof(txLockAddr)) != 0) return;

    // リングバッファに書き込み（高速）
    uint16_t nextHead = (rxBufHead + 1) % RX_BUF_SIZE;
    if (nextHead == rxBufTail) {
      // バッファフル - オーバーフロー
      bufOverflow++;
      return;
    }

    RxEntry& e = rxBuf[rxBufHead];
    e.ms = millis() - t0Ms;
    e.rssi = (int8_t)d->getRSSI();
    strncpy(e.addr, addrStd.c_str(), sizeof(e.addr)-1);
    e.addr[sizeof(e.addr)-1] = '\0';
    strncpy(e.mfd, mfdStd.c_str(), sizeof(e.mfd)-1);
    e.mfd[sizeof(e.mfd)-1] = '\0';

    rxBufHead = nextHead;
    rxCount++;
  }
};
CB cb;
#else
BLEScan* gScan=nullptr;
class CB: public BLEAdvertisedDeviceCallbacks{
  void onResult(BLEAdvertisedDevice d) override {
    if (!trial) return;

    // MFDパース (Arduino String版)
    String mfdStr = d.getManufacturerData();
    if (mfdStr.length() < 6) return;
    if (mfdStr[0] != 'M' || mfdStr[1] != 'F') return;

    // アドレス取得 (Arduino String版)
    String addrStr = d.getAddress().toString();

    // 最初のTXにロック
    if (txLockAddr[0] == '\0') {
      strncpy(txLockAddr, addrStr.c_str(), sizeof(txLockAddr)-1);
      txLockAddr[sizeof(txLockAddr)-1] = '\0';
    }
    if (strncmp(txLockAddr, addrStr.c_str(), sizeof(txLockAddr)) != 0) return;

    // リングバッファに書き込み（高速）
    uint16_t nextHead = (rxBufHead + 1) % RX_BUF_SIZE;
    if (nextHead == rxBufTail) {
      // バッファフル - オーバーフロー
      bufOverflow++;
      return;
    }

    RxEntry& e = rxBuf[rxBufHead];
    e.ms = millis() - t0Ms;
    e.rssi = (int8_t)d.getRSSI();
    strncpy(e.addr, addrStr.c_str(), sizeof(e.addr)-1);
    e.addr[sizeof(e.addr)-1] = '\0';
    strncpy(e.mfd, mfdStr.c_str(), sizeof(e.mfd)-1);
    e.mfd[sizeof(e.mfd)-1] = '\0';

    rxBufHead = nextHead;
    rxCount++;
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
  Serial.printf("[RX] ready (buffered, buf_size=%u, flush_interval=%lums)\n",
                (unsigned)RX_BUF_SIZE, (unsigned long)FLUSH_INTERVAL_MS);
}

void loop(){
  if (syncEdge){
    noInterrupts(); bool s=syncLvl; syncEdge=false; interrupts();
    if (s && !trial) {
      startTrial();
    } else if (USE_SYNC_END && !s && trial) {
      endTrial();
    }
  }

  // 定期的にバッファをSDへフラッシュ
  if (trial) {
    uint32_t now = millis();
    if (now - lastFlushMs >= FLUSH_INTERVAL_MS) {
      flushBuffer();
      lastFlushMs = now;
    }
  }

  // 固定窓での自動終了（SYNC立ち下がりを無視する場合）
  if (trial && !USE_SYNC_END){
    if ((millis() - t0Ms) >= TRIAL_MS){
      endTrial();
    }
  }
}
