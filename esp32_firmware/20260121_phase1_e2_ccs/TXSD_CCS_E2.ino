// TXSD_DeltaE_Sweep.ino
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
// Role: INA219 power logger to SD. Start/stop by SYNC. Count adv by TICK (optional but recommended).

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_INA219.h>
#include <esp_system.h> // esp_random()

static const char FW_TAG[] = "TXSD_CCS_E2";
static const char FW_BUILD[] = "TXSD_CCS_E2_2026-01-21";
static const char PROGRAM_ID[] = "TXSD_CCS_E2_20260121";

// Pins (start/end pulses)
static const int SD_CS = 5;
static const int SD_SCK = 18;
static const int SD_MISO = 19;
static const int SD_MOSI = 23;
static const int I2C_SDA = 21;
static const int I2C_SCL = 22;
static const int SYNC_IN = 26;     // START pulse
static const int SYNC_ALT_IN = 25; // END pulse
static const int TICK_IN = 33;

// Sampling
static const uint32_t SAMPLE_US = 10000;   // 10 ms
static const uint32_t MIN_TRIAL_MS = 1000; // ignore too-short
static const uint32_t FALLBACK_MS = 900000;
static const uint32_t NO_TICK_TIMEOUT_MS = 8000;
static const uint32_t NO_TICK_MIN_MS = 2000;

// Debounce
static const uint32_t START_DEBOUNCE_MS = 100;
static const uint32_t END_DEBOUNCE_MS = 100;

// Debug verbosity: 0=min, 1=edges+agent, 2=more agent detail, 3=periodic verbose
#ifndef DBG_LEVEL
#define DBG_LEVEL 1
#endif

Adafruit_INA219 ina;
File f;

volatile uint32_t tickCountRaw = 0;
static void IRAM_ATTR onTickRaw() { tickCountRaw++; }

volatile bool endSignalReceived = false;
static void IRAM_ATTR onEndSignal() { endSignalReceived = true; }

bool logging = false;
uint32_t t0_ms = 0;
uint32_t nextSampleUs = 0;
uint32_t sampN = 0;
double sumP_mW = 0.0;
double sumV_V = 0.0;
double sumI_mA = 0.0;
uint32_t badLines = 0;
uint32_t tickStart = 0;
uint32_t lastTickRaw = 0;
uint32_t lastTickMs = 0;

static void makeNextPath(char* out, size_t out_sz) {
  SD.mkdir("/logs");
  uint32_t ms = millis();
  uint32_t r = (uint32_t)esp_random();
  snprintf(out, out_sz, "/logs/pwr_%08lu_%08lx_sweep.csv", (unsigned long)ms, (unsigned long)r);
}

static void startTrial() {
  char path[80];
  makeNextPath(path, sizeof(path));
  f = SD.open(path, FILE_WRITE);
  if (!f) {
    Serial.printf("[SD] open FAIL path=%s\n", path);
    return;
  }
  f.println("prog_id,ms,mV,uA,p_mW,tick_raw");
  f.printf("# meta, firmware=%s, program_id=%s, build=%s %s\r\n",
           FW_TAG, PROGRAM_ID, __DATE__, __TIME__);

  logging = true;
  t0_ms = millis();
  nextSampleUs = micros() + SAMPLE_US;
  tickStart = (tickCountRaw > 0) ? (tickCountRaw - 1) : 0;
  lastTickRaw = tickCountRaw;
  lastTickMs = t0_ms;
  sumP_mW = 0.0;
  sumV_V = 0.0;
  sumI_mA = 0.0;
  sampN = 0;
  badLines = 0;
  endSignalReceived = false;

  Serial.printf("[AGENT] TXSD startTrial nowMs=%lu t0_ms=%lu sync=%d alt=%d tickStart=%lu\n",
                (unsigned long)millis(), (unsigned long)t0_ms,
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN),
                (unsigned long)tickStart);
  Serial.printf("[PWR] start %s\n", path);
}

static void endTrial() {
  if (!logging) return;
  logging = false;

  uint32_t now_ms = millis();
  uint32_t ms_total = now_ms - t0_ms;
  uint32_t advN = tickCountRaw - tickStart;

  Serial.printf("[AGENT] TXSD endTrial nowMs=%lu t0_ms=%lu dt=%lu sync=%d alt=%d adv=%lu\n",
                (unsigned long)now_ms, (unsigned long)t0_ms, (unsigned long)ms_total,
                digitalRead(SYNC_IN), digitalRead(SYNC_ALT_IN),
                (unsigned long)advN);

  if (ms_total < MIN_TRIAL_MS) {
    Serial.printf("[PWR] ignore short trial ms_total=%lu\n", (unsigned long)ms_total);
    if (f) {
      f.flush();
      f.close();
    }
    return;
  }

  double meanP = (sampN > 0) ? (sumP_mW / (double)sampN) : 0.0;
  double meanV = (sampN > 0) ? (sumV_V / (double)sampN) : 0.0;
  double meanI = (sampN > 0) ? (sumI_mA / (double)sampN) : 0.0;
  double E_mJ = meanP * (ms_total / 1000.0);
  double Eper_uJ = (advN > 0) ? (E_mJ * 1000.0 / advN) : 0.0;

  f.printf("# summary, ms_total=%lu, adv_count=%lu, E_total_mJ=%.3f, E_per_adv_uJ=%.1f\r\n",
           (unsigned long)ms_total, (unsigned long)advN, E_mJ, Eper_uJ);
  f.printf("# diag, samples=%lu, rate_hz=%.2f, mean_v=%.3f, mean_i_mA=%.3f, mean_p_mW=%.1f, parse_drop=%lu\r\n",
           (unsigned long)sampN,
           (ms_total > 0 ? (double)sampN / (ms_total / 1000.0) : 0.0),
           meanV, meanI, meanP, (unsigned long)badLines);
  f.flush();
  f.close();

  Serial.printf("[PWR] end ms=%lu adv=%lu E=%.3fmJ\n",
                (unsigned long)ms_total, (unsigned long)advN, E_mJ);
}

