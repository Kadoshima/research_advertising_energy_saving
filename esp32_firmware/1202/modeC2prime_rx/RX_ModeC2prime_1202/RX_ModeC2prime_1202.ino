// === RX_ModeC2prime_1202.ino ===
// 目的: Mode C2' の TX (makeMFD("%04u_%s")) を受信し、seq と label をSDへ記録する。
// - SYNCは使用せず、セッション全体を1ファイルで収集。
// - NimBLE（ESP32ボード付属）前提。ArduinoBLEは使わない。

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include <NimBLEDevice.h>

// ピン設定
static const int SD_CS   = 5;
static const int SD_SCK  = 18;
static const int SD_MISO = 19;
static const int SD_MOSI = 23;
static const uint16_t SCAN_MS = 50;

// リングバッファ
static const uint16_t RX_BUF_SIZE = 512;
static const uint32_t FLUSH_INTERVAL_MS = 500;

struct RxEntry {
  uint32_t ms;
  int8_t   rssi;
  uint16_t seq;
  char     label[12];
  char     addr[18];
  char     mfd[20];
};

static RxEntry rxBuf[RX_BUF_SIZE];
static volatile uint16_t rxHead = 0;
static uint16_t rxTail = 0;
static uint32_t bufOverflow = 0;
static uint32_t lastFlushMs = 0;

// セッション状態
static bool trial = true;
static uint32_t t0Ms = 0;
static uint32_t rxCount = 0;
static File f;
static const char FW_TAG[] = "RX_MODEC2P_1202";

// MFD parser: "0001_label"
static bool parseMFD(const std::string& s, uint16_t& seq, std::string& label) {
  // 例: "0001_2" / "0123_walk"
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
  uint16_t head = rxHead;
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
  }
}

static void startSession() {
  String path = nextPath();
  f = SD.open(path, FILE_WRITE);
  if (f) {
    f.println("ms,event,rssi,seq,label,addr,mfd");
    f.printf("# meta, firmware=%s, buf_size=%u\r\n", FW_TAG, (unsigned)RX_BUF_SIZE);
    f.flush();
  }
  t0Ms = millis();
  rxCount = 0;
  rxHead = rxTail = 0;
  bufOverflow = 0;
  lastFlushMs = t0Ms;
  Serial.printf("[RX] start %s\n", path.c_str());
}

static void endSession() {
  if (!trial) return;
  flushBuffer();
  if (f) { f.flush(); f.close(); }
  uint32_t t_ms = millis() - t0Ms;
  double dur_s = t_ms / 1000.0;
  double rate_hz = dur_s > 0 ? (double)rxCount / dur_s : 0.0;
  Serial.printf("[RX] summary ms_total=%lu, rx=%lu, rate_hz=%.2f, buf_overflow=%lu\n",
                (unsigned long)t_ms,
                (unsigned long)rxCount,
                rate_hz,
                (unsigned long)bufOverflow);
  Serial.println("[RX] end");
  trial = false;
}

class ScanCB : public NimBLEScanCallbacks {
  void onResult(NimBLEAdvertisedDevice* d) {
    const std::string& mfd = d->getManufacturerData();
    uint16_t seq;
    std::string label;
    if (!parseMFD(mfd, seq, label)) return;
    const std::string addr = d->getAddress().toString();

    uint16_t nextH = (rxHead + 1) % RX_BUF_SIZE;
    if (nextH == rxTail) { bufOverflow++; return; }
    RxEntry& e = rxBuf[rxHead];
    e.ms = millis() - t0Ms;
    e.rssi = (int8_t)d->getRSSI();
    e.seq = seq;
    strncpy(e.label, label.c_str(), sizeof(e.label) - 1); e.label[sizeof(e.label) - 1] = '\0';
    strncpy(e.addr, addr.c_str(), sizeof(e.addr) - 1); e.addr[sizeof(e.addr) - 1] = '\0';
    strncpy(e.mfd, mfd.c_str(), sizeof(e.mfd) - 1);   e.mfd[sizeof(e.mfd) - 1] = '\0';
    rxHead = nextH; rxCount++;
  }
};

void setup() {
  Serial.begin(115200);
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)) { Serial.println("[SD] init FAIL"); while (1) delay(1000); }

  NimBLEDevice::init("RX_ESP32");
  NimBLEScan* scan = NimBLEDevice::getScan();
  scan->setActiveScan(false);
  scan->setInterval(SCAN_MS);
  scan->setWindow(SCAN_MS);
  scan->setScanCallbacks(new ScanCB());
  scan->start(0, false);

  startSession();
  Serial.printf("[RX] ready (buf=%u, flush=%lums)\n", (unsigned)RX_BUF_SIZE, (unsigned long)FLUSH_INTERVAL_MS);
}

void loop() {
  uint32_t now = millis();
  if (now - lastFlushMs >= FLUSH_INTERVAL_MS) {
    flushBuffer();
    lastFlushMs = now;
  }
  vTaskDelay(1);
}
