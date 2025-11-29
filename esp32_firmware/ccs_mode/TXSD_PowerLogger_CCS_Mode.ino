// === TXSD_PowerLogger_CCS_Mode.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// Extended version of TXSD_PowerLogger_PASS_THRU_ON_v2.ino
// Supports CCS mode with interval_ms field in UART input.
//
// Input format from TX:
//   Fixed mode: "mv,uA\n"
//   CCS mode:   "mv,uA,interval_ms\n"
//
// Output CSV format:
//   "ms,mV,µA,p_mW,interval_ms"
//
// Tracks interval distribution and transitions for CCS mode analysis.

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include <WiFi.h>

HardwareSerial uart1(1);

// ---- Pin/Constants ----
static const int RX_PIN   = 34;
static const int SD_CS    = 5;
static const int SYNC_IN  = 26;
static const int TICK_IN  = 33;

#define USE_TICK_INPUT    1
#define SD_CHUNK_BYTES    16384
#define UART_RXBUF_BYTES  16384
#define LINE_MAX_BYTES    64

// ---- Variables ----
File f;
volatile bool syncLvl = false, syncEdge = false;
volatile uint32_t advCountISR = 0;

bool     logging = false;
uint32_t t0_ms = 0, tPrev = 0;
uint32_t lineN = 0, badLines = 0;

// Energy integration
double   E_mJ = 0.0;
uint32_t dtMin = 0xFFFFFFFF, dtMax = 0;
double   sumDt = 0.0, sumDt2 = 0.0;
int64_t  sum_mv = 0, sum_uA = 0;
uint32_t sampN = 0;
static   uint32_t trialIndex = 0;

// CCS mode tracking
uint32_t interval_100_count = 0;
uint32_t interval_500_count = 0;
uint32_t interval_2000_count = 0;
uint32_t intervalChangeCount = 0;
uint16_t lastInterval = 0;

// SD buffer
static uint8_t sdBuf[SD_CHUNK_BYTES];
static size_t  sdLen = 0;

// Line buffer
static char    lineBuf[LINE_MAX_BYTES];
static size_t  lbLen = 0;

static const char FW_TAG[] = "TXSD_PowerLogger_CCS_Mode_v1";

static inline void sd_flush_chunk() {
  if (sdLen) { f.write(sdBuf, sdLen); sdLen = 0; }
}
static inline void sd_puts(const char* s, size_t n) {
  if (sdLen + n > SD_CHUNK_BYTES) sd_flush_chunk();
  memcpy(sdBuf + sdLen, s, n); sdLen += n;
}

void IRAM_ATTR onSync() {
  bool s = digitalRead(SYNC_IN);
  if (s != syncLvl) { syncLvl = s; syncEdge = true; }
}
void IRAM_ATTR onTick() { if (logging && USE_TICK_INPUT) advCountISR++; }

String nextPath() {
  SD.mkdir("/logs");
  char p[64];
  for (uint32_t id = 1;; ++id) {
    snprintf(p, sizeof(p), "/logs/trial_%03lu_ccs.csv", (unsigned long)id);
    if (!SD.exists(p)) return String(p);
  }
}

void startTrial() {
  String path = nextPath();
  f = SD.open(path, FILE_WRITE);
  if (!f) { Serial.println("[SD] open FAIL"); return; }

  // Header
  f.println("ms,mV,µA,p_mW,interval_ms");
  trialIndex++;
  f.printf("# meta, firmware=%s, trial_index=%lu\r\n",
           FW_TAG, (unsigned long)trialIndex);

  logging = true;
  t0_ms = millis(); tPrev = t0_ms; lineN = badLines = 0;
  E_mJ = 0.0; sampN = 0; sum_mv = sum_uA = 0;
  sumDt = sumDt2 = 0.0; dtMin = 0xFFFFFFFF; dtMax = 0;
  advCountISR = 0;

  // Reset CCS tracking
  interval_100_count = 0;
  interval_500_count = 0;
  interval_2000_count = 0;
  intervalChangeCount = 0;
  lastInterval = 0;

  // Clear UART buffer
  while (uart1.available()) uart1.read();
  sdLen = 0; lbLen = 0;

  Serial.printf("[PWR] start %s (CCS, trial=%lu)\n", path.c_str(), (unsigned long)trialIndex);
}

