// === TXSD_PowerLogger_SYNC_TICK_OFF.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// 機能：TX(②)からの UART 受信(v,i,p)を SD に保存。SYNCで試行開始/終了。
//       広告OFFのベースライン計測用：サマリの adv_count は 0 とし、
//       E/adv は 0 を出力（ΔE = E_on − E_off の算出目的）。
//
// 配線：UART RX=34 ← ② TX=4（クロス）
//      SYNC_IN=26 ← ② SYNC_OUT=25
//      SD: CS=5, SCK=18, MISO=19, MOSI=23
//
// 出力：/logs/trial_XXX_off.csv
//   ms,voltage,current,power
//   # summary, ms_total=..., adv_count=0, E_total_mJ=..., E_per_adv_uJ=0.0

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
// esp_random()
#include <esp_system.h>

HardwareSerial uart1(1);

// ===== パススルー設定（受信→SD を最短経路へ） =====
#define PASS_THRU_ONLY 1         // 数値パース/積分を止め、受信行をそのままSDへ
#define RXBUF_SIZE   16384       // UART受信バッファ拡張
#define SD_CHUNK      8192       // まとめ書きの塊サイズ（バイト）
static uint8_t sdBuf[SD_CHUNK];  // SDチャンクバッファ
static size_t  sdLen = 0;        // バッファ内有効バイト数

static const int RX_PIN  = 34;
static const int SD_CS   = 5;
static const int SYNC_IN = 26;
static const int SYNC_ALT_IN = 25;

static const uint32_t TRIAL_MS_FALLBACK = 60000;   // 60s (fallback)
static const uint32_t MIN_TRIAL_MS = 1000;
static const uint32_t START_DEBOUNCE_MS = 100;
// Note: This logger historically uses fixed window end (TRIAL_MS_FALLBACK).
// We keep SYNC low handling disabled to remain compatible with "short SYNC pulse" start schemes.
static const uint32_t END_DEBOUNCE_MS = 100;
static const char PROGRAM_ID[] = "TXSD_PWRLOGGER_SYNC_TICK_OFF_20260116";
// Debug verbosity: 0=min, 1=edges+agent, 2=more agent detail, 3=periodic verbose
#ifndef DBG_LEVEL
#define DBG_LEVEL 1
#endif

File f;

static bool logging=false;
static uint32_t t0_ms=0, tPrev=0, lineN=0;
static double   E_mJ=0.0;
static String   lineBuf;

static uint32_t syncHighSince = 0;
static uint32_t syncLowSince = 0;

static const char FW_TAG[] = "TXSD_PowerLogger_SYNC_TICK_OFF";
// Diagnostics accumulators
double sumV=0.0, sumI=0.0, sumPcalc=0.0; // mW for Pcalc
double sumDt=0.0, sumDt2=0.0;            // ms
uint32_t dtMin=0xFFFFFFFF, dtMax=0;
uint32_t badLines=0;

static void makeNextPath(char* out, size_t out_sz){
  SD.mkdir("/logs");
  uint32_t ms = millis();
  uint32_t r = (uint32_t)esp_random();
  snprintf(out, out_sz, "/logs/pwr_%08lu_%08lx_off.csv", (unsigned long)ms, (unsigned long)r);
}

void startTrial(){
  char path[80];
  makeNextPath(path, sizeof(path));
  f = SD.open(path, FILE_WRITE);
  if (!f) { Serial.println("[SD] open FAIL"); return; }
  f.println("prog_id,ms,raw_payload");
  f.printf("# meta, firmware=%s, program_id=%s\r\n", FW_TAG, PROGRAM_ID);
  logging = true;
  t0_ms = millis(); tPrev = t0_ms; E_mJ = 0.0; lineN = 0;
  sumV = sumI = sumPcalc = 0.0; sumDt = sumDt2 = 0.0; dtMin = 0xFFFFFFFF; dtMax = 0; badLines = 0; sdLen = 0;
  syncHighSince = 0;
  syncLowSince = 0;
  Serial.printf("[AGENT] TXSD startTrial nowMs=%lu t0_ms=%lu sync=%d alt=%d\n",
                (unsigned long)millis(), (unsigned long)t0_ms,
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN));
  Serial.printf("[PWR] start %s (mode=OFF)\n", path);
}

