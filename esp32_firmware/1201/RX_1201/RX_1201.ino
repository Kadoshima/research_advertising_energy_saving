// === RX_1201.ino (SYNCポーリング版) ===
// パッシブスキャン受信ロガー。SYNC_INをポーリングして試行開始/終了。
// リングバッファでSD書き込みをバッファリング。

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

// --- ピン設定 ---
static const int SD_CS    = 5;
static const int SD_SCK   = 18;
static const int SD_MISO  = 19;
static const int SD_MOSI  = 23;
static const int SYNC_IN  = 26;

// --- 試行・スキャン設定 ---
static const uint16_t SCAN_MS       = 50;
static const uint32_t TRIAL_MS_FALLBACK = 660000;  // SYNCを使わない場合のフォールバック（オプション）
static const uint32_t MIN_TRIAL_MS       = 1000;   // 1秒未満は試行とみなさない（ノイズ対策）
static const bool     USE_SYNC_END       = true;   // SYNC立下りで終了するか（true推奨）

// --- リングバッファ ---
static const uint16_t RX_BUF_SIZE        = 512;
static const uint32_t FLUSH_INTERVAL_MS  = 500;

struct RxEntry {
  uint32_t ms;
  int8_t   rssi;
  char     addr[18];
  char     mfd[8];
};

static RxEntry rxBuf[RX_BUF_SIZE];
static volatile uint16_t rxHead = 0;  // コールバック側（書き込み）
static uint16_t          rxTail = 0;  // loop側（読み出し）
static uint32_t          bufOverflow = 0;
static uint32_t          lastFlushMs = 0;

// --- SYNC & trial 状態 ---
static bool     syncPrev   = false;   // 直前ループのSYNCレベル
static bool     trial      = false;   // trial中か
static uint32_t t0Ms       = 0;       // trial開始時刻
static uint32_t rxCount    = 0;       // 受信ADV数
static uint32_t trialIndex = 0;
static uint32_t syncLowStartMs = 0;   // SYNCがLOWになり始めた時刻
static const uint32_t SYNC_OFF_DELAY_MS = 500; // 500ms未満の瞬断は無視

static File     f;
static const char FW_TAG[] = "RX_1201_SYNC_POLL";

// --- ユーティリティ ---
static inline int nib(char c){
  if(c>='0'&&c<='9')return c-'0';
  if(c>='A'&&c<='F')return c-'A'+10;
  if(c>='a'&&c<='f')return c-'a'+10;
  return -1;
}

// NimBLE用 MFDパース
static bool parseMFD(const std::string& s){
  if (s.size() < 6) return false;
  if (s[0] != 'M' || s[1] != 'F') return false;
  int n0=nib(s[2]), n1=nib(s[3]), n2=nib(s[4]), n3=nib(s[5]);
  if (n0<0||n1<0||n2<0||n3<0) return false;
  return true;
}

// Classic BLE用 MFDパース
static bool parseMFD(const String& s){
  if (s.length() < 6) return false;
  if (s[0] != 'M' || s[1] != 'F') return false;
  int n0=nib(s[2]), n1=nib(s[3]), n2=nib(s[4]), n3=nib(s[5]);
  if (n0<0||n1<0||n2<0||n3<0) return false;
  return true;
}

static String nextPath(){
  SD.mkdir("/logs");
  char p[64];
  for(uint32_t id=1;;++id){
    snprintf(p,sizeof(p),"/logs/rx_trial_%03lu.csv",(unsigned long)id);
    if(!SD.exists(p)) return String(p);
  }
}

// バッファをSDへフラッシュ
static void flushBuffer(){
  if (!f) return;
  uint16_t head = rxHead; // volatile読み出し
  while (rxTail != head){
    RxEntry& e = rxBuf[rxTail];
    f.printf("%lu,ADV,%d,%s,%s\r\n",
             (unsigned long)e.ms,
             (int)e.rssi,
             e.addr,
             e.mfd);
    rxTail = (rxTail + 1) % RX_BUF_SIZE;
  }
}

static void startTrial(){
  String path = nextPath();
  f = SD.open(path, FILE_WRITE);
  if (f){
    f.println("ms,event,rssi,addr,mfd");
    trialIndex++;
    f.printf("# meta, firmware=%s, trial_index=%lu, buf_size=%u\r\n",
             FW_TAG, (unsigned long)trialIndex, (unsigned)RX_BUF_SIZE);
  }
  trial    = true;
  t0Ms     = millis();
  rxCount  = 0;
  rxHead   = 0;
  rxTail   = 0;
  bufOverflow = 0;
  lastFlushMs = t0Ms;
  Serial.printf("[RX] start %s (trial=%lu)\n", path.c_str(), (unsigned long)trialIndex);
}