void setup() {
  Serial.begin(115200);
  Serial.printf("[FW] %s build=%s %s\n", FW_BUILD, __DATE__, __TIME__);

  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)) {
    Serial.println("[SD] init FAIL");
    while (1) delay(1000);
  }

  pinMode(SYNC_IN, INPUT_PULLDOWN);
  pinMode(SYNC_ALT_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(SYNC_ALT_IN), onEndSignal, RISING);
  pinMode(TICK_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(TICK_IN), onTickRaw, RISING);

  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);
  ina.begin();
  ina.setCalibration_16V_400mA();

  Serial.printf("[PWR] ready %s program_id=%s\n", FW_TAG, PROGRAM_ID);
}

void loop() {
  uint32_t nowMs = millis();
  int syncIn = digitalRead(SYNC_IN);
  int syncAlt = digitalRead(SYNC_ALT_IN);

  // Edge logs (quiet by default)
  static int lastSyncIn = -1;
  static int lastSyncAlt = -1;
  bool startRise = (syncIn == HIGH) && (lastSyncIn == LOW);
  bool endRise = (syncAlt == HIGH) && (lastSyncAlt == LOW);
#if DBG_LEVEL >= 1
  if (syncIn != lastSyncIn) {
    Serial.printf("[DBG] SYNC_PIN=%d level=%d nowMs=%lu\n", SYNC_IN, syncIn, (unsigned long)nowMs);
  }
  if (syncAlt != lastSyncAlt) {
    Serial.printf("[DBG] SYNC_PIN=%d level=%d nowMs=%lu\n", SYNC_ALT_IN, syncAlt, (unsigned long)nowMs);
  }
#endif
  lastSyncIn = syncIn;
  lastSyncAlt = syncAlt;
#if DBG_LEVEL >= 3
  static uint32_t lastDbg = 0;
  if (nowMs - lastDbg >= 5000) {
    Serial.printf("[DBG] sync=%d alt=%d logging=%d tick=%lu\n",
                  syncIn, syncAlt, logging ? 1 : 0, (unsigned long)tickCountRaw);
    lastDbg = nowMs;
  }
#endif

  if (!logging) {
    static uint32_t lastStartEdgeMs = 0;
    if (startRise && (nowMs - lastStartEdgeMs >= START_DEBOUNCE_MS)) {
      startTrial();
      lastStartEdgeMs = nowMs;
      return;
    }
  } else {
    static uint32_t lastEndEdgeMs = 0;
    bool endDetected = endSignalReceived || (endRise && (nowMs - lastEndEdgeMs >= END_DEBOUNCE_MS));

    if (tickCountRaw != lastTickRaw) {
      lastTickRaw = tickCountRaw;
      lastTickMs = nowMs;
    } else if ((nowMs - t0_ms) >= NO_TICK_MIN_MS &&
               (nowMs - lastTickMs) >= NO_TICK_TIMEOUT_MS) {
      Serial.printf("[AGENT] TXSD endTrial reason=NO_TICK dt=%lu lastTickMs=%lu tick=%lu\n",
                    (unsigned long)(nowMs - t0_ms),
                    (unsigned long)lastTickMs,
                    (unsigned long)tickCountRaw);
      endTrial();
      return;
    }

    if (endDetected) {
      endTrial();
      lastEndEdgeMs = nowMs;
      endSignalReceived = false;
    }
    if (logging && (nowMs - t0_ms) >= FALLBACK_MS) {
      endTrial();
    }
    if (!logging) return;

    // Sampling loop
    uint32_t nowUs = micros();
    while ((int32_t)(nowUs - nextSampleUs) >= 0) {
      if (endSignalReceived) break; 
      nextSampleUs += SAMPLE_US;
      float v = ina.getBusVoltage_V();
      float i_mA = ina.getCurrent_mA();
      int32_t mv = (int32_t)lroundf(v * 1000.0f);
      int32_t uA = (int32_t)lroundf(i_mA * 1000.0f);
      double p_mW = (double)v * (double)i_mA;
      uint32_t relMs = millis() - t0_ms;

      sumP_mW += p_mW;
      sumV_V += v;
      sumI_mA += i_mA;
      sampN++;

      char buf[128];
      int n = snprintf(buf, sizeof(buf), "%s,%lu,%ld,%ld,%.1f,%lu\r\n",
                       PROGRAM_ID, (unsigned long)relMs,
                       (long)mv, (long)uA, p_mW,
                       (unsigned long)tickCountRaw);
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

