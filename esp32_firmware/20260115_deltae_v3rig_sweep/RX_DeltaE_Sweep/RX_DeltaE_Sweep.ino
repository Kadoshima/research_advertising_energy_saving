// RX_DeltaE_Sweep.ino
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
// Role: Passive scan and log MFD to SD. Start/stop via SYNC (dual input). Robust MFD parsing.

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include <esp_system.h> // esp_random()

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

static const char FW_TAG[] = "RX_DeltaE_Sweep";
static const char FW_BUILD[] = "RX_DeltaE_Sweep_2026-01-15";
static const char PROGRAM_ID[] = "RX_DELTAE_SWEEP_20260115";

// Pins
static const int SD_CS = 5;
static const int SYNC_IN = 26;
static const int SYNC_ALT_IN = 25;

// Trial + buffering
static const uint16_t RX_BUF_SIZE = 512;
static const uint32_t FLUSH_INTERVAL_MS = 500;
static const uint32_t TRIAL_MS_FALLBACK = 70000;

// Debounce
static const uint32_t START_DEBOUNCE_MS = 100;
static const uint32_t END_DEBOUNCE_MS = 100;

// Scan config
#ifndef SCAN_MS
  #define SCAN_MS 50
#endif

// Debug verbosity: 0=min, 1=edges+agent, 2=more agent detail, 3=periodic verbose
#ifndef DBG_LEVEL
#define DBG_LEVEL 1
#endif

struct RxEntry {
  uint32_t ms;
  int8_t rssi;
  char addr[18];
  char mfd[8]; // "MFxxxx" + '\0'
};

static RxEntry rxBuf[RX_BUF_SIZE];
static volatile uint16_t rxBufHead = 0;
static uint16_t rxBufTail = 0;
static uint32_t bufOverflow = 0;
static uint32_t lastFlushMs = 0;

static File f;
static uint32_t trialIndex = 0;
static bool trial = false;
static uint32_t t0Ms = 0;
static uint32_t rxCount = 0;
static char txLockAddr[18] = "";

// Callback diagnostics
static uint32_t cbTotal = 0;
static uint32_t cbMfdBad = 0;
static uint32_t cbAddrMismatch = 0;
static uint32_t cbBufDrop = 0;
static char firstAddr[18] = "";
static char firstMfd[16] = "";

static void makeNextPath(char* out, size_t out_sz) {
  SD.mkdir("/logs");
  uint32_t ms = millis();
  uint32_t r = (uint32_t)esp_random();
  snprintf(out, out_sz, "/logs/rx_%08lu_%08lx.csv", (unsigned long)ms, (unsigned long)r);
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

static bool parseMfdAsciiMFxxxx(const uint8_t* data, size_t len, char out6[7]) {
  if (len < 6) return false;
  if (data[0] != 'M' || data[1] != 'F') return false;
  // Copy 6 bytes and null terminate
  out6[0] = (char)data[0];
  out6[1] = (char)data[1];
  out6[2] = (char)data[2];
  out6[3] = (char)data[3];
  out6[4] = (char)data[4];
  out6[5] = (char)data[5];
  out6[6] = '\0';
  return true;
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
  char path[80];
  makeNextPath(path, sizeof(path));
  f = SD.open(path, FILE_WRITE);
  if (!f) {
    Serial.printf("[SD] open FAIL path=%s\n", path);
    return;
  }
  f.println("prog_id,ms,event,rssi,addr,mfd");
  trialIndex++;
  f.printf("# meta, firmware=%s, program_id=%s, trial_index=%lu, scan_ms=%u, buf_size=%u, build=%s %s\r\n",
           FW_TAG, PROGRAM_ID, (unsigned long)trialIndex, (unsigned)SCAN_MS, (unsigned)RX_BUF_SIZE,
           __DATE__, __TIME__);

  t0Ms = millis();
  trial = true;
  txLockAddr[0] = '\0';
  rxCount = 0;
  rxBufHead = 0;
  rxBufTail = 0;
  bufOverflow = 0;
  lastFlushMs = millis();

  cbTotal = 0;
  cbMfdBad = 0;
  cbAddrMismatch = 0;
  cbBufDrop = 0;
  firstAddr[0] = '\0';
  firstMfd[0] = '\0';

  Serial.printf("[AGENT] RX startTrial nowMs=%lu t0Ms=%lu sync=%d alt=%d\n",
                (unsigned long)millis(), (unsigned long)t0Ms,
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN));
  Serial.printf("[RX] start %s (trial=%lu)\n", path, (unsigned long)trialIndex);
}

static void endTrialWithReason(const char* reason) {
  if (!trial) return;
  trial = false;

  uint32_t nowMs = millis();
  Serial.printf("[AGENT] RX endTrial reason=%s nowMs=%lu t0Ms=%lu dt=%lu sync=%d alt=%d\n",
                reason, (unsigned long)nowMs, (unsigned long)t0Ms,
                (unsigned long)(nowMs - t0Ms),
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN));

  flushBuffer();
  if (f) {
    f.flush();
    f.close();
  }

  uint32_t t_ms = nowMs - t0Ms;
  double dur_s = t_ms / 1000.0;
  double rate_hz = (dur_s > 0.0) ? ((double)rxCount / dur_s) : 0.0;
  Serial.printf("[RX] summary trial=%lu ms_total=%lu, rx=%lu, rate_hz=%.2f, buf_overflow=%lu\n",
                (unsigned long)trialIndex, (unsigned long)t_ms, (unsigned long)rxCount,
                rate_hz, (unsigned long)bufOverflow);
  Serial.printf("[AGENT] RX diag trial=%lu cbTotal=%lu mfdBad=%lu addrMis=%lu bufDrop=%lu firstAddr=%s firstMfd=%s\n",
                (unsigned long)trialIndex,
                (unsigned long)cbTotal,
                (unsigned long)cbMfdBad,
                (unsigned long)cbAddrMismatch,
                (unsigned long)cbBufDrop,
                firstAddr[0] ? firstAddr : "-",
                firstMfd[0] ? firstMfd : "-");
  Serial.println("[RX] end");
}

