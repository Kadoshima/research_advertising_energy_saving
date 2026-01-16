// === RX_BLE_to_SD_SYNC_B.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// 機能：パッシブスキャンでTXのMFD("MFxxxx")を受信 → SDへ記録。
//       SYNCで試行ファイルを開始/終了（dual input + debounce）。
//
// 配線：
//   - SYNC_IN=26 ← TX SYNC_OUT
//   - SYNC_ALT_IN=25 ← (任意) 冗長SYNC
//   - SD: CS=5, SCK=18, MISO=19, MOSI=23
//
// 出力：/logs/rx_<millis>_<rand>.csv
//   prog_id,ms,event,rssi,addr,mfd

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
// esp_random()
#include <esp_system.h>

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

static const int SD_CS = 5;
static const int SYNC_IN = 26;
static const int SYNC_ALT_IN = 25;
static const uint16_t ADV_INTERVAL_MS = 100;
static const uint32_t TRIAL_MS_FALLBACK = 70000;
static const bool USE_SYNC_END = true;
static const char PROGRAM_ID[] = "RX_BLE_TO_SD_SYNC_B_20260116";

#ifndef SCAN_MS
  #define SCAN_MS 50
#endif

// Debug verbosity: 0=min, 1=edges+agent, 2=more agent detail, 3=periodic verbose
#ifndef DBG_LEVEL
#define DBG_LEVEL 1
#endif

static const uint16_t RX_BUF_SIZE = 512;
static const uint32_t FLUSH_INTERVAL_MS = 500;
static const char FW_TAG[] = "RX_BLE_to_SD_SYNC_B";

struct RxEntry {
  uint32_t ms;
  int8_t rssi;
  char addr[18];
  char mfd[8];
};

static RxEntry rxBuf[RX_BUF_SIZE];
static volatile uint16_t rxBufHead = 0;
static uint16_t rxBufTail = 0;
static uint32_t lastFlushMs = 0;
static uint32_t bufOverflow = 0;
static File f;
static uint32_t trialIndex = 0;

static inline int nib(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}
static inline void bytesToHex(const uint8_t* p, size_t n, char* out, size_t out_sz) {
  static const char* H = "0123456789ABCDEF";
  size_t j = 0;
  for (size_t i = 0; i < n && (j + 2) < out_sz; i++) {
    out[j++] = H[(p[i] >> 4) & 0xF];
    out[j++] = H[p[i] & 0xF];
  }
  out[j] = '\0';
}
static bool parseMfdAsciiMFxxxx(const uint8_t* data, size_t len, char out6[7], uint16_t& seq) {
  // Manufacturer data may include 2-byte Company ID prefix; search within payload.
  if (!data || len < 6) return false;
  for (size_t i = 0; (i + 6) <= len; i++) {
    if (data[i] != 'M' || data[i + 1] != 'F') continue;
    int n0 = nib((char)data[i + 2]);
    int n1 = nib((char)data[i + 3]);
    int n2 = nib((char)data[i + 4]);
    int n3 = nib((char)data[i + 5]);
    if (n0 < 0 || n1 < 0 || n2 < 0 || n3 < 0) continue;
    out6[0] = 'M';
    out6[1] = 'F';
    out6[2] = (char)data[i + 2];
    out6[3] = (char)data[i + 3];
    out6[4] = (char)data[i + 4];
    out6[5] = (char)data[i + 5];
    out6[6] = '\0';
    seq = (uint16_t)((n0 << 12) | (n1 << 8) | (n2 << 4) | n3);
    return true;
  }
  return false;
}

static char txLockAddr[18] = "";
static uint32_t t0Ms = 0;
static bool trial = false;
static uint32_t rxCount = 0;

// RX callback diagnostics (to distinguish "no packets seen" vs "filtered out")
static uint32_t cbTotal = 0;
static uint32_t cbMfdParseFail = 0;
static uint32_t cbAddrMismatch = 0;
static uint32_t cbBufDrop = 0;
static char cbFirstMfd[32] = "";
static char cbFirstAddr[18] = "";

