// RX_DeltaE_V3.ino
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
// Role: Passive scan and log MFD to SD. Start/stop via SYNC.

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
static const uint32_t TRIAL_MS = 70000;
static const bool USE_SYNC_END = true;
static const char PROGRAM_ID[] = "RX_DELTAE_V3_SYNC_PROBE_20260115";

#ifndef SCAN_MS
  #define SCAN_MS 50
#endif

static const uint16_t RX_BUF_SIZE = 512;
static const uint32_t FLUSH_INTERVAL_MS = 500;
static const char FW_BUILD[] = "RX_DeltaE_V3_syncdebounce_2026-01-15_v2";
// Debug verbosity: 0=min, 1=edges+agent, 2=more agent detail, 3=periodic verbose
#ifndef DBG_LEVEL
#define DBG_LEVEL 1
#endif

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

volatile bool syncLvl = false;
File f;
static const char FW_TAG[] = "RX_DeltaE_V3";
static uint32_t trialIndex = 0;

static inline int nib(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}
static bool parseMFD(const String& s, uint16_t& seq) {
  if (s.length() < 6) return false;
  if (!(s[0] == 'M' && s[1] == 'F')) return false;
  int n0 = nib(s[2]), n1 = nib(s[3]), n2 = nib(s[4]), n3 = nib(s[5]);
  if (n0 < 0 || n1 < 0 || n2 < 0 || n3 < 0) return false;
  seq = (uint16_t)((n0 << 12) | (n1 << 8) | (n2 << 4) | n3);
  return true;
}

char txLockAddr[18] = "";
uint32_t t0Ms = 0;
bool trial = false;
uint32_t rxCount = 0;

void IRAM_ATTR onSync() {
  bool s = digitalRead(SYNC_IN);
  if (s != syncLvl) {
    syncLvl = s;
  }
}

static void makeNextPath(char* out, size_t out_sz) {
  SD.mkdir("/logs");
  // Avoid O(N) SD.exists() scan from 1; generate a unique-ish filename immediately.
  uint32_t ms = millis();
  uint32_t r = (uint32_t)esp_random();
  snprintf(out, out_sz, "/logs/rx_%08lu_%08lx.csv", (unsigned long)ms, (unsigned long)r);
}

void flushBuffer() {
  if (!f) return;
  uint16_t head = rxBufHead;
  while (rxBufTail != head) {
    RxEntry& e = rxBuf[rxBufTail];
    f.printf("%s,%lu,ADV,%d,%s,%s\r\n",
             PROGRAM_ID, (unsigned long)e.ms, (int)e.rssi, e.addr, e.mfd);
    rxBufTail = (rxBufTail + 1) % RX_BUF_SIZE;
  }
}

void startTrial() {
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
           FW_TAG, PROGRAM_ID, (unsigned long)trialIndex, (unsigned)ADV_INTERVAL_MS, (unsigned)RX_BUF_SIZE);
  t0Ms = millis();
  trial = true;
  // #region agent log
  Serial.printf("[AGENT] RX startTrial nowMs=%lu t0Ms=%lu sync=%d alt=%d\n",
                (unsigned long)millis(), (unsigned long)t0Ms,
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN));
  // #endregion
  txLockAddr[0] = '\0';
  rxCount = 0;
  rxBufHead = 0;
  rxBufTail = 0;
  bufOverflow = 0;
  lastFlushMs = millis();
  Serial.printf("[RX] start %s (trial=%lu)\n", path, (unsigned long)trialIndex);
}

static void endTrialWithReason(const char* reason) {
  if (!trial) return;
  trial = false;
  // #region agent log
  Serial.printf("[AGENT] RX endTrial reason=%s nowMs=%lu t0Ms=%lu dt=%lu sync=%d alt=%d\n",
                reason,
                (unsigned long)millis(), (unsigned long)t0Ms,
                (unsigned long)(millis() - t0Ms),
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN));
  // #endregion
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
  Serial.println("[RX] end");
}

