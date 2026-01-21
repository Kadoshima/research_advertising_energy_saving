// RX_DeltaE_Sweep.ino
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
// Role: Passive scan and log MFD to SD. Start/stop via SYNC (dual input). Robust MFD parsing.

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include <esp_system.h> // esp_random()

#include <NimBLEDevice.h>
#define USE_NIMBLE 1

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

// Scan config (match 1210 baseline)
static const uint16_t SCAN_INTERVAL_MS = 100;
static const uint16_t SCAN_WINDOW_MS = 90; // 90% duty
static const bool ACTIVE_SCAN = false;
static const bool DUPLICATE_FILTER = false;

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
static uint32_t cbNoMfd = 0;
static uint32_t cbMfdBad = 0;
static uint32_t cbAddrMismatch = 0;
static uint32_t cbBufDrop = 0;
static char firstAddr[18] = "";
static char firstMfd[16] = "";
static char firstGoodAddr[18] = "";
static char firstGoodMfd[8] = "";
static uint32_t mfdSeen = 0;
static uint32_t mfdLenSum = 0;
static uint16_t mfdLenMin = 0;
static uint16_t mfdLenMax = 0;
static uint8_t mfdBadSampleCount = 0;
static const uint8_t MFD_BAD_SAMPLE_MAX = 5;
static char mfdBadSamples[MFD_BAD_SAMPLE_MAX][32];
static uint8_t mfdBadLens[MFD_BAD_SAMPLE_MAX];
static uint32_t mfdMfHit = 0;
static uint8_t mfHitCount = 0;
static const uint8_t MF_HIT_SAMPLE_MAX = 5;
static char mfHitAddr[MF_HIT_SAMPLE_MAX][18];
static char mfHitHex[MF_HIT_SAMPLE_MAX][32];
static uint8_t mfHitOffset[MF_HIT_SAMPLE_MAX];
static uint8_t mfHitLen[MF_HIT_SAMPLE_MAX];
static int8_t mfHitRssi[MF_HIT_SAMPLE_MAX];
static char mfHitName[MF_HIT_SAMPLE_MAX][20];
static uint32_t nameHit = 0;
static uint8_t nameHitCount = 0;
static const uint8_t NAME_HIT_SAMPLE_MAX = 5;
static char nameHitAddr[NAME_HIT_SAMPLE_MAX][18];
static char nameHitName[NAME_HIT_SAMPLE_MAX][20];
static int8_t nameHitRssi[NAME_HIT_SAMPLE_MAX];
static uint8_t nameHitMfdLen[NAME_HIT_SAMPLE_MAX];

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

