// RX_UCCS_D3_SCAN70.ino (uccs_d3_scan70)
// Receive TX_UCCS_D3 packets (MFD "<step_idx>_<tag>") and log to SD.
// - SYNC gate: TX GPIO25 -> RX GPIO26.
// - NimBLE passive scan with scan70% (interval=100ms, window=70ms).

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include <NimBLEDevice.h>
#include <math.h>

static const int SD_CS   = 5;
static const int SD_SCK  = 18;
static const int SD_MISO = 19;
static const int SD_MOSI = 23;
static const int SYNC_IN = 26; // TX GPIO25 -> RX GPIO26

// scan70
static const float SCAN_INTERVAL_MS = 100.0f;
static const float SCAN_WINDOW_MS   = 70.0f;

static const uint32_t SESSION_TIMEOUT_MS = 1200000;
static const uint32_t SYNC_LOW_DEBOUNCE_MS = 100;
static const uint32_t START_LEVEL_HOLD_MS = 200;

static inline uint16_t ms_to_0p625(float ms){ return (uint16_t)lroundf(ms / 0.625f); }

static const uint16_t RX_BUF_SIZE = 512;
static const uint32_t FLUSH_INTERVAL_MS = 500;

struct RxEntry {
  uint32_t ms;
  int8_t   rssi;
  uint16_t seq;
  char     label[16];
  char     addr[18];
  char     mfd[40];
};

static RxEntry rxBuf[RX_BUF_SIZE];
static volatile uint16_t rxHead = 0;
static uint16_t rxTail = 0;
static uint32_t bufOverflow = 0;
static uint32_t lastFlushMs = 0;

static bool trial = false;
static uint32_t t0Ms = 0;
static uint32_t rxCount = 0;
static uint32_t syncLowSince = 0;
static uint32_t syncHighSince = 0;

static File f;
static const char FW_TAG[] = "RX_UCCS_D3_SCAN70";
static bool condSeen = false;
static bool condWritten = false;
static char condLabel[16] = {0};

static bool parseMFD(const std::string& s, uint16_t& seq, std::string& label) {
  size_t usPos = s.find('_');
  if (usPos == std::string::npos || usPos < 1) return false;
  std::string seqStr = s.substr(0, usPos);
  label = s.substr(usPos + 1);
  if (label.empty()) return false;
  char* endp = nullptr;
  unsigned long v = strtoul(seqStr.c_str(), &endp, 10);
  if (endp == seqStr.c_str() || v > 65535UL) return false;
  seq = static_cast<uint16_t>(v);
  return true;
}

static String nextPath() {
  SD.mkdir("/logs");
  char p[64];
  for (uint32_t id = 1;; ++id) {
    snprintf(p, sizeof(p), "/logs/rx_trial_%03lu.csv", (unsigned long)id);
    if (!SD.exists(p)) return String(p);
  }
}

static void flushBuffer() {
  if (!f) return;
  if (!condWritten && condSeen) {
    f.printf("# condition_label=%s\r\n", condLabel);
    condWritten = true;
  }
  uint16_t head = rxHead;
  bool wrote = false;
  while (rxTail != head) {
    RxEntry& e = rxBuf[rxTail];
    f.printf("%lu,ADV,%d,%u,%s,%s,%s\r\n",
             (unsigned long)e.ms,
             (int)e.rssi,
             (unsigned)e.seq,
             e.label,
             e.addr,
             e.mfd);
    rxTail = (rxTail + 1) % RX_BUF_SIZE;
    wrote = true;
  }
  if (wrote) f.flush();
}

static void startSession() {
  String path = nextPath();
  f = SD.open(path, FILE_WRITE);
  if (f) {
    f.println("ms,event,rssi,seq,label,addr,mfd");
    f.printf("# meta, firmware=%s, buf_size=%u\r\n", FW_TAG, (unsigned)RX_BUF_SIZE);
    f.printf("# meta, scan_interval_ms=%.1f, scan_window_ms=%.1f\r\n", SCAN_INTERVAL_MS, SCAN_WINDOW_MS);
    f.flush();
  }
  t0Ms = millis();
  rxCount = 0;
  rxHead = rxTail = 0;
  bufOverflow = 0;
  lastFlushMs = t0Ms;
  condSeen = false;
  condWritten = false;
  condLabel[0] = '\0';
  Serial.printf("[RX] start %s\n", path.c_str());
  trial = true;
}