void endTrial(){
  if (!logging) return;
  logging = false;
  uint32_t t_ms = millis() - t0_ms;
  if (t_ms < MIN_TRIAL_MS) {
    Serial.printf("[PWR] ignore short trial ms_total=%lu\n", (unsigned long)t_ms);
    if (sdLen) { f.write(sdBuf, sdLen); sdLen = 0; }
    f.flush(); f.close();
    return;
  }
  const uint32_t N = 0; // 広告OFF: adv_countは0
  const double Eper_uJ = 0.0;
  // 未書き出しバッファをドレイン
  if (sdLen) { f.write(sdBuf, sdLen); sdLen = 0; }
  // Diagnostics（パース不要の範囲）
  double samples = (double)lineN;
  double dur_s = t_ms / 1000.0;
  double rate_hz = (dur_s>0)? (samples / dur_s) : 0.0;
  double meanDt = (samples>0)? (sumDt / samples) : 0.0;
  double varDt = (samples>0)? (sumDt2 / samples) - (meanDt*meanDt) : 0.0;
  double stdDt = (varDt>0)? sqrt(varDt) : 0.0;
  // System state
  int cpu_mhz = getCpuFrequencyMhz();
  uint32_t free_heap = ESP.getFreeHeap();
  f.printf("# summary, ms_total=%lu, adv_count=%lu, E_total_mJ=%.3f, E_per_adv_uJ=%.1f\r\n",
           (unsigned long)t_ms, (unsigned long)N, E_mJ, Eper_uJ);
  Serial.printf("# summary, ms_total=%lu, adv_count=%lu, E_total_mJ=%.3f, E_per_adv_uJ=%.1f\n",
                (unsigned long)t_ms, (unsigned long)N, E_mJ, Eper_uJ);
  f.printf("# diag, samples=%lu, rate_hz=%.2f\r\n",
           (unsigned long)lineN, rate_hz);
  Serial.printf("# diag, samples=%lu, rate_hz=%.2f\n",
                (unsigned long)lineN, rate_hz);
  f.printf("# diag, dt_ms_mean=%.3f, dt_ms_std=%.3f, dt_ms_min=%lu, dt_ms_max=%lu, parse_drop=%lu\r\n",
           meanDt, stdDt, (unsigned long)(dtMin==0xFFFFFFFF?0:dtMin), (unsigned long)dtMax, (unsigned long)badLines);
  Serial.printf("# diag, dt_ms_mean=%.3f, dt_ms_std=%.3f, dt_ms_min=%lu, dt_ms_max=%lu, parse_drop=%lu\n",
                meanDt, stdDt, (unsigned long)(dtMin==0xFFFFFFFF?0:dtMin), (unsigned long)dtMax, (unsigned long)badLines);
  f.printf("# sys, cpu_mhz=%d, free_heap=%lu\r\n",
           cpu_mhz, (unsigned long)free_heap);
  Serial.printf("# sys, cpu_mhz=%d, free_heap=%lu\n",
                cpu_mhz, (unsigned long)free_heap);
  f.flush(); f.close();
  Serial.printf("[PWR] end t=%lums N=%lu E=%.3fmJ (mode=OFF)\n",
                (unsigned long)t_ms, (unsigned long)N, E_mJ);
}

void setup(){
  Serial.begin(115200);

  // SD
  SPI.begin(18,19,23,SD_CS);
  if (!SD.begin(SD_CS)) { Serial.println("[SD] init FAIL"); while(1) delay(1000); }

  // UART
  uart1.begin(230400, SERIAL_8N1, RX_PIN, -1);
#if defined(ARDUINO_ARCH_ESP32)
  uart1.setRxBufferSize(RXBUF_SIZE);
#endif

  // SYNC
  pinMode(SYNC_IN, INPUT_PULLDOWN);
  pinMode(SYNC_ALT_IN, INPUT_PULLDOWN);
  lineBuf.reserve(256);
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

  // Debounce start/stop
  if (!logging) {
    if (syncAnyHigh) {
      if (syncHighSince == 0) syncHighSince = nowMs;
      if (nowMs - syncHighSince >= START_DEBOUNCE_MS) {
        startTrial();
        syncHighSince = 0;
        syncLowSince = 0;
        // avoid same-iteration end / timeout logic
        return;
      }
    } else {
      syncHighSince = 0;
    }
  } else {
    // fallback end
    if (logging && (nowMs - t0_ms >= TRIAL_MS_FALLBACK)) {
      endTrial();
    }
  }

  // UART受信→SD保存（パススルー）
  while (uart1.available()){
    char c = uart1.read();
    if (c == '\n'){
      if (logging && f){
        uint32_t tNow = millis();
        // dt統計のみ計測
        uint32_t dt   = tNow - tPrev; tPrev = tNow;
        sumDt += dt; sumDt2 += (double)dt * (double)dt;
        if (dt < dtMin) dtMin = dt;
        if (dt > dtMax) dtMax = dt;

#if PASS_THRU_ONLY
        // 受信行をそのままSDへ（先頭に相対時刻msを付与）
        uint32_t tRel = tNow - t0_ms;
        char tbuf[64];
        int n = snprintf(tbuf, sizeof(tbuf), "%s,%lu,", PROGRAM_ID, (unsigned long)tRel);
        if (sdLen + (size_t)n + lineBuf.length() + 2 > SD_CHUNK) { f.write(sdBuf, sdLen); sdLen = 0; }
        memcpy(sdBuf + sdLen, tbuf, (size_t)n);                 sdLen += (size_t)n;
        memcpy(sdBuf + sdLen, lineBuf.c_str(), lineBuf.length()); sdLen += lineBuf.length();
        sdBuf[sdLen++] = '\r'; sdBuf[sdLen++] = '\n';
        lineN++;
        if (sdLen >= SD_CHUNK) { f.write(sdBuf, sdLen); sdLen = 0; }
#else
        // 既存の数値パース＋積分（停止中）
#endif
      }
      lineBuf = "";
    } else if (c != '\r'){
      lineBuf += c;
    }
  }
}