static inline int nib(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}
static bool parseMfdAsciiMFxxxx(const uint8_t* data, size_t len, char out6[7]) {
  // Manufacturer data may include 2-byte Company ID prefix; only allow offsets 0 or 2.
  // (Avoid false positives from scanning arbitrary binary payloads.)
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
    return true;
  }
  return false;
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
  f.printf("# meta, firmware=%s, program_id=%s, trial_index=%lu, scan_interval_ms=%u, scan_window_ms=%u, active_scan=%u, dup_filter=%u, buf_size=%u, build=%s %s\r\n",
           FW_TAG, PROGRAM_ID, (unsigned long)trialIndex,
           (unsigned)SCAN_INTERVAL_MS, (unsigned)SCAN_WINDOW_MS,
           ACTIVE_SCAN ? 1U : 0U, DUPLICATE_FILTER ? 1U : 0U,
           (unsigned)RX_BUF_SIZE, __DATE__, __TIME__);

  t0Ms = millis();
  trial = true;
  txLockAddr[0] = '\0';
  rxCount = 0;
  rxBufHead = 0;
  rxBufTail = 0;
  bufOverflow = 0;
  lastFlushMs = millis();

  cbTotal = 0;
  cbNoMfd = 0;
  cbMfdBad = 0;
  cbAddrMismatch = 0;
  cbBufDrop = 0;
  firstAddr[0] = '\0';
  firstMfd[0] = '\0';
  firstGoodAddr[0] = '\0';
  firstGoodMfd[0] = '\0';
  mfdSeen = 0;
  mfdLenSum = 0;
  mfdLenMin = 0;
  mfdLenMax = 0;
  mfdBadSampleCount = 0;
  mfdMfHit = 0;
  mfHitCount = 0;
  nameHit = 0;
  nameHitCount = 0;

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
  Serial.printf("[AGENT] RX diag trial=%lu cbTotal=%lu noMfd=%lu mfdBad=%lu addrMis=%lu bufDrop=%lu firstAddr=%s firstMfd=%s\n",
                (unsigned long)trialIndex,
                (unsigned long)cbTotal,
                (unsigned long)cbNoMfd,
                (unsigned long)cbMfdBad,
                (unsigned long)cbAddrMismatch,
                (unsigned long)cbBufDrop,
                firstAddr[0] ? firstAddr : "-",
                firstMfd[0] ? firstMfd : "-");
  Serial.printf("[AGENT] RX diag2 trial=%lu mfdSeen=%lu mfdLenMin=%u mfdLenMax=%u mfdLenAvg=%.2f firstGoodAddr=%s firstGoodMfd=%s\n",
                (unsigned long)trialIndex,
                (unsigned long)mfdSeen,
                (unsigned)mfdLenMin,
                (unsigned)mfdLenMax,
                (mfdSeen > 0) ? ((double)mfdLenSum / (double)mfdSeen) : 0.0,
                firstGoodAddr[0] ? firstGoodAddr : "-",
                firstGoodMfd[0] ? firstGoodMfd : "-");
  for (uint8_t i = 0; i < mfdBadSampleCount; ++i) {
    Serial.printf("[AGENT] RX mfdBadSample idx=%u len=%u hex=%s\n",
                  (unsigned)i, (unsigned)mfdBadLens[i], mfdBadSamples[i]);
  }
  Serial.printf("[AGENT] RX diag3 trial=%lu mfdMfHit=%lu\n",
                (unsigned long)trialIndex, (unsigned long)mfdMfHit);
  for (uint8_t i = 0; i < mfHitCount; ++i) {
    Serial.printf("[AGENT] RX mfHit idx=%u len=%u offset=%u rssi=%d addr=%s name=%s hex=%s\n",
                  (unsigned)i, (unsigned)mfHitLen[i], (unsigned)mfHitOffset[i],
                  (int)mfHitRssi[i],
                  mfHitAddr[i][0] ? mfHitAddr[i] : "-",
                  mfHitName[i][0] ? mfHitName[i] : "-",
                  mfHitHex[i]);
  }
  Serial.printf("[AGENT] RX diag4 trial=%lu nameHit=%lu name=TX_DELTAE_SWEEP\n",
                (unsigned long)trialIndex, (unsigned long)nameHit);
  for (uint8_t i = 0; i < nameHitCount; ++i) {
    Serial.printf("[AGENT] RX nameHit idx=%u rssi=%d addr=%s name=%s mfd_len=%u\n",
                  (unsigned)i, (int)nameHitRssi[i],
                  nameHitAddr[i][0] ? nameHitAddr[i] : "-",
                  nameHitName[i][0] ? nameHitName[i] : "-",
                  (unsigned)nameHitMfdLen[i]);
  }
  Serial.println("[RX] end");
}