static void makeNextPath(char* out, size_t out_sz) {
  SD.mkdir("/logs");
  uint32_t ms = millis();
  uint32_t r = (uint32_t)esp_random();
  snprintf(out, out_sz, "/logs/rx_%08lu_%08lx.csv", (unsigned long)ms, (unsigned long)r);
}

static void flushBuffer() {
  if (!f) return;
  uint16_t head = rxBufHead;
  while (rxBufTail != head) {
    RxEntry& e = rxBuf[rxBufTail];
    f.printf("%s,%lu,ADV,%d,%s,%s\r\n",
             PROGRAM_ID, (unsigned long)e.ms, (int)e.rssi, e.addr, e.mfd);
    rxBufTail = (rxBufTail + 1) % RX_BUF_SIZE;
  }
}

static void startTrial() {
  char path[64];
  makeNextPath(path, sizeof(path));
  f = SD.open(path, FILE_WRITE);
  if (!f) {
    Serial.printf("[SD] open FAIL path=%s\n", path);
    return;
  }
  f.println("prog_id,ms,event,rssi,addr,mfd");
  trialIndex++;
  f.printf("# meta, firmware=%s, program_id=%s, trial_index=%lu, adv_interval_ms=%u, buf_size=%u\r\n",
           FW_TAG, PROGRAM_ID, (unsigned long)trialIndex,
           (unsigned)ADV_INTERVAL_MS, (unsigned)RX_BUF_SIZE);
  t0Ms = millis();
  trial = true;
  Serial.printf("[AGENT] RX startTrial nowMs=%lu t0Ms=%lu sync=%d alt=%d\n",
                (unsigned long)millis(), (unsigned long)t0Ms,
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN));

  txLockAddr[0] = '\0';
  rxCount = 0;
  cbTotal = 0;
  cbMfdParseFail = 0;
  cbAddrMismatch = 0;
  cbBufDrop = 0;
  cbFirstMfd[0] = '\0';
  cbFirstAddr[0] = '\0';
  rxBufHead = 0;
  rxBufTail = 0;
  bufOverflow = 0;
  lastFlushMs = millis();
  Serial.printf("[RX] start %s (trial=%lu)\n", path, (unsigned long)trialIndex);
}

static void endTrialWithReason(const char* reason) {
  if (!trial) return;
  trial = false;
  Serial.printf("[AGENT] RX endTrial reason=%s nowMs=%lu t0Ms=%lu dt=%lu sync=%d alt=%d\n",
                reason,
                (unsigned long)millis(), (unsigned long)t0Ms,
                (unsigned long)(millis() - t0Ms),
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN));
  flushBuffer();
  if (f) {
    f.flush();
    f.close();
  }
  uint32_t t_ms = millis() - t0Ms;
  double dur_s = t_ms / 1000.0;
  double rate_hz = (dur_s > 0.0) ? ((double)rxCount / dur_s) : 0.0;
  double expected = (double)t_ms / (double)ADV_INTERVAL_MS;
  double pdr = (expected > 0.0) ? ((double)rxCount / expected) : 0.0;
  Serial.printf("[RX] summary trial=%lu ms_total=%lu, rx=%lu, rate_hz=%.2f, est_pdr=%.3f, buf_overflow=%lu\n",
                (unsigned long)trialIndex, (unsigned long)t_ms, (unsigned long)rxCount,
                rate_hz, pdr, (unsigned long)bufOverflow);
  Serial.printf("[AGENT] RX diag trial=%lu cbTotal=%lu mfdFail=%lu addrMis=%lu bufDrop=%lu firstAddr=%s firstMfd=%s\n",
                (unsigned long)trialIndex,
                (unsigned long)cbTotal,
                (unsigned long)cbMfdParseFail,
                (unsigned long)cbAddrMismatch,
                (unsigned long)cbBufDrop,
                cbFirstAddr[0] ? cbFirstAddr : "-",
                cbFirstMfd[0] ? cbFirstMfd : "-");
  Serial.println("[RX] end");
}

