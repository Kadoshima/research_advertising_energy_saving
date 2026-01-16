// TXSD_DeltaE_V3_OFF.ino
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
// Role: Read INA219 on TXSD, log to SD. Start/stop by SYNC. Optional TICK counting.

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_INA219.h>
// esp_random()
#include <esp_system.h>

static const int SD_CS = 5;
static const int SD_SCK = 18;
static const int SD_MISO = 19;
static const int SD_MOSI = 23;
static const int SYNC_IN = 26;
static const int SYNC_ALT_IN = 25;
static const int TICK_IN = 33;
static const int I2C_SDA = 21;
static const int I2C_SCL = 22;

static const uint32_t SAMPLE_US = 10000;
static const uint32_t FALLBACK_MS = 900000;
static const uint32_t MIN_TRIAL_MS = 1000;
static const uint32_t ADV_INTERVAL_MS = 0;
static const bool USE_TICK_INPUT = false;
static const char FW_TAG[] = "TXSD_DeltaE_V3_OFF";
static const char FW_BUILD[] = "TXSD_DeltaE_V3_OFF_syncdebounce_2026-01-15_v2";
static const char PROGRAM_ID[] = "TXSD_DELTAE_V3_OFF_20260114";
// Debug verbosity: 0=min, 1=edges+agent, 2=more agent detail, 3=periodic verbose
#ifndef DBG_LEVEL
#define DBG_LEVEL 1
#endif

Adafruit_INA219 ina;
File f;

volatile uint32_t tickCountRaw = 0;
uint32_t tickStart = 0;
bool logging = false;
uint32_t t0_ms = 0;
uint32_t nextSampleUs = 0;
uint32_t sampN = 0;
double sumP = 0.0;
double sumV = 0.0;
double sumI = 0.0;
uint32_t badLines = 0;
uint32_t syncLowSince = 0;

void IRAM_ATTR onTickRaw() { tickCountRaw++; }

static void makeNextPath(char* out, size_t out_sz) {
  SD.mkdir("/logs");
  // Avoid O(N) SD.exists() scan from 1; generate a unique-ish filename immediately.
  uint32_t ms = millis();
  uint32_t r = (uint32_t)esp_random();
  snprintf(out, out_sz, "/logs/pwr_%08lu_%08lx_off.csv", (unsigned long)ms, (unsigned long)r);
}

static void startTrial() {
  char path[64];
  makeNextPath(path, sizeof(path));
  f = SD.open(path, FILE_WRITE);
  if (!f) {
    Serial.println("[SD] open FAIL");
    return;
  }
  f.println("prog_id,ms,mV,uA,p_mW");
  f.printf("# meta, firmware=%s, program_id=%s, trial_index=auto, adv_interval_ms=%lu\r\n",
           FW_TAG, PROGRAM_ID, (unsigned long)ADV_INTERVAL_MS);

  logging = true;
  t0_ms = millis();
  nextSampleUs = micros() + SAMPLE_US;
  tickStart = (tickCountRaw > 0) ? (tickCountRaw - 1) : 0;
  sumP = 0.0;
  sumV = 0.0;
  sumI = 0.0;
  sampN = 0;
  badLines = 0;
  syncLowSince = 0;
  // #region agent log
  Serial.printf("[AGENT] TXSD startTrial nowMs=%lu t0_ms=%lu sync=%d alt=%d\n",
                (unsigned long)millis(), (unsigned long)t0_ms,
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN));
  // #endregion
  Serial.printf("[PWR] start %s\n", path);
}

static void endTrial() {
  if (!logging) return;
  logging = false;
  // #region agent log
  Serial.printf("[AGENT] TXSD endTrial nowMs=%lu t0_ms=%lu dt=%lu sync=%d alt=%d syncLowSince=%lu\n",
                (unsigned long)millis(), (unsigned long)t0_ms,
                (unsigned long)(millis() - t0_ms),
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN),
                (unsigned long)syncLowSince);
  // #endregion

  uint32_t now_ms = millis();
  uint32_t ms_total = now_ms - t0_ms;
  if (ms_total < MIN_TRIAL_MS) {
    Serial.printf("[PWR] ignore short trial ms_total=%lu\n", (unsigned long)ms_total);
    if (f) {
      f.flush();
      f.close();
    }
    return;
  }

  double meanP = (sampN > 0) ? (sumP / (double)sampN) : 0.0;
  double meanV = (sampN > 0) ? (sumV / (double)sampN) : 0.0;
  double meanI = (sampN > 0) ? (sumI / (double)sampN) : 0.0;
  double E_mJ = meanP * (ms_total / 1000.0);
  uint32_t advN = USE_TICK_INPUT ? (tickCountRaw - tickStart) : 0;
  double Eper_uJ = (advN > 0) ? (E_mJ * 1000.0 / advN) : 0.0;

  f.printf("# summary, ms_total=%lu, adv_count=%lu, E_total_mJ=%.3f, E_per_adv_uJ=%.1f\r\n",
           (unsigned long)ms_total, (unsigned long)advN, E_mJ, Eper_uJ);
  f.printf("# diag, samples=%lu, rate_hz=%.2f, mean_v=%.3f, mean_i=%.3f, mean_p_mW=%.1f, parse_drop=%lu\r\n",
           (unsigned long)sampN,
           (ms_total > 0 ? (double)sampN / (ms_total / 1000.0) : 0.0),
           meanV, meanI, meanP, (unsigned long)badLines);
  f.flush();
  f.close();
  Serial.printf("[PWR] end ms=%lu adv=%lu E=%.3fmJ\n", (unsigned long)ms_total, (unsigned long)advN, E_mJ);
}

