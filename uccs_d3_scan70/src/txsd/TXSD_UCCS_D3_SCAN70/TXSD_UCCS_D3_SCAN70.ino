// TXSD_UCCS_D3_SCAN70.ino (uccs_d3_scan70)
// INA219 logger for Step D3 (scan70 on RX).
// Start/stop via SYNC (TX GPIO25 -> TXSD GPIO26).
// TX sends preamble pulses on TICK (TX GPIO27 -> TXSD GPIO33) to encode cond_id.
// During trial, TX additionally emits 1 tick per payload update; TXSD uses tick_count as adv_count (approx).
//
// cond_id:
//   1: S4 fixed100
//   2: S4 fixed500
//   3: S4 policy (U+CCS, 100↔500)

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_INA219.h>

// Pins
static const int SD_CS   = 5;
static const int SD_SCK  = 18;
static const int SD_MISO = 19;
static const int SD_MOSI = 23;
static const int SYNC_IN = 26;
static const int SYNC_OFF_IN = -1; // unused
static const int TICK_IN = 33;
static const int I2C_SDA = 21;
static const int I2C_SCL = 22;

// Settings
static const uint32_t SAMPLE_US    = 10000;   // 10ms = 100Hz
static const uint32_t FALLBACK_MS  = 2400000; // safety fallback
static const uint32_t MIN_TRIAL_MS = 1000;
static const uint32_t TICK_PER_TRIAL = 0;     // 0=disabled (use SYNC to end)
static const char SUBJECT_ID[] = "uccs_d3_scan70";

// Preamble window (count TICK pulses after SYNC rising edge)
static const uint32_t PREAMBLE_WINDOW_MS = 800;
static const uint8_t PREAMBLE_MAX_ID = 16;

HardwareSerial Debug(0);
Adafruit_INA219 ina;
File f;

volatile uint32_t tickCountRaw=0; // cumulative
uint32_t tickStart=0;
uint32_t tickCount=0;
bool logging=false;
bool pendingStart=false;
uint32_t t0_ms=0, nextSampleUs=0;
uint32_t badLines=0;
uint32_t syncLowSince=0;
uint32_t pendingSinceMs=0;
uint32_t tickAtSync=0;
uint8_t condId=0;

// Stats
double sumP=0.0; double sumV=0.0; double sumI=0.0; uint32_t sampN=0;

static bool condInfo(uint8_t id, const char** tag){
  switch(id){
    case 1: *tag = "s4_fixed100"; return true;
    case 2: *tag = "s4_fixed500"; return true;
    case 3: *tag = "s4_policy";   return true;
    default: break;
  }
  *tag = "unk";
  return false;
}

static inline String nextPath(uint8_t id){
  SD.mkdir("/logs");
  char p[96];
  const char* tag="unk";
  (void)condInfo(id, &tag);
  for (uint32_t trial_idx=1;;++trial_idx){
    snprintf(p,sizeof(p),"/logs/trial_%03lu_c%u_%s.csv",
             (unsigned long)trial_idx, (unsigned)id, tag);
    if(!SD.exists(p)) return String(p);
  }
}

void IRAM_ATTR onTickRaw(){ tickCountRaw++; }

static void startTrial(uint8_t id){
  condId = id;
  const char* tag="unk";
  (void)condInfo(condId, &tag);
  String path = nextPath(id);
  f = SD.open(path, FILE_WRITE);
  if (!f){ Debug.println("[SD] open FAIL"); return; }
  f.println("ms,mV,uA,p_mW");

  f.printf("# meta, firmware=TXSD_UCCS_D3_SCAN70, cond_id=%u, tag=%s, subject=%s\r\n",
           (unsigned)condId, tag, SUBJECT_ID);
  if (condId == 3){
    f.printf("# meta, policy=actions{100,500} u_mid=0.20 u_high=0.35 c_mid=0.20 c_high=0.35 hyst=0.02 ema_alpha=0.20 ccs_inverted=true preamble_guard=true\r\n");
  }
  f.flush();

  logging = true;
  t0_ms = millis();
  nextSampleUs = micros() + SAMPLE_US;
  badLines = 0;
  tickCount = 0;
  tickStart = tickCountRaw; // exclude preamble pulses
  sumP=sumV=sumI=0.0;
  sampN=0;
  Debug.printf("[PWR] start %s subject=%s\n", path.c_str(), SUBJECT_ID);
}