static void endTrial(bool fromTimeout = false){
  if (!trial) return;
  trial = false;

  flushBuffer();
  if (f){
    f.flush();
    f.close();
  }

  uint32_t t_ms = millis() - t0Ms;
  if (t_ms < MIN_TRIAL_MS){
    Serial.printf("[RX] ignore short trial (%lums)\n", (unsigned long)t_ms);
    return;
  }

  double dur_s   = t_ms / 1000.0;
  double rate_hz = (dur_s>0.0) ? ((double)rxCount / dur_s) : 0.0;
  // 期待値PDRは便宜的に100ms interval想定のままにしておく（必要ならTX側メタと合わせて計算）
  double expected = (double)t_ms / 100.0;
  double pdr      = (expected>0.0) ? ((double)rxCount / expected) : 0.0;

  Serial.printf("[RX] summary trial=%lu ms_total=%lu, rx=%lu, rate_hz=%.2f, est_pdr_expected=%.3f, buf_overflow=%lu%s\n",
                (unsigned long)trialIndex,
                (unsigned long)t_ms,
                (unsigned long)rxCount,
                rate_hz,
                pdr,
                (unsigned long)bufOverflow,
                fromTimeout ? " (timeout)" : "");
  Serial.println("[RX] end");
}

// === BLEコールバック ===
#if USE_NIMBLE
class CB: public NimBLEAdvertisedDeviceCallbacks{
  void onResult(NimBLEAdvertisedDevice* d) override {
    if (!trial) return;
    const std::string& mfd = d->getManufacturerData();
    if (!parseMFD(mfd)) return;
    const std::string addr = d->getAddress().toString();

    uint16_t nextH = (rxHead + 1) % RX_BUF_SIZE;
    if (nextH == rxTail){
      bufOverflow++;
      return;
    }

    RxEntry& e = rxBuf[rxHead];
    e.ms   = millis() - t0Ms;
    e.rssi = (int8_t)d->getRSSI();
    strncpy(e.addr, addr.c_str(), sizeof(e.addr)-1);
    e.addr[sizeof(e.addr)-1] = '\0';
    strncpy(e.mfd, mfd.c_str(), sizeof(e.mfd)-1);
    e.mfd[sizeof(e.mfd)-1] = '\0';

    rxHead = nextH;
    rxCount++;
  }
};
#else
class CB: public BLEAdvertisedDeviceCallbacks{
  void onResult(BLEAdvertisedDevice d) override {
    if (!trial) return;
    String mfdStr  = d.getManufacturerData();
    uint16_t dummySeq;
    if (!parseMFD(mfdStr)) return;

    String addrStr = d.getAddress().toString();

    uint16_t nextH = (rxHead + 1) % RX_BUF_SIZE;
    if (nextH == rxTail){
      bufOverflow++;
      return;
    }

    RxEntry& e = rxBuf[rxHead];
    e.ms   = millis() - t0Ms;
    e.rssi = (int8_t)d.getRSSI();
    strncpy(e.addr, addrStr.c_str(), sizeof(e.addr)-1);
    e.addr[sizeof(e.addr)-1] = '\0';
    strncpy(e.mfd, mfdStr.c_str(), sizeof(e.mfd)-1);
    e.mfd[sizeof(e.mfd)-1] = '\0';

    rxHead = nextH;
    rxCount++;
  }
};
#endif

void setup(){
  Serial.begin(115200);

  // --- SD初期化 ---
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)){
    Serial.println("[SD] init FAIL");
    while(1) delay(1000);
  }

  // --- SYNC入力（割り込みは使わない） ---
  pinMode(SYNC_IN, INPUT_PULLDOWN);
  syncPrev = digitalRead(SYNC_IN); // ここでは trial を開始しない

  // --- BLE Passive Scan 初期化 ---
#if USE_NIMBLE
  NimBLEDevice::init("RX_ESP32");
  NimBLEScan* scan = NimBLEDevice::getScan();
  scan->setActiveScan(false);
  scan->setInterval(SCAN_MS);
  scan->setWindow(SCAN_MS);
  scan->setAdvertisedDeviceCallbacks(new CB());
  scan->start(0, false);
#else
  BLEDevice::init("RX_ESP32");
  BLEScan* scan = BLEDevice::getScan();
  scan->setActiveScan(false);
  scan->setInterval(SCAN_MS);
  scan->setWindow(SCAN_MS);
  scan->setAdvertisedDeviceCallbacks(new CB(), true);
  scan->start(0, nullptr, false);
#endif

  Serial.printf("[RX] ready (buf=%u, flush=%lums)\n",
                (unsigned)RX_BUF_SIZE,
                (unsigned long)FLUSH_INTERVAL_MS);
}

void loop(){
  uint32_t nowMs = millis();

  // --- SYNC ポーリングによる trial 開始/終了検出（OFF遅延付き） ---
  bool syncCur = digitalRead(SYNC_IN);

  // 立ち上がり: すぐ開始
  if (syncCur && !trial){
    startTrial();
    syncLowStartMs = 0;
  }

  // 立ち下がり: 500ms以上続いたら終了（瞬断無視）
  if (trial){
    if (!syncCur){
      if (syncLowStartMs == 0) syncLowStartMs = nowMs;
      if (nowMs - syncLowStartMs > SYNC_OFF_DELAY_MS && USE_SYNC_END){
        endTrial(false);
        syncLowStartMs = 0;
      }
    } else {
      // HIGHに戻ったらタイマーリセット
      syncLowStartMs = 0;
    }
  }

  // --- trial 中のフラッシュ & フォールバック終了 ---
  if (trial){
    if (nowMs - lastFlushMs >= FLUSH_INTERVAL_MS){
      flushBuffer();
      lastFlushMs = nowMs;
    }
    if (!USE_SYNC_END){
      if (nowMs - t0Ms >= TRIAL_MS_FALLBACK){
        endTrial(true);
      }
    }
  }

  vTaskDelay(1);
}
