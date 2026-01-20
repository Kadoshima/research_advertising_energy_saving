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
File f;
static const char FW_TAG[] = "RX_DeltaE_V3";
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
  // Note: Manufacturer data may start with 2-byte Company ID, so "MFxxxx" may be at offset 2.
  // Only allow offsets 0 or 2 to avoid false positives scanning arbitrary binary payloads.
  if (!data || len < 6) return false;
  for (size_t k = 0; k < 2; k++) {
    const size_t i = (k == 0) ? 0 : 2;
    if ((i + 6) > len) continue;
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

char txLockAddr[18] = "";
uint32_t t0Ms = 0;
bool trial = false;
uint32_t rxCount = 0;
// #region agent log
// RX callback diagnostics (to distinguish "no packets seen" vs "filtered out")
static uint32_t cbTotal = 0;
static uint32_t cbTotalAll = 0;
static uint32_t cbNoMfd = 0;
static uint32_t cbMfdParseFail = 0;
static uint32_t cbAddrMismatch = 0;
static uint32_t cbBufDrop = 0;
static char cbFirstMfd[32] = "";
static char cbFirstAddr[18] = "";
static uint32_t cbNameHit = 0;
static char cbFirstNameAddr[18] = "";
static char cbFirstNameMfd[32] = "";
static bool sdOk = false;
// #endregion

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
  char path[64] = "NO_SD";
  if (sdOk) {
    makeNextPath(path, sizeof(path));
    f = SD.open(path, FILE_WRITE);
    if (!f) {
      Serial.printf("[SD] open FAIL path=%s\n", path);
    } else {
      f.println("prog_id,ms,event,rssi,addr,mfd");
      f.printf("# meta, firmware=%s, program_id=%s, trial_index=%lu, adv_interval_ms=%u, buf_size=%u\r\n",
               FW_TAG, PROGRAM_ID, (unsigned long)trialIndex + 1, (unsigned)ADV_INTERVAL_MS, (unsigned)RX_BUF_SIZE);
    }
  } else {
    f = File();
  }
  trialIndex++;
  t0Ms = millis();
  trial = true;
  // #region agent log
  Serial.printf("[AGENT] RX startTrial nowMs=%lu t0Ms=%lu sync=%d alt=%d\n",
                (unsigned long)millis(), (unsigned long)t0Ms,
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN));
  // #endregion
  txLockAddr[0] = '\0';
  rxCount = 0;
  cbTotal = 0;
  cbTotalAll = 0;
  cbNoMfd = 0;
  cbMfdParseFail = 0;
  cbAddrMismatch = 0;
  cbBufDrop = 0;
  cbFirstMfd[0] = '\0';
  cbFirstAddr[0] = '\0';
  cbNameHit = 0;
  cbFirstNameAddr[0] = '\0';
  cbFirstNameMfd[0] = '\0';
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
  // #region agent log
  Serial.printf("[AGENT] RX diag trial=%lu cbTotal=%lu noMfd=%lu mfdFail=%lu addrMis=%lu bufDrop=%lu nameHit=%lu firstAddr=%s firstMfd=%s nameAddr=%s nameMfd=%s\n",
                (unsigned long)trialIndex,
                (unsigned long)cbTotal,
                (unsigned long)cbNoMfd,
                (unsigned long)cbMfdParseFail,
                (unsigned long)cbAddrMismatch,
                (unsigned long)cbBufDrop,
                (unsigned long)cbNameHit,
                cbFirstAddr[0] ? cbFirstAddr : "-",
                cbFirstMfd[0] ? cbFirstMfd : "-",
                cbFirstNameAddr[0] ? cbFirstNameAddr : "-",
                cbFirstNameMfd[0] ? cbFirstNameMfd : "-");
  // #endregion
  Serial.println("[RX] end");
}

#if USE_NIMBLE
NimBLEScan* gScan = nullptr;
class CB : public NimBLEAdvertisedDeviceCallbacks {
  void onResult(NimBLEAdvertisedDevice* d) override {
    cbTotalAll++;
    if (!trial) return;
    cbTotal++;

    std::string addrStd = d->getAddress().toString();
    if (cbFirstAddr[0] == '\0') {
      strncpy(cbFirstAddr, addrStd.c_str(), sizeof(cbFirstAddr) - 1);
      cbFirstAddr[sizeof(cbFirstAddr) - 1] = '\0';
    }

    std::string name = d->getName();
    if (!name.empty() && name.find("TX_DELTAE_V3") != std::string::npos) {
      cbNameHit++;
      if (cbFirstNameAddr[0] == '\0') {
        strncpy(cbFirstNameAddr, addrStd.c_str(), sizeof(cbFirstNameAddr) - 1);
        cbFirstNameAddr[sizeof(cbFirstNameAddr) - 1] = '\0';
      }
    }

    std::string mfd = d->getManufacturerData(); // may be binary
    if (mfd.size() == 0) {
      cbNoMfd++;
      return;
    }
    if (cbFirstNameMfd[0] == '\0' && !name.empty() && name.find("TX_DELTAE_V3") != std::string::npos) {
      char hex[32];
      bytesToHex((const uint8_t*)mfd.data(), (mfd.size() > 8 ? 8 : mfd.size()), hex, sizeof(hex));
      strncpy(cbFirstNameMfd, hex, sizeof(cbFirstNameMfd) - 1);
      cbFirstNameMfd[sizeof(cbFirstNameMfd) - 1] = '\0';
    }
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
BLEScan* gScan = nullptr;
class CB : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice d) override {
    cbTotalAll++;
    if (!trial) return;
    cbTotal++;