void endTrial() {
  if (!logging) return;
  logging = false;

  uint32_t t_ms = millis() - t0_ms;
  uint32_t Nadv = USE_TICK_INPUT ? advCountISR : 0;
  double Eper_uJ = (Nadv > 0) ? (E_mJ * 1000.0 / Nadv) : 0.0;

  // Summary
  sd_flush_chunk();
  f.printf("# summary, ms_total=%lu, adv_count=%lu, E_total_mJ=%.3f, E_per_adv_uJ=%.1f\r\n",
           (unsigned long)t_ms, (unsigned long)Nadv, E_mJ, Eper_uJ);

  double meanDt = (sampN > 0) ? (sumDt / sampN) : 0.0;
  double varDt  = (sampN > 0) ? (sumDt2 / sampN) - meanDt * meanDt : 0.0;
  double stdDt  = (varDt > 0) ? sqrt(varDt) : 0.0;
  double rate_hz = (meanDt > 0) ? (1000.0 / meanDt) : 0.0;
  double mean_mv = (sampN > 0) ? (double)sum_mv / (double)sampN : 0.0;
  double mean_uA = (sampN > 0) ? (double)sum_uA / (double)sampN : 0.0;
  double mean_mA = mean_uA / 1000.0;
  double meanPmW = (mean_mv * mean_uA) / 1000.0;

  f.printf("# diag, samples=%lu, rate_hz=%.2f, mean_v=%.3f, mean_i=%.3f, mean_p_mW=%.1f\r\n",
           (unsigned long)sampN, rate_hz, mean_mv / 1000.0, mean_mA, meanPmW);
  f.printf("# diag, dt_ms_mean=%.3f, dt_ms_std=%.3f, dt_ms_min=%lu, dt_ms_max=%lu, parse_drop=%lu\r\n",
           meanDt, stdDt, (unsigned long)(dtMin == 0xFFFFFFFF ? 0 : dtMin), (unsigned long)dtMax, (unsigned long)badLines);

  // CCS-specific summary
  uint32_t totalIntervals = interval_100_count + interval_500_count + interval_2000_count;
  f.printf("# ccs, interval_100ms=%lu (%.1f%%), interval_500ms=%lu (%.1f%%), interval_2000ms=%lu (%.1f%%)\r\n",
           (unsigned long)interval_100_count, totalIntervals > 0 ? 100.0 * interval_100_count / totalIntervals : 0.0,
           (unsigned long)interval_500_count, totalIntervals > 0 ? 100.0 * interval_500_count / totalIntervals : 0.0,
           (unsigned long)interval_2000_count, totalIntervals > 0 ? 100.0 * interval_2000_count / totalIntervals : 0.0);
  f.printf("# ccs, interval_changes=%lu\r\n", (unsigned long)intervalChangeCount);

  f.printf("# sys, cpu_mhz=%d, wifi_mode=%s, free_heap=%lu\r\n",
           getCpuFrequencyMhz(), (WiFi.getMode() == WIFI_OFF ? "OFF" : "ON"), (unsigned long)ESP.getFreeHeap());

  f.flush(); f.close();
  Serial.printf("[PWR] end trial=%lu t=%lums N=%lu E=%.3fmJ changes=%lu\n",
                (unsigned long)trialIndex, (unsigned long)t_ms, (unsigned long)Nadv, E_mJ, (unsigned long)intervalChangeCount);
}