#if USE_NIMBLE
NimBLEScan* gScan = nullptr;
class CB : public NimBLEScanCallbacks {
  void onResult(const NimBLEAdvertisedDevice* d) override {
    if (!trial) return;
    cbTotal++;

    std::string addrStd = d->getAddress().toString();
    std::string name = d->getName();
    if (firstAddr[0] == '\0') {
      strncpy(firstAddr, addrStd.c_str(), sizeof(firstAddr) - 1);
      firstAddr[sizeof(firstAddr) - 1] = '\0';
    }
    if (!name.empty() && name == "TX_DELTAE_SWEEP") {
      nameHit++;
      if (nameHitCount < NAME_HIT_SAMPLE_MAX) {
        strncpy(nameHitAddr[nameHitCount], addrStd.c_str(), sizeof(nameHitAddr[nameHitCount]) - 1);
        nameHitAddr[nameHitCount][sizeof(nameHitAddr[nameHitCount]) - 1] = '\0';
        strncpy(nameHitName[nameHitCount], name.c_str(), sizeof(nameHitName[nameHitCount]) - 1);
        nameHitName[nameHitCount][sizeof(nameHitName[nameHitCount]) - 1] = '\0';
        nameHitRssi[nameHitCount] = (int8_t)d->getRSSI();
        nameHitMfdLen[nameHitCount] = (uint8_t)d->getManufacturerData().size();
        nameHitCount++;
      }
    }

    std::string mfd = d->getManufacturerData();
    if (mfd.size() == 0) {
      cbNoMfd++;
      return;
    }
    mfdSeen++;
    uint16_t mfdLen = (uint16_t)mfd.size();
    mfdLenSum += mfdLen;
    if (mfdLenMin == 0 || mfdLen < mfdLenMin) mfdLenMin = mfdLen;
    if (mfdLen > mfdLenMax) mfdLenMax = mfdLen;
    if (firstMfd[0] == '\0' && mfd.size() > 0) {
      // store first 8 bytes as hex for visibility
      char hex[32];
      bytesToHex((const uint8_t*)mfd.data(), (mfd.size() > 8 ? 8 : mfd.size()), hex, sizeof(hex));
      strncpy(firstMfd, hex, sizeof(firstMfd) - 1);
      firstMfd[sizeof(firstMfd) - 1] = '\0';
    }
    // Scan for ASCII "MF" anywhere in manufacturer data to detect TX payload.
    for (size_t i = 0; i + 1 < mfd.size(); ++i) {
      if (mfd[i] == 'M' && mfd[i + 1] == 'F') {
        mfdMfHit++;
        if (mfHitCount < MF_HIT_SAMPLE_MAX) {
          std::string name = d->getName();
          strncpy(mfHitAddr[mfHitCount], addrStd.c_str(), sizeof(mfHitAddr[mfHitCount]) - 1);
          mfHitAddr[mfHitCount][sizeof(mfHitAddr[mfHitCount]) - 1] = '\0';
          mfHitRssi[mfHitCount] = (int8_t)d->getRSSI();
          mfHitOffset[mfHitCount] = (uint8_t)i;
          mfHitLen[mfHitCount] = (uint8_t)mfd.size();
          bytesToHex((const uint8_t*)mfd.data(),
                     (mfd.size() > 12 ? 12 : mfd.size()),
                     mfHitHex[mfHitCount],
                     sizeof(mfHitHex[mfHitCount]));
          if (!name.empty()) {
            strncpy(mfHitName[mfHitCount], name.c_str(), sizeof(mfHitName[mfHitCount]) - 1);
            mfHitName[mfHitCount][sizeof(mfHitName[mfHitCount]) - 1] = '\0';
          } else {
            mfHitName[mfHitCount][0] = '\0';
          }
          mfHitCount++;
        }
        break;
      }
    }

    char mfd6[7];
    if (!parseMfdAsciiMFxxxx((const uint8_t*)mfd.data(), mfd.size(), mfd6)) {
      cbMfdBad++;
      if (mfdBadSampleCount < MFD_BAD_SAMPLE_MAX) {
        bytesToHex((const uint8_t*)mfd.data(),
                   (mfd.size() > 12 ? 12 : mfd.size()),
                   mfdBadSamples[mfdBadSampleCount],
                   sizeof(mfdBadSamples[mfdBadSampleCount]));
        mfdBadLens[mfdBadSampleCount] = (uint8_t)mfdLen;
        mfdBadSampleCount++;
      }
      return;
    }
    if (firstGoodMfd[0] == '\0') {
      strncpy(firstGoodMfd, mfd6, sizeof(firstGoodMfd) - 1);
      firstGoodMfd[sizeof(firstGoodMfd) - 1] = '\0';
      strncpy(firstGoodAddr, addrStd.c_str(), sizeof(firstGoodAddr) - 1);
      firstGoodAddr[sizeof(firstGoodAddr) - 1] = '\0';
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

    String addr = d.getAddress().toString();
    String name = d.getName();
    if (firstAddr[0] == '\0') {
      strncpy(firstAddr, addr.c_str(), sizeof(firstAddr) - 1);
      firstAddr[sizeof(firstAddr) - 1] = '\0';
    }
    if (name.length() > 0 && name == "TX_DELTAE_SWEEP") {
      nameHit++;
      if (nameHitCount < NAME_HIT_SAMPLE_MAX) {
        strncpy(nameHitAddr[nameHitCount], addr.c_str(), sizeof(nameHitAddr[nameHitCount]) - 1);
        nameHitAddr[nameHitCount][sizeof(nameHitAddr[nameHitCount]) - 1] = '\0';
        strncpy(nameHitName[nameHitCount], name.c_str(), sizeof(nameHitName[nameHitCount]) - 1);
        nameHitName[nameHitCount][sizeof(nameHitName[nameHitCount]) - 1] = '\0';
        nameHitRssi[nameHitCount] = (int8_t)d.getRSSI();
        nameHitMfdLen[nameHitCount] = (uint8_t)mfdStr.length();
        nameHitCount++;
      }
    }

    String mfdStr = d.getManufacturerData();
    const uint8_t* mfdData = (const uint8_t*)mfdStr.c_str();
    const size_t mfdLen = (size_t)mfdStr.length();
    if (mfdLen == 0) {
      cbNoMfd++;
      return;
    }
    mfdSeen++;
    mfdLenSum += (uint16_t)mfdLen;
    if (mfdLenMin == 0 || mfdLen < mfdLenMin) mfdLenMin = (uint16_t)mfdLen;
    if (mfdLen > mfdLenMax) mfdLenMax = (uint16_t)mfdLen;
    if (firstMfd[0] == '\0' && mfdLen > 0) {
      char hex[32];
      bytesToHex(mfdData, (mfdLen > 8 ? 8 : mfdLen), hex, sizeof(hex));
      strncpy(firstMfd, hex, sizeof(firstMfd) - 1);
      firstMfd[sizeof(firstMfd) - 1] = '\0';
    }
    for (size_t i = 0; i + 1 < mfdLen; ++i) {
      if (mfdData[i] == 'M' && mfdData[i + 1] == 'F') {
        mfdMfHit++;
        if (mfHitCount < MF_HIT_SAMPLE_MAX) {
          String name = d.getName();
          strncpy(mfHitAddr[mfHitCount], addr.c_str(), sizeof(mfHitAddr[mfHitCount]) - 1);
          mfHitAddr[mfHitCount][sizeof(mfHitAddr[mfHitCount]) - 1] = '\0';
          mfHitRssi[mfHitCount] = (int8_t)d.getRSSI();
          mfHitOffset[mfHitCount] = (uint8_t)i;
          mfHitLen[mfHitCount] = (uint8_t)mfdLen;
          bytesToHex(mfdData,
                     (mfdLen > 12 ? 12 : mfdLen),
                     mfHitHex[mfHitCount],
                     sizeof(mfHitHex[mfHitCount]));
          if (name.length() > 0) {
            strncpy(mfHitName[mfHitCount], name.c_str(), sizeof(mfHitName[mfHitCount]) - 1);
            mfHitName[mfHitCount][sizeof(mfHitName[mfHitCount]) - 1] = '\0';
          } else {
            mfHitName[mfHitCount][0] = '\0';
          }
          mfHitCount++;
        }
        break;
      }
    }

    char mfd6[7];
    if (!parseMfdAsciiMFxxxx(mfdData, mfdLen, mfd6)) {
      cbMfdBad++;
      if (mfdBadSampleCount < MFD_BAD_SAMPLE_MAX) {
        bytesToHex(mfdData,
                   (mfdLen > 12 ? 12 : mfdLen),
                   mfdBadSamples[mfdBadSampleCount],
                   sizeof(mfdBadSamples[mfdBadSampleCount]));
        mfdBadLens[mfdBadSampleCount] = (uint8_t)mfdLen;
        mfdBadSampleCount++;
      }
      return;
    }
    if (firstGoodMfd[0] == '\0') {
      strncpy(firstGoodMfd, mfd6, sizeof(firstGoodMfd) - 1);
      firstGoodMfd[sizeof(firstGoodMfd) - 1] = '\0';
      strncpy(firstGoodAddr, addr.c_str(), sizeof(firstGoodAddr) - 1);
      firstGoodAddr[sizeof(firstGoodAddr) - 1] = '\0';
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
  Serial.printf("[FW] tag=%s program_id=%s use_nimble=%d scan_interval_ms=%u scan_window_ms=%u active_scan=%u dup_filter=%u\n",
                FW_TAG, PROGRAM_ID, (int)USE_NIMBLE,
                (unsigned)SCAN_INTERVAL_MS, (unsigned)SCAN_WINDOW_MS,
                ACTIVE_SCAN ? 1U : 0U, DUPLICATE_FILTER ? 1U : 0U);

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
  gScan->setScanCallbacks(&cb, true);
  gScan->setActiveScan(ACTIVE_SCAN);
  gScan->setInterval(SCAN_INTERVAL_MS);
  gScan->setWindow(SCAN_WINDOW_MS);
  gScan->setDuplicateFilter(DUPLICATE_FILTER);
  gScan->start(0, false);
#else
  BLEDevice::init("RX_DELTAE_SWEEP");
  gScan = BLEDevice::getScan();
  gScan->setAdvertisedDeviceCallbacks(&cb, true);
  gScan->setActiveScan(ACTIVE_SCAN);
  gScan->setInterval(SCAN_INTERVAL_MS);
  gScan->setWindow(SCAN_WINDOW_MS);
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
  static int lastRptSyncIn = -1;
  static int lastRptSyncAlt = -1;
  static int lastRptTrial = -1;
  bool changed = (syncIn != lastRptSyncIn) || (syncAlt != lastRptSyncAlt) || ((trial ? 1 : 0) != lastRptTrial);
  if (changed || (nowMs - lastDbg >= 10000)) {
    Serial.printf("[DBG] sync=%d alt=%d trial=%d cbTotal=%lu rx=%lu\n",
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