#if USE_NIMBLE
NimBLEScan* gScan=nullptr;
class CB: public NimBLEAdvertisedDeviceCallbacks{
  void onResult(NimBLEAdvertisedDevice* d) override {
    if (!trial) return;
    cbTotal++;

    std::string mfd = d->getManufacturerData(); // may be binary
    if (cbFirstMfd[0] == '\0' && mfd.size() > 0) {
      char hex[32];
      bytesToHex((const uint8_t*)mfd.data(), (mfd.size() > 8 ? 8 : mfd.size()), hex, sizeof(hex));
      strncpy(cbFirstMfd, hex, sizeof(cbFirstMfd) - 1);
      cbFirstMfd[sizeof(cbFirstMfd) - 1] = '\0';
    }
    char mfd6[7];
    uint16_t seq;
    if (!parseMfdAsciiMFxxxx((const uint8_t*)mfd.data(), mfd.size(), mfd6, seq)) {
      cbMfdParseFail++;
      return;
    }

    std::string addrStd = d->getAddress().toString();
    if (cbFirstAddr[0] == '\0') {
      strncpy(cbFirstAddr, addrStd.c_str(), sizeof(cbFirstAddr) - 1);
      cbFirstAddr[sizeof(cbFirstAddr) - 1] = '\0';
    }
    if (txLockAddr[0] == '\0') {
      strncpy(txLockAddr, addrStd.c_str(), sizeof(txLockAddr) - 1);
      txLockAddr[sizeof(txLockAddr) - 1] = '\0';
    }
    if (strncmp(txLockAddr, addrStd.c_str(), sizeof(txLockAddr)) != 0) {
      cbAddrMismatch++;
      return;
    }

    uint16_t nextHead = (rxBufHead + 1) % RX_BUF_SIZE;
    if (nextHead == rxBufTail) {
      bufOverflow++;
      cbBufDrop++;
      return;
    }
    RxEntry& e = rxBuf[rxBufHead];
    e.ms = millis() - t0Ms;
    e.rssi = (int8_t)d->getRSSI();
    strncpy(e.addr, addrStd.c_str(), sizeof(e.addr) - 1);
    e.addr[sizeof(e.addr) - 1] = '\0';
    strncpy(e.mfd, mfd6, sizeof(e.mfd) - 1);
    e.mfd[sizeof(e.mfd) - 1] = '\0';
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
    cbTotal++;
    String mfdStr = d.getManufacturerData();
    const uint8_t* mfdData = (const uint8_t*)mfdStr.c_str();
    const size_t mfdLen = (size_t)mfdStr.length();
    if (cbFirstMfd[0] == '\0' && mfdLen > 0) {
      char hex[32];
      bytesToHex(mfdData, (mfdLen > 8 ? 8 : mfdLen), hex, sizeof(hex));
      strncpy(cbFirstMfd, hex, sizeof(cbFirstMfd) - 1);
      cbFirstMfd[sizeof(cbFirstMfd) - 1] = '\0';
    }
    char mfd6[7];
    uint16_t seq;
    if (!parseMfdAsciiMFxxxx(mfdData, mfdLen, mfd6, seq)) {
      cbMfdParseFail++;
      return;
    }

    String addr = d.getAddress().toString();
    if (cbFirstAddr[0] == '\0') {
      strncpy(cbFirstAddr, addr.c_str(), sizeof(cbFirstAddr) - 1);
      cbFirstAddr[sizeof(cbFirstAddr) - 1] = '\0';
    }
    if (txLockAddr[0] == '\0') {
      strncpy(txLockAddr, addr.c_str(), sizeof(txLockAddr) - 1);
      txLockAddr[sizeof(txLockAddr) - 1] = '\0';
    }
    if (strncmp(txLockAddr, addr.c_str(), sizeof(txLockAddr)) != 0) {
      cbAddrMismatch++;
      return;
    }

    uint16_t nextHead = (rxBufHead + 1) % RX_BUF_SIZE;
    if (nextHead == rxBufTail) {
      bufOverflow++;
      cbBufDrop++;
      return;
    }
    RxEntry& e = rxBuf[rxBufHead];
    e.ms = millis() - t0Ms;
    e.rssi = (int8_t)d.getRSSI();
    strncpy(e.addr, addr.c_str(), sizeof(e.addr) - 1);
    e.addr[sizeof(e.addr) - 1] = '\0';
    strncpy(e.mfd, mfd6, sizeof(e.mfd) - 1);
    e.mfd[sizeof(e.mfd) - 1] = '\0';
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

  // SYNC (polling + dual input)
  pinMode(SYNC_IN, INPUT_PULLDOWN);
  pinMode(SYNC_ALT_IN, INPUT_PULLDOWN);

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
  uint32_t nowMs = millis();
  int syncIn = digitalRead(SYNC_IN);
  int syncAlt = digitalRead(SYNC_ALT_IN);
  int syncAnyHigh = (syncIn == HIGH) || (syncAlt == HIGH);
  int syncAllLow = (syncIn == LOW) && (syncAlt == LOW);

  // Edge logs (quiet by default)
  static int lastSyncIn = -1;
  static int lastSyncAlt = -1;
#if DBG_LEVEL >= 1
  if (syncIn != lastSyncIn) {
    Serial.printf("[DBG] SYNC_PIN=%d level=%d nowMs=%lu\n", SYNC_IN, syncIn, (unsigned long)nowMs);
    lastSyncIn = syncIn;
  }
  if (syncAlt != lastSyncAlt) {
    Serial.printf("[DBG] SYNC_PIN=%d level=%d nowMs=%lu\n", SYNC_ALT_IN, syncAlt, (unsigned long)nowMs);
    lastSyncAlt = syncAlt;
  }
#else
  lastSyncIn = syncIn;
  lastSyncAlt = syncAlt;
#endif
#if DBG_LEVEL >= 3
  static uint32_t lastDbg = 0;
  static int lastRptSyncIn = -1;
  static int lastRptSyncAlt = -1;
  static int lastRptTrial = -1;
  bool changed = (syncIn != lastRptSyncIn) || (syncAlt != lastRptSyncAlt) || ((trial ? 1 : 0) != lastRptTrial);
  if (changed || (nowMs - lastDbg >= 10000)) {
    Serial.printf("[DBG] SYNC_IN=%d SYNC_ALT=%d trial=%d cbTotal=%lu rx=%lu\n",
                  syncIn, syncAlt, trial ? 1 : 0,
                  (unsigned long)cbTotal, (unsigned long)rxCount);
    lastDbg = nowMs;
    lastRptSyncIn = syncIn;
    lastRptSyncAlt = syncAlt;
    lastRptTrial = (trial ? 1 : 0);
  }
#endif

  // Debounce start/stop
  static uint32_t highSince = 0;
  static uint32_t lowSince = 0;
  static const uint32_t START_DEBOUNCE_MS = 100;
  static const uint32_t END_DEBOUNCE_MS = 100;

  if (!trial) {
    if (syncAnyHigh) {
      if (highSince == 0) highSince = nowMs;
      if (nowMs - highSince >= START_DEBOUNCE_MS) {
#if DBG_LEVEL >= 2
        Serial.printf("[AGENT] RX start condition met (HIGH stable) nowMs=%lu highSince=%lu\n",
                      (unsigned long)nowMs, (unsigned long)highSince);
#endif
        startTrial();
        highSince = 0;
        lowSince = 0;
        return;
      }
    } else {
      highSince = 0;
    }
  } else {
    if (USE_SYNC_END) {
      if (syncAllLow) {
        if (lowSince == 0) lowSince = nowMs;
        if (nowMs - lowSince >= END_DEBOUNCE_MS) {
          endTrialWithReason("SYNC_LOW_STABLE");
          lowSince = 0;
        }
      } else {
        lowSince = 0;
      }
    }
    if (trial && (nowMs - t0Ms) >= TRIAL_MS_FALLBACK) {
      endTrialWithReason("TRIAL_TIMEOUT");
    }
    if (trial && (nowMs - lastFlushMs) >= FLUSH_INTERVAL_MS) {
      flushBuffer();
      lastFlushMs = nowMs;
    }
  }
  vTaskDelay(1);
}
