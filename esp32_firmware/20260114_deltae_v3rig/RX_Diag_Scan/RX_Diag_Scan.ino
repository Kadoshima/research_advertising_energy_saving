// RX_Diag_Scan.ino
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
// Role: BLE scan diagnostic (print basic fields to Serial).

#include <Arduino.h>

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

static const char PROGRAM_ID[] = "RX_DIAG_SCAN_20260119";
static const char TARGET_NAME[] = "TX_DELTAE_V3";
static const uint32_t RUN_MS = 30000;
static const uint16_t SCAN_INTERVAL = 80;
static const uint16_t SCAN_WINDOW = 80;
static const bool ACTIVE_SCAN = true;
static const uint32_t PRINT_MAX = 200;

static uint32_t cbTotal = 0;
static uint32_t cbNameHit = 0;
static uint32_t cbMfdHit = 0;
static uint32_t printCount = 0;
static uint32_t startedMs = 0;
static bool summaryPrinted = false;

static inline int nib(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}

static bool parseMfdAsciiMFxxxx(const uint8_t* data, size_t len) {
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
    return true;
  }
  return false;
}

static void bytesToHex(const uint8_t* p, size_t n, char* out, size_t out_sz) {
  static const char* H = "0123456789ABCDEF";
  size_t j = 0;
  for (size_t i = 0; i < n && (j + 2) < out_sz; i++) {
    out[j++] = H[(p[i] >> 4) & 0xF];
    out[j++] = H[p[i] & 0xF];
  }
  out[j] = '\0';
}

#if USE_NIMBLE
NimBLEScan* gScan = nullptr;
class CB : public NimBLEAdvertisedDeviceCallbacks {
  void onResult(NimBLEAdvertisedDevice* d) override {
    cbTotal++;
    std::string name = d->getName();
    std::string mfd = d->getManufacturerData();
    bool nameHit = (!name.empty() && name.find(TARGET_NAME) != std::string::npos);
    bool mfdHit = (mfd.size() > 0 && parseMfdAsciiMFxxxx((const uint8_t*)mfd.data(), mfd.size()));
    if (nameHit) cbNameHit++;
    if (mfdHit) cbMfdHit++;
    if (printCount >= PRINT_MAX) return;
    char hex[32] = "";
    if (mfd.size() > 0) {
      bytesToHex((const uint8_t*)mfd.data(), (mfd.size() > 12 ? 12 : mfd.size()), hex, sizeof(hex));
    }
    Serial.printf("[SCAN] addr=%s rssi=%d name=%s mfd=%s hit_name=%d hit_mfd=%d\n",
                  d->getAddress().toString().c_str(),
                  (int)d->getRSSI(),
                  name.empty() ? "-" : name.c_str(),
                  (mfd.size() > 0) ? hex : "-",
                  nameHit ? 1 : 0,
                  mfdHit ? 1 : 0);
    printCount++;
  }
};
CB cb;
#else
BLEScan* gScan = nullptr;
class CB : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice d) override {
    cbTotal++;
    String name = d.getName();
    String mfdStr = d.getManufacturerData();
    const uint8_t* mfdData = (const uint8_t*)mfdStr.c_str();
    const size_t mfdLen = (size_t)mfdStr.length();
    bool nameHit = (name.length() > 0 && name.indexOf(TARGET_NAME) >= 0);
    bool mfdHit = (mfdLen > 0 && parseMfdAsciiMFxxxx(mfdData, mfdLen));
    if (nameHit) cbNameHit++;
    if (mfdHit) cbMfdHit++;
    if (printCount >= PRINT_MAX) return;
    char hex[32] = "";
    if (mfdLen > 0) {
      bytesToHex(mfdData, (mfdLen > 12 ? 12 : mfdLen), hex, sizeof(hex));
    }
    Serial.printf("[SCAN] addr=%s rssi=%d name=%s mfd=%s hit_name=%d hit_mfd=%d\n",
                  d.getAddress().toString().c_str(),
                  (int)d.getRSSI(),
                  (name.length() > 0) ? name.c_str() : "-",
                  (mfdLen > 0) ? hex : "-",
                  nameHit ? 1 : 0,
                  mfdHit ? 1 : 0);
    printCount++;
  }
};
CB cb;
#endif

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.printf("[FW] RX_Diag_Scan program_id=%s\n", PROGRAM_ID);
#if USE_NIMBLE
  NimBLEDevice::init("RX_DIAG_SCAN");
  gScan = NimBLEDevice::getScan();
  gScan->setAdvertisedDeviceCallbacks(&cb);
  gScan->setActiveScan(ACTIVE_SCAN);
  gScan->setInterval(SCAN_INTERVAL);
  gScan->setWindow(SCAN_WINDOW);
  gScan->setDuplicateFilter(false);
  gScan->start(0, nullptr, false);
#else
  BLEDevice::init("RX_DIAG_SCAN");
  gScan = BLEDevice::getScan();
  gScan->setAdvertisedDeviceCallbacks(&cb, true);
  gScan->setActiveScan(ACTIVE_SCAN);
  gScan->setInterval(SCAN_INTERVAL);
  gScan->setWindow(SCAN_WINDOW);
  gScan->start(0, nullptr, false);
#endif
  startedMs = millis();
  Serial.println("[SCAN] start");
}

void loop() {
  uint32_t nowMs = millis();
  if (!summaryPrinted && (nowMs - startedMs) >= RUN_MS) {
    summaryPrinted = true;
    Serial.printf("[SCAN] summary run_ms=%lu total=%lu name_hit=%lu mfd_hit=%lu printed=%lu\n",
                  (unsigned long)(nowMs - startedMs),
                  (unsigned long)cbTotal,
                  (unsigned long)cbNameHit,
                  (unsigned long)cbMfdHit,
                  (unsigned long)printCount);
  }
  vTaskDelay(10);
}