#if USE_NIMBLE
NimBLEScan* gScan = nullptr;
class CB : public NimBLEAdvertisedDeviceCallbacks {
  void onResult(NimBLEAdvertisedDevice* d) override {
    if (!trial) return;
    cbTotal++;

    std::string mfd = d->getManufacturerData();
    if (firstMfd[0] == '\0' && mfd.size() > 0) {
      // store first 8 bytes as hex for visibility
      char hex[32];
      bytesToHex((const uint8_t*)mfd.data(), (mfd.size() > 8 ? 8 : mfd.size()), hex, sizeof(hex));
      strncpy(firstMfd, hex, sizeof(firstMfd) - 1);
      firstMfd[sizeof(firstMfd) - 1] = '\0';
    }

    char mfd6[7];
    if (!parseMfdAsciiMFxxxx((const uint8_t*)mfd.data(), mfd.size(), mfd6)) {
      cbMfdBad++;
      return;
    }

    std::string addrStd = d->getAddress().toString();
    if (firstAddr[0] == '\0') {
      strncpy(firstAddr, addrStd.c_str(), sizeof(firstAddr) - 1);
      firstAddr[sizeof(firstAddr) - 1] = '\0';
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
static CB cb;
#else
BLEScan* gScan = nullptr;
class CB : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice d) override {
    if (!trial) return;
    cbTotal++;

    String mfdStr = d.getManufacturerData();
    const uint8_t* mfdData = (const uint8_t*)mfdStr.c_str();
    const size_t mfdLen = (size_t)mfdStr.length();
    if (firstMfd[0] == '\0' && mfdLen > 0) {
      char hex[32];
      bytesToHex(mfdData, (mfdLen > 8 ? 8 : mfdLen), hex, sizeof(hex));
      strncpy(firstMfd, hex, sizeof(firstMfd) - 1);
      firstMfd[sizeof(firstMfd) - 1] = '\0';
    }

    char mfd6[7];
    if (!parseMfdAsciiMFxxxx(mfdData, mfdLen, mfd6)) {
      cbMfdBad++;
      return;
    }

    String addr = d.getAddress().toString();
    if (firstAddr[0] == '\0') {
      strncpy(firstAddr, addr.c_str(), sizeof(firstAddr) - 1);
      firstAddr[sizeof(firstAddr) - 1] = '\0';
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
static CB cb;
#endif

void setup() {
  Serial.begin(115200);
  Serial.printf("[FW] %s build=%s %s\n", FW_BUILD, __DATE__, __TIME__);
  Serial.printf("[FW] tag=%s program_id=%s use_nimble=%d scan_ms=%u\n",
                FW_TAG, PROGRAM_ID, (int)USE_NIMBLE, (unsigned)SCAN_MS);

  SPI.begin(18, 19, 23, SD_CS);
  if (!SD.begin(SD_CS)) {
    Serial.println("[SD] init FAIL");
    while (1) delay(1000);
  }

  pinMode(SYNC_IN, INPUT_PULLDOWN);
  pinMode(SYNC_ALT_IN, INPUT_PULLDOWN);

#if USE_NIMBLE
  NimBLEDevice::init("RX_DELTAE_SWEEP");
  gScan = NimBLEDevice::getScan();
  gScan->setAdvertisedDeviceCallbacks(&cb);
  gScan->setActiveScan(false);
  gScan->setInterval(SCAN_MS);
  gScan->setWindow(SCAN_MS);
  gScan->start(0, nullptr, false);
#else
  BLEDevice::init("RX_DELTAE_SWEEP");
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
  if (nowMs - lastDbg >= 5000) {
    Serial.printf("[DBG] sync=%d alt=%d trial=%d cbTotal=%lu rx=%lu\n",
                  syncIn, syncAlt, trial ? 1 : 0,
                  (unsigned long)cbTotal, (unsigned long)rxCount);
    lastDbg = nowMs;
  }
#endif

  // Debounce start/stop
  static uint32_t highSince = 0;
  static uint32_t lowSince = 0;

  if (!trial) {
    if (syncAnyHigh) {
      if (highSince == 0) highSince = nowMs;
      if (nowMs - highSince >= START_DEBOUNCE_MS) {
        startTrial();
        highSince = 0;
        lowSince = 0;
        return;
      }
    } else {
      highSince = 0;
    }
  } else {
    if (syncAllLow) {
      if (lowSince == 0) lowSince = nowMs;
      if (nowMs - lowSince >= END_DEBOUNCE_MS) {
        endTrialWithReason("SYNC_LOW_STABLE");
        lowSince = 0;
      }
    } else {
      lowSince = 0;
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