// Parse "mv,uA" or "mv,uA,interval_ms"
static inline bool parse_line(const char* s, int32_t& mv, int32_t& uA, uint16_t& interval_ms) {
  const char* p = s;
  long a = 0, b = 0, c = 0;
  bool hasInterval = false;

  // Parse mv
  if (!*p) return false;
  while (*p >= '0' && *p <= '9') { a = a * 10 + (*p - '0'); ++p; }
  if (*p != ',') return false; ++p;

  // Parse uA
  if (!*p) return false;
  while (*p >= '0' && *p <= '9') { b = b * 10 + (*p - '0'); ++p; }

  // Check for optional interval_ms
  if (*p == ',') {
    ++p;
    if (*p) {
      while (*p >= '0' && *p <= '9') { c = c * 10 + (*p - '0'); ++p; }
      hasInterval = true;
    }
  }

  mv = (int32_t)a;
  uA = (int32_t)b;
  interval_ms = hasInterval ? (uint16_t)c : 0;
  return true;
}

void setup() {
  Serial.begin(115200);

  // SD
  SPI.begin(18, 19, 23, SD_CS);
  if (!SD.begin(SD_CS)) { Serial.println("[SD] init FAIL"); while (1) delay(1000); }

  // UART (RX only)
  uart1.begin(230400, SERIAL_8N1, RX_PIN, -1);
  uart1.setRxBufferSize(UART_RXBUF_BYTES);

  // SYNC/TICK
  pinMode(SYNC_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(SYNC_IN), onSync, CHANGE);
  pinMode(TICK_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(TICK_IN), onTick, RISING);

  syncLvl = digitalRead(SYNC_IN);
  if (syncLvl) startTrial();

  Serial.printf("[PWR] %s ready\n", FW_TAG);
}

void loop() {
  // SYNC edge detection
  if (syncEdge) {
    noInterrupts(); bool s = syncLvl; syncEdge = false; interrupts();
    if (s && !logging) {
      startTrial();
    } else if (!s && logging) {
      endTrial();
    }
  }

  // UART receive (passthrough + aggregation)
  while (uart1.available()) {
    char c = (char)uart1.read();
    if (c == '\n') {
      if (logging && f) {
        uint32_t tNow = millis();
        uint32_t dt = tNow - tPrev; tPrev = tNow;
        if (lbLen > 0 && lbLen < LINE_MAX_BYTES) {
          lineBuf[lbLen] = '\0';  // Null terminate

          int32_t mv = 0, uA = 0;
          uint16_t interval_ms = 0;

          if (parse_line(lineBuf, mv, uA, interval_ms)) {
            // Aggregation
            sampN++;
            sum_mv += mv; sum_uA += uA;
            sumDt += dt; sumDt2 += (double)dt * (double)dt;
            if (dt < dtMin) dtMin = dt;
            if (dt > dtMax) dtMax = dt;

            // Energy integration
            double p_mW = ((double)mv * (double)uA) / 1000000.0;
            E_mJ += p_mW * (dt / 1000.0);

            // Track interval distribution
            if (interval_ms == 100) interval_100_count++;
            else if (interval_ms == 500) interval_500_count++;
            else if (interval_ms == 2000) interval_2000_count++;

            // Track interval changes
            if (lastInterval != 0 && interval_ms != lastInterval) {
              intervalChangeCount++;
            }
            lastInterval = interval_ms;

            // Write to SD: "ms,mv,uA,p_mW,interval_ms\r\n"
            char outLine[64];
            int len = snprintf(outLine, sizeof(outLine), "%lu,%ld,%ld,%.1f,%u\r\n",
                               (unsigned long)(tNow - t0_ms),
                               (long)mv, (long)uA, p_mW,
                               (unsigned)interval_ms);
            sd_puts(outLine, len);
            lineN++;
          } else {
            badLines++;
          }
        } else {
          badLines++;
        }
      }
      lbLen = 0;
    } else if (c != '\r') {
      if (lbLen < LINE_MAX_BYTES - 1) lineBuf[lbLen++] = c;
      else badLines++;
    }
  }

  // Flush SD buffer when nearly full
  if (sdLen >= (SD_CHUNK_BYTES - 128)) sd_flush_chunk();

  // Yield
  vTaskDelay(1);
}