#if USE_NIMBLE
NimBLEScan* gScan = nullptr;
class CB : public NimBLEAdvertisedDeviceCallbacks {
  void onResult(NimBLEAdvertisedDevice* d) override {
    if (!trial) return;
    std::string mfdStd = d->getManufacturerData();
    if (mfdStd.length() < 6) return;
    if (mfdStd[0] != 'M' || mfdStd[1] != 'F') return;
    std::string addrStd = d->getAddress().toString();
    if (txLockAddr[0] == '\0') {
      strncpy(txLockAddr, addrStd.c_str(), sizeof(txLockAddr) - 1);
      txLockAddr[sizeof(txLockAddr) - 1] = '\0';
    }
    if (strncmp(txLockAddr, addrStd.c_str(), sizeof(txLockAddr)) != 0) return;
    uint16_t nextHead = (rxBufHead + 1) % RX_BUF_SIZE;
    if (nextHead == rxBufTail) {
      bufOverflow++;
      return;
    }
    RxEntry& e = rxBuf[rxBufHead];
    e.ms = millis() - t0Ms;
    e.rssi = (int8_t)d->getRSSI();
    strncpy(e.addr, addrStd.c_str(), sizeof(e.addr) - 1);
    e.addr[sizeof(e.addr) - 1] = '\0';
    strncpy(e.mfd, mfdStd.c_str(), sizeof(e.mfd) - 1);
    e.mfd[sizeof(e.mfd) - 1] = '\0';
    rxBufHead = nextHead;
    rxCount++;
  }
};
CB cb;
#else
BLEScan* gScan = nullptr;
class CB : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice d) override {
    if (!trial) return;
    String mfd = d.getManufacturerData().c_str();
    uint16_t seq;
    if (!parseMFD(mfd, seq)) return;
    String addr = d.getAddress().toString();
    if (txLockAddr[0] == '\0') {
      strncpy(txLockAddr, addr.c_str(), sizeof(txLockAddr) - 1);
      txLockAddr[sizeof(txLockAddr) - 1] = '\0';
    }
    if (strncmp(txLockAddr, addr.c_str(), sizeof(txLockAddr)) != 0) return;
    uint16_t nextHead = (rxBufHead + 1) % RX_BUF_SIZE;
    if (nextHead == rxBufTail) {
      bufOverflow++;
      return;
    }
    RxEntry& e = rxBuf[rxBufHead];
    e.ms = millis() - t0Ms;
    e.rssi = (int8_t)d.getRSSI();
    strncpy(e.addr, addr.c_str(), sizeof(e.addr) - 1);
    e.addr[sizeof(e.addr) - 1] = '\0';
    strncpy(e.mfd, mfd.c_str(), sizeof(e.mfd) - 1);
    e.mfd[sizeof(e.mfd) - 1] = '\0';
    rxBufHead = nextHead;
    rxCount++;
  }
};
CB cb;
#endif

void setup() {
  Serial.begin(115200);
  Serial.printf("[FW] %s\n", FW_BUILD);
  // #region agent log
  Serial.printf("[AGENT] RX build_file=%s dbg_level=%d periodic_dbg=%d\n",
                __FILE__, (int)DBG_LEVEL, (DBG_LEVEL >= 3) ? 1 : 0);
  Serial.printf("[AGENT_PROBE] RX build_datetime=%s %s fw_build=%s\n",
                __DATE__, __TIME__, FW_BUILD);
  // #endregion
  SPI.begin(18, 19, 23, SD_CS);
  if (!SD.begin(SD_CS)) {
    Serial.println("[SD] init FAIL");
    while (1) delay(1000);
  }
  pinMode(SYNC_IN, INPUT_PULLDOWN);
  pinMode(SYNC_ALT_IN, INPUT_PULLDOWN);
  // Removed interrupt - using polling instead for stability

#if USE_NIMBLE
  NimBLEDevice::init("RX_DELTAE_V3");
  gScan = NimBLEDevice::getScan();
  gScan->setAdvertisedDeviceCallbacks(&cb);
  gScan->setActiveScan(false);
  gScan->setInterval(SCAN_MS);
  gScan->setWindow(SCAN_MS);
  gScan->start(0, nullptr, false);
#else
  BLEDevice::init("RX_DELTAE_V3");
  gScan = BLEDevice::getScan();
  gScan->setAdvertisedDeviceCallbacks(&cb);
  gScan->setActiveScan(false);
  gScan->setInterval(SCAN_MS);
  gScan->setWindow(SCAN_MS);
  gScan->start(0, nullptr, false);
#endif

  Serial.println("[RX] ready");
}

