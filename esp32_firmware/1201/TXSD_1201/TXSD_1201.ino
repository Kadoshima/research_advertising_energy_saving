// TXSD_1201.ino
// Read INA219 on TXSD, log ms,mV,uA,p_mW to SD. Start/stop via TICK_IN (SYNC unused).
// Board: ESP32-DevKitC (WROVER-E assumed)

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
static const int SYNC_IN = 26;     // RX/TXSD側で受けるSYNCピン（TX GPIO25と接続）
static const int SYNC_OFF_IN = -1; // 使わない場合は -1（OFFゲート未使用）
static const int TICK_IN = 33;
static const int I2C_SDA = 21;
static const int I2C_SCL = 22;

// Settings
static const uint32_t SAMPLE_US    = 10000;   // 10ms = 100Hz
static const uint32_t FALLBACK_MS  = 900000;  // safety fallback (~15 min)
static const uint32_t MIN_TRIAL_MS = 1000;    // ignore trials shorter than 1s
static const uint32_t TICK_PER_TRIAL = 0;     // 0=disabled (use SYNC to end); fallback if >0
static const char SUBJECT_ID[] = "subject_flash"; // set per experiment

HardwareSerial Debug(0);
Adafruit_INA219 ina;
File f;

volatile uint32_t tickCountRaw=0; // cumulative TICK count
uint32_t tickStart=0;             // TICK count at trial start
uint32_t tickCount=0;             // adv count in trial
bool syncState=false;
bool syncOffState=false;
bool logging=false;
uint32_t t0_ms=0, nextSampleUs=0;
uint32_t lineN=0, badLines=0;
uint32_t lastTickSnapshot=0;
uint32_t syncLowSince=0;

// Stats
double sumP=0.0; double sumV=0.0; double sumI=0.0; uint32_t sampN=0;
uint32_t firstMs=0, lastMs=0; bool hasSample=false;

static inline String nextPath(){
  SD.mkdir("/logs");
  char p[64];
  for (uint32_t id=1;;++id){
    snprintf(p,sizeof(p),"/logs/trial_%03lu_on.csv",(unsigned long)id);
    if(!SD.exists(p)) return String(p);
  }
}
void IRAM_ATTR onTickRaw(){ tickCountRaw++; }

static void startTrial(){
  String path=nextPath();
  f=SD.open(path, FILE_WRITE);
  if (!f){ Debug.println("[SD] open FAIL"); return; }
  f.println("ms,mV,µA,p_mW");
  f.printf("# meta, firmware=TXSD_1201, trial_index=auto, adv_interval_ms=0, subject=%s\r\n", SUBJECT_ID);
  logging=true; t0_ms=millis(); nextSampleUs=micros()+SAMPLE_US; lineN=badLines=0; tickCount=0;
  tickStart = (tickCountRaw>0) ? (tickCountRaw-1) : 0; // include preceding TICK
  lastTickSnapshot=tickCountRaw;
  sumP=sumV=sumI=0.0; sampN=0; hasSample=false; firstMs=lastMs=0;
  Debug.printf("[PWR] start %s subject=%s\n", path.c_str(), SUBJECT_ID);
}

static void endTrial(){
  if (!logging) return;
  logging=false;
  uint32_t now_ms = millis();
  uint32_t ms_total = now_ms - t0_ms; // wall-clock duration

  // Ignore too-short trials
  if (ms_total < MIN_TRIAL_MS){
    Debug.printf("[PWR] ignore short trial ms_total=%lu\n", (unsigned long)ms_total);
    if (f){ f.flush(); f.close(); }
    return;
  }

  double meanP = (sampN>0)? (sumP/sampN) : 0.0;
  double meanV = (sampN>0)? (sumV/sampN) : 0.0;
  double meanI = (sampN>0)? (sumI/sampN) : 0.0;
  double E_mJ  = meanP * (ms_total/1000.0);
  double Eper_uJ = (tickCount>0)? (E_mJ*1000.0/tickCount) : 0.0;

  f.printf("# summary, ms_total=%lu, adv_count=%lu, E_total_mJ=%.3f, E_per_adv_uJ=%.1f, subject=%s\r\n",
           (unsigned long)ms_total, (unsigned long)tickCount, E_mJ, Eper_uJ, SUBJECT_ID);
  f.printf("# diag, samples=%lu, rate_hz=%.2f, mean_v=%.3f, mean_i=%.3f, mean_p_mW=%.1f, parse_drop=%lu\r\n",
           (unsigned long)sampN, (ms_total>0? (double)sampN/(ms_total/1000.0):0.0), meanV, meanI, meanP, (unsigned long)badLines);
  f.flush(); f.close();
  Debug.printf("[PWR] end ms=%lu Nadv=%lu E=%.3fmJ\n", (unsigned long)ms_total, (unsigned long)tickCount, E_mJ);
  Debug.printf("[PWR] diag samples=%lu rate=%.2f mean_v=%.3f mean_i=%.3f mean_p=%.1f parse_drop=%lu\n",
               (unsigned long)sampN, (ms_total>0? (double)sampN/(ms_total/1000.0):0.0), meanV, meanI, meanP, (unsigned long)badLines);
  Debug.printf("[PWR] tick_raw=%lu tick_start=%lu tick_count=%lu\n",
               (unsigned long)tickCountRaw, (unsigned long)tickStart, (unsigned long)tickCount);
}