static void endSession() {
  if (!trial) return;
  flushBuffer();
  if (f) { f.flush(); f.close(); }
  uint32_t t_ms = millis() - t0Ms;
  double dur_s = t_ms / 1000.0;
  double rate_hz = dur_s > 0 ? (double)rxCount / dur_s : 0.0;
  Serial.printf("[RX] end ms_total=%lu rx=%lu buf_overflow=%lu rate_hz=%.2f\n",
                (unsigned long)t_ms,
                (unsigned long)rxCount,
                (unsigned long)bufOverflow,
                rate_hz);
  trial = false;
}

class AdvCB : public NimBLEScanCallbacks {
  void onResult(const NimBLEAdvertisedDevice* d) override {
    if (!trial) return;
    const std::string& mfd = d->getManufacturerData();
    uint16_t seq;
    std::string label;
    if (!parseMFD(mfd, seq, label)) return;
    if (!condSeen) {
      strncpy(condLabel, label.c_str(), sizeof(condLabel) - 1);
      condLabel[sizeof(condLabel) - 1] = '\0';
      condSeen = true;
    }
    const std::string addr = d->getAddress().toString();

    uint16_t nextH = (rxHead + 1) % RX_BUF_SIZE;
    if (nextH == rxTail) { bufOverflow++; return; }

    RxEntry& e = rxBuf[rxHead];
    e.ms = millis() - t0Ms;
    e.rssi = (int8_t)d->getRSSI();
    e.seq = seq;
    strncpy(e.label, label.c_str(), sizeof(e.label) - 1);
    e.label[sizeof(e.label) - 1] = '\0';
    strncpy(e.addr, addr.c_str(), sizeof(e.addr) - 1);
    e.addr[sizeof(e.addr) - 1] = '\0';
    strncpy(e.mfd, mfd.c_str(), sizeof(e.mfd) - 1);
    e.mfd[sizeof(e.mfd) - 1] = '\0';

    rxHead = nextH;
    rxCount++;
  }
};

static NimBLEScan* scan = nullptr;
static AdvCB cb;

void setup() {
  Serial.begin(115200);
  Serial.printf("[RX] FW=%s\n", FW_TAG);

  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)) {
    Serial.println("[RX] SD init FAIL");
    while (1) delay(1000);
  }

  pinMode(SYNC_IN, INPUT_PULLDOWN);

  NimBLEDevice::init("");
  scan = NimBLEDevice::getScan();
  // NimBLE-Arduino API compatibility:
  // Prefer setScanCallbacks (available on older/newer). If your NimBLE build only has
  // setAdvertisedDeviceCallbacks, replace this line with:
  //   scan->setAdvertisedDeviceCallbacks(&cb);
  scan->setScanCallbacks(&cb, false);
  scan->setActiveScan(false);
  scan->setInterval(ms_to_0p625(SCAN_INTERVAL_MS));
  scan->setWindow(ms_to_0p625(SCAN_WINDOW_MS));
  scan->setMaxResults(0);
  // start(duration_s, isContinue, restart)
  scan->start(0, false, false);

  Serial.printf("[RX] ready (buf=%u, flush=%lums, wait SYNC pin=%d)\n",
                (unsigned)RX_BUF_SIZE, (unsigned long)FLUSH_INTERVAL_MS, SYNC_IN);
}

void loop() {
  uint32_t nowMs = millis();
  int syncIn = digitalRead(SYNC_IN);

  if (!trial) {
    if (syncIn == HIGH) {
      if (syncHighSince == 0) syncHighSince = nowMs;
      if ((nowMs - syncHighSince) >= START_LEVEL_HOLD_MS) {
        startSession();
        syncHighSince = 0;
        syncLowSince = 0;
      }
    } else {
      syncHighSince = 0;
    }
    vTaskDelay(pdMS_TO_TICKS(10));
    return;
  }

  if ((nowMs - lastFlushMs) >= FLUSH_INTERVAL_MS) {
    flushBuffer();
    lastFlushMs = nowMs;
  }

  if (syncIn == LOW) {
    if (syncLowSince == 0) syncLowSince = nowMs;
    if ((nowMs - syncLowSince) >= SYNC_LOW_DEBOUNCE_MS) {
      endSession();
      syncLowSince = 0;
    }
  } else {
    syncLowSince = 0;
  }

  if ((nowMs - t0Ms) >= SESSION_TIMEOUT_MS) {
    endSession();
  }

  vTaskDelay(pdMS_TO_TICKS(10));
}