static void endTrial(){
  if (!logging) return;
  logging = false;
  uint32_t ms_total = millis() - t0_ms;
  tickCount = tickCountRaw - tickStart;

  if (ms_total < MIN_TRIAL_MS){
    Debug.printf("[PWR] ignore short trial ms_total=%lu\n", (unsigned long)ms_total);
    if (f){ f.flush(); f.close(); }
    return;
  }

  double meanP = (sampN>0)? (sumP/sampN) : 0.0;
  double meanV = (sampN>0)? (sumV/sampN) : 0.0;
  double meanI = (sampN>0)? (sumI/sampN) : 0.0;
  double E_mJ  = meanP * (ms_total/1000.0);

  f.printf("# summary, ms_total=%lu, adv_count=%lu, E_total_mJ=%.3f, subject=%s\r\n",
           (unsigned long)ms_total, (unsigned long)tickCount, E_mJ, SUBJECT_ID);
  f.printf("# diag, samples=%lu, rate_hz=%.2f, mean_v=%.3f, mean_i=%.3f, mean_p_mW=%.1f, parse_drop=%lu\r\n",
           (unsigned long)sampN,
           (ms_total>0? (double)sampN/(ms_total/1000.0):0.0),
           meanV, meanI, meanP, (unsigned long)badLines);
  f.flush(); f.close();

  Debug.printf("[PWR] end ms=%lu adv_count=%lu E=%.3fmJ\n",
               (unsigned long)ms_total, (unsigned long)tickCount, E_mJ);
  Debug.printf("[PWR] diag samples=%lu rate=%.2f mean_v=%.3f mean_i=%.3f mean_p=%.1f parse_drop=%lu\n",
               (unsigned long)sampN,
               (ms_total>0? (double)sampN/(ms_total/1000.0):0.0),
               meanV, meanI, meanP, (unsigned long)badLines);
}

void setup(){
  Debug.begin(115200);
  Debug.println("[PWR] FW=TXSD_UCCS_D3_SCAN70");
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)){ Debug.println("[SD] init FAIL"); while(1) delay(1000); }

  pinMode(SYNC_IN, INPUT_PULLDOWN);
  if (SYNC_OFF_IN >= 0) pinMode(SYNC_OFF_IN, INPUT_PULLDOWN);
  pinMode(TICK_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(TICK_IN), onTickRaw, RISING);

  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);
  ina.begin();
  ina.setCalibration_16V_400mA();

  Debug.println("[PWR] ready");
}

void loop(){
  uint32_t nowMs = millis();
  int syncIn = digitalRead(SYNC_IN);
  int syncOff = (SYNC_OFF_IN >= 0) ? digitalRead(SYNC_OFF_IN) : HIGH;

  if (!logging && !pendingStart && syncIn == HIGH){
    pendingStart = true;
    pendingSinceMs = nowMs;
    tickAtSync = tickCountRaw;
    syncLowSince = 0;
    Debug.printf("[PWR] SYNC high, wait preamble %lums (tick_raw=%lu)\n",
                 (unsigned long)PREAMBLE_WINDOW_MS, (unsigned long)tickCountRaw);
  }

  if (pendingStart){
    if (syncIn == LOW){
      pendingStart = false;
      Debug.println("[PWR] pending start canceled (SYNC LOW)");
    } else if ((nowMs - pendingSinceMs) >= PREAMBLE_WINDOW_MS){
      uint32_t pulses = tickCountRaw - tickAtSync;
      uint8_t id = (pulses >= 1 && pulses <= PREAMBLE_MAX_ID) ? (uint8_t)pulses : 0;
      startTrial(id);
      pendingStart = false;
      syncLowSince = 0;
      Debug.printf("[PWR] trigger start by preamble pulses=%lu -> cond_id=%u\n",
                   (unsigned long)pulses, (unsigned)id);
      nowMs = millis();
    }
  }

  if (logging){
    bool syncLow = (syncIn == LOW) || (syncOff == LOW);
    if (syncLow){
      if (syncLowSince == 0) syncLowSince = nowMs;
      if ((nowMs - syncLowSince) >= 100){
        Debug.printf("[PWR] end by SYNC/SYNC_OFF sync=%d sync_off=%d\n", syncIn, syncOff);
        endTrial();
        syncLowSince = 0;
      }
    } else {
      syncLowSince = 0;
      tickCount = tickCountRaw - tickStart;
      if (TICK_PER_TRIAL > 0 && tickCount >= TICK_PER_TRIAL){
        Debug.printf("[PWR] force end by TICK (count=%lu)\n", (unsigned long)tickCount);
        endTrial();
      }
      if ((nowMs - t0_ms) >= FALLBACK_MS){
        Debug.printf("[PWR] force end by timeout (ms=%lu)\n", (unsigned long)(nowMs - t0_ms));
        endTrial();
      }
    }

    uint32_t nowUs = micros();
    while ((int32_t)(nowUs - nextSampleUs) >= 0){
      nextSampleUs += SAMPLE_US;
      float v = ina.getBusVoltage_V();
      float i = ina.getCurrent_mA();
      int32_t mv = (int32_t)lroundf(v*1000.0f);
      int32_t uA = (int32_t)lroundf(i*1000.0f);
      double p_mW = v*i;
      uint32_t relMs = millis() - t0_ms;

      sumP += p_mW;
      sumV += v;
      sumI += i;
      sampN++;

      char buf[64];
      int n = snprintf(buf, sizeof(buf), "%lu,%ld,%ld,%.1f\r\n",
                       (unsigned long)relMs, (long)mv, (long)uA, p_mW);
      if (n > 0) f.write((uint8_t*)buf, n); else badLines++;
      nowUs = micros();
    }
  } else {
    delay(10);
  }
}