void setup() {
  Serial.begin(115200);
  Serial.printf("[FW] %s\n", FW_BUILD);
  // #region agent log
  Serial.printf("[AGENT] TXSD_OFF build_file=%s dbg_level=%d periodic_dbg=%d use_tick=%d\n",
                __FILE__, (int)DBG_LEVEL, (DBG_LEVEL >= 3) ? 1 : 0,
                USE_TICK_INPUT ? 1 : 0);
  Serial.printf("[AGENT_PROBE] TXSD_OFF build_datetime=%s %s fw_build=%s\n",
                __DATE__, __TIME__, FW_BUILD);
  // #endregion
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)) {
    Serial.println("[SD] init FAIL");
    while (1) delay(1000);
  }

  pinMode(SYNC_IN, INPUT_PULLDOWN);
  pinMode(SYNC_ALT_IN, INPUT_PULLDOWN);
  pinMode(TICK_IN, INPUT_PULLDOWN);
  if (USE_TICK_INPUT) {
    attachInterrupt(digitalPinToInterrupt(TICK_IN), onTickRaw, RISING);
  }

  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);
  ina.begin();
  ina.setCalibration_16V_400mA();

  Serial.printf("[PWR] ready %s\n", FW_TAG);
}

void loop() {
  uint32_t nowMs = millis();
  int syncIn = digitalRead(SYNC_IN);
  int syncAlt = digitalRead(SYNC_ALT_IN);
  int syncAnyHigh = (syncIn == HIGH) || (syncAlt == HIGH);
  int syncAllLow = (syncIn == LOW) && (syncAlt == LOW);

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
  static int lastRptLogging = -1;
  bool changed = (syncIn != lastRptSyncIn) || (syncAlt != lastRptSyncAlt) || ((logging ? 1 : 0) != lastRptLogging);
  if (changed || (nowMs - lastDebugMs >= 10000)) {
    Serial.printf("[DBG] SYNC_IN=%d SYNC_ALT=%d logging=%d syncLowSince=%lu\n",
                  syncIn, syncAlt, logging ? 1 : 0, (unsigned long)syncLowSince);
    lastDebugMs = nowMs;
    lastRptSyncIn = syncIn;
    lastRptSyncAlt = syncAlt;
    lastRptLogging = (logging ? 1 : 0);
  }
#endif

  // Start only if SYNC stays HIGH for a short time (avoid floating/noise triggers)
  static uint32_t syncHighSince = 0;
  static const uint32_t START_DEBOUNCE_MS = 100;
  if (!logging) {
    if (syncAnyHigh) {
      if (syncHighSince == 0) syncHighSince = nowMs;
      if ((nowMs - syncHighSince) >= START_DEBOUNCE_MS) {
        // #region agent log
#if DBG_LEVEL >= 2
        Serial.printf("[AGENT] TXSD start condition met (HIGH stable) nowMs=%lu highSince=%lu\n",
                      (unsigned long)nowMs, (unsigned long)syncHighSince);
#endif
        // #endregion
        startTrial();
        syncHighSince = 0;
        return;  // Exit loop to avoid same-iteration issues
      }
    } else {
      syncHighSince = 0;
    }
  }

  if (logging) {
    if (syncAllLow) {
      if (syncLowSince == 0) syncLowSince = nowMs;
      if ((nowMs - syncLowSince) >= 100) {
        // #region agent log
#if DBG_LEVEL >= 2
        Serial.printf("[AGENT] TXSD end condition met (LOW stable) nowMs=%lu lowSince=%lu\n",
                      (unsigned long)nowMs, (unsigned long)syncLowSince);
#endif
        // #endregion
        endTrial();
        syncLowSince = 0;
      }
    } else {
      syncLowSince = 0;
      if ((nowMs - t0_ms) >= FALLBACK_MS) {
        // #region agent log
#if DBG_LEVEL >= 2
        Serial.printf("[AGENT] TXSD end condition met (FALLBACK) nowMs=%lu t0_ms=%lu\n",
                      (unsigned long)nowMs, (unsigned long)t0_ms);
#endif
        // #endregion
        endTrial();
      }
    }

    uint32_t nowUs = micros();
    while ((int32_t)(nowUs - nextSampleUs) >= 0) {
      nextSampleUs += SAMPLE_US;
      float v = ina.getBusVoltage_V();
      float i = ina.getCurrent_mA();
      int32_t mv = (int32_t)lroundf(v * 1000.0f);
      int32_t uA = (int32_t)lroundf(i * 1000.0f);
      double p_mW = v * i;
      uint32_t relMs = millis() - t0_ms;

      sumP += p_mW;
      sumV += v;
      sumI += i;
      sampN++;

      char buf[96];
      int n = snprintf(buf, sizeof(buf), "%s,%lu,%ld,%ld,%.1f\r\n",
                       PROGRAM_ID, (unsigned long)relMs, (long)mv, (long)uA, p_mW);
      if (n > 0) {
        f.write((uint8_t*)buf, n);
      } else {
        badLines++;
      }
      nowUs = micros();
    }
  }

  vTaskDelay(1);
}