void setup(){
  Debug.begin(115200);
  Debug.println("[PWR] FW=TXSD_1201");
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)){ Debug.println("[SD] init FAIL"); while(1) delay(1000); }

  pinMode(SYNC_IN, INPUT_PULLDOWN);
  if (SYNC_OFF_IN >= 0) pinMode(SYNC_OFF_IN, INPUT_PULLDOWN);
  pinMode(TICK_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(TICK_IN), onTickRaw, RISING);

  Wire.begin(I2C_SDA, I2C_SCL); Wire.setClock(400000);
  ina.begin(); ina.setCalibration_16V_400mA();

  Debug.println("[PWR] ready");
}

void loop(){
  uint32_t nowMs = millis();
  bool justStarted = false;

  // --- start/stop controlled by SYNC_IN ---
  int syncIn = digitalRead(SYNC_IN);
  int syncOff = (SYNC_OFF_IN >= 0) ? digitalRead(SYNC_OFF_IN) : HIGH; // default HIGH if not used
  if (!logging && syncIn == HIGH){
    startTrial();
    syncState = true;
    syncOffState = (syncOff == HIGH);
    Debug.printf("[PWR] trigger start by SYNC (raw=%lu)\n", (unsigned long)tickCountRaw);
    justStarted = true;
    nowMs = millis();      // refresh to avoid immediate timeout underflow
    syncLowSince = 0;
  }

  if (logging){
    if (justStarted) {
      nowMs = millis();    // ensure fresh timestamp on first loop after start
    }
    bool syncLow = (syncIn == LOW) || (syncOff == LOW);
    // end when SYNC stays LOW for >=100ms, or fallback by TICK_PER_TRIAL/timeout if enabled
    if (syncLow){
      if (syncLowSince == 0) syncLowSince = nowMs;
      if ((nowMs - syncLowSince) >= 100){
        Debug.printf("[PWR] end by SYNC/SYNC_OFF sync=%d sync_off=%d\n", syncIn, syncOff);
        endTrial();
        syncState = false;
        syncOffState = false;
        syncLowSince = 0;
      }
    } else {
      syncLowSince = 0;
      tickCount = tickCountRaw - tickStart;
      if (TICK_PER_TRIAL > 0 && tickCount >= TICK_PER_TRIAL){
        Debug.printf("[PWR] force end by TICK (count=%lu)\n", (unsigned long)tickCount);
        endTrial();
        syncState = false;
      }
      int32_t dt_ms = (int32_t)(nowMs - t0_ms);
      if (dt_ms >= 0 && (uint32_t)dt_ms >= FALLBACK_MS){
        Debug.printf("[PWR] force end by timeout (ms=%lu)\n", (unsigned long)(nowMs - t0_ms));
        endTrial();
        syncState = false;
      }
    }

    uint32_t nowUs=micros();
    while ((int32_t)(nowUs - nextSampleUs) >= 0){
      nextSampleUs += SAMPLE_US;
      float v=ina.getBusVoltage_V();
      float i=ina.getCurrent_mA();
      int32_t mv=(int32_t)lroundf(v*1000.0f);
      int32_t uA=(int32_t)lroundf(i*1000.0f);
      double p_mW=v*i;
      uint32_t relMs=millis()-t0_ms;

      if (!hasSample){ hasSample=true; firstMs=relMs; }
      lastMs=relMs;
      sumP+=p_mW; sumV+=v; sumI+=i; sampN++;

      char buf[64];
      int n=snprintf(buf,sizeof(buf),"%lu,%ld,%ld,%.1f\r\n", (unsigned long)relMs, (long)mv, (long)uA, p_mW);
      if (n>0) f.write((uint8_t*)buf, n); else badLines++;
      lineN++;
      nowUs=micros();
    }
  }

  lastTickSnapshot = tickCountRaw;
  vTaskDelay(1);
}