void loop() {
  uint32_t nowMs = millis();
  
  // Use polling instead of interrupt (more stable)
  int syncIn = digitalRead(SYNC_IN);
  int syncAlt = digitalRead(SYNC_ALT_IN);
  int syncAnyHigh = (syncIn == HIGH) || (syncAlt == HIGH);
  int syncAllLow = (syncIn == LOW) && (syncAlt == LOW);
  
  // Debounce for SYNC HIGH/LOW detection (avoid floating/noise triggers)
  static uint32_t syncHighSince = 0;
  static uint32_t syncLowSince = 0;
  static const uint32_t START_DEBOUNCE_MS = 100;
  static const uint32_t END_DEBOUNCE_MS = 100;
  
  // DEBUG: reduce log volume (default: only edge changes)
  static int lastSyncIn = -1;
  static int lastSyncAlt = -1;
#if DBG_LEVEL >= 1
  if (syncIn != lastSyncIn) {
    Serial.printf("[DBG] SYNC_PIN=%d level=%d nowMs=%lu\n",
                  SYNC_IN, syncIn, (unsigned long)nowMs);
    lastSyncIn = syncIn;
  }
  if (syncAlt != lastSyncAlt) {
    Serial.printf("[DBG] SYNC_PIN=%d level=%d nowMs=%lu\n",
                  SYNC_ALT_IN, syncAlt, (unsigned long)nowMs);
    lastSyncAlt = syncAlt;
  }
#else
  lastSyncIn = syncIn;
  lastSyncAlt = syncAlt;
#endif
#if DBG_LEVEL >= 3
  static uint32_t lastDebugMs = 0;
  if (nowMs - lastDebugMs >= 5000) {
    Serial.printf("[DBG] SYNC_IN=%d SYNC_ALT=%d trial=%d highSince=%lu lowSince=%lu\n",
                  syncIn, syncAlt, (int)trial, (unsigned long)syncHighSince, (unsigned long)syncLowSince);
    lastDebugMs = nowMs;
  }
#endif
  
  if (!trial) {
    if (syncAnyHigh) {
      if (syncHighSince == 0) syncHighSince = nowMs;
      if ((nowMs - syncHighSince) >= START_DEBOUNCE_MS) {
        // #region agent log
#if DBG_LEVEL >= 2
        Serial.printf("[AGENT] RX start condition met (HIGH stable) nowMs=%lu highSince=%lu\n",
                      (unsigned long)nowMs, (unsigned long)syncHighSince);
#endif
        // #endregion
        startTrial();
        syncLowSince = 0;
        syncHighSince = 0; // reset for next cycle
        return;  // Exit loop to avoid same-iteration timeout check
      }
    } else {
      syncHighSince = 0;
    }
  }
  
  if (trial && USE_SYNC_END) {
    if (syncAllLow) {
      if (syncLowSince == 0) syncLowSince = nowMs;
      if ((nowMs - syncLowSince) >= END_DEBOUNCE_MS) {
        endTrialWithReason("SYNC_LOW_STABLE");
        syncLowSince = 0;
      }
    } else {
      syncLowSince = 0;
    }
  }
  
  if (trial && (nowMs - t0Ms) >= TRIAL_MS) {
    endTrialWithReason("TRIAL_TIMEOUT");
  }
  if (trial && (nowMs - lastFlushMs) >= FLUSH_INTERVAL_MS) {
    flushBuffer();
    lastFlushMs = nowMs;
  }
  vTaskDelay(1);
}