    String addr = d.getAddress().toString();
    if (cbFirstAddr[0] == '\0') {
      strncpy(cbFirstAddr, addr.c_str(), sizeof(cbFirstAddr) - 1);
      cbFirstAddr[sizeof(cbFirstAddr) - 1] = '\0';
    }

    String name = d.getName();
    if (name.length() > 0 && name.indexOf("TX_DELTAE_V3") >= 0) {
      cbNameHit++;
      if (cbFirstNameAddr[0] == '\0') {
        strncpy(cbFirstNameAddr, addr.c_str(), sizeof(cbFirstNameAddr) - 1);
        cbFirstNameAddr[sizeof(cbFirstNameAddr) - 1] = '\0';
      }
    }

    String mfdStr = d.getManufacturerData();
    const uint8_t* mfdData = (const uint8_t*)mfdStr.c_str();
    const size_t mfdLen = (size_t)mfdStr.length();
    if (mfdLen == 0) {
      cbNoMfd++;
      return;
    }
    if (cbFirstNameMfd[0] == '\0' && name.length() > 0 && name.indexOf("TX_DELTAE_V3") >= 0) {
      char hex[32];
      bytesToHex(mfdData, (mfdLen > 8 ? 8 : mfdLen), hex, sizeof(hex));
      strncpy(cbFirstNameMfd, hex, sizeof(cbFirstNameMfd) - 1);
      cbFirstNameMfd[sizeof(cbFirstNameMfd) - 1] = '\0';
    }
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
  sdOk = SD.begin(SD_CS);
  if (!sdOk) {
    Serial.println("[SD] init FAIL (continue without SD)");
  }
  pinMode(SYNC_IN, INPUT_PULLDOWN);
  pinMode(SYNC_ALT_IN, INPUT_PULLDOWN);
  // Removed interrupt - using polling instead for stability

#if USE_NIMBLE
  NimBLEDevice::init("RX_DELTAE_V3");
  gScan = NimBLEDevice::getScan();
  gScan->setAdvertisedDeviceCallbacks(&cb);
  gScan->setActiveScan(true);
  gScan->setInterval(SCAN_MS);
  gScan->setWindow(SCAN_MS);
  gScan->setDuplicateFilter(false);
  gScan->start(0, nullptr, false);
#else
  BLEDevice::init("RX_DELTAE_V3");
  gScan = BLEDevice::getScan();
  gScan->setAdvertisedDeviceCallbacks(&cb, true);
  gScan->setActiveScan(true);
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
  static int lastRptSyncIn = -1;
  static int lastRptSyncAlt = -1;
  static int lastRptTrial = -1;
  bool changed = (syncIn != lastRptSyncIn) || (syncAlt != lastRptSyncAlt) || ((int)trial != lastRptTrial);
  if (changed || (nowMs - lastDebugMs >= 10000)) {
    Serial.printf("[DBG] SYNC_IN=%d SYNC_ALT=%d trial=%d highSince=%lu lowSince=%lu cbTotal=%lu cbAll=%lu nameHit=%lu noMfd=%lu mfdFail=%lu addrMis=%lu bufDrop=%lu firstAddr=%s firstMfd=%s nameAddr=%s nameMfd=%s\n",
                  syncIn, syncAlt, (int)trial,
                  (unsigned long)syncHighSince, (unsigned long)syncLowSince,
                  (unsigned long)cbTotal, (unsigned long)cbTotalAll,
                  (unsigned long)cbNameHit,
                  (unsigned long)cbNoMfd,
                  (unsigned long)cbMfdParseFail, (unsigned long)cbAddrMismatch,
                  (unsigned long)cbBufDrop, cbFirstAddr, cbFirstMfd,
                  cbFirstNameAddr[0] ? cbFirstNameAddr : "-",
                  cbFirstNameMfd[0] ? cbFirstNameMfd : "-");
    lastDebugMs = nowMs;
    lastRptSyncIn = syncIn;
    lastRptSyncAlt = syncAlt;
    lastRptTrial = (int)trial;
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
