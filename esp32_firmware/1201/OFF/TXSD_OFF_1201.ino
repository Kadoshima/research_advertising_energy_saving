// === TXSD_OFF_1201.ino ===
// INA219をTXSD側で直読みし、TICKでtrialを区切るOFF計測用ロガー。
// TX側は被測定体（BLE OFF/sleep前提）。SYNCは使わず、TICKのみで300adv終了。
// 板: ESP32-DevKitC (WROVER-E想定)

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_INA219.h>

// ピン設定
static const int SD_CS   = 5;
static const int SD_SCK  = 18;
static const int SD_MISO = 19;
static const int SD_MOSI = 23;
static const int TICK_IN = 33;
static const int I2C_SDA = 21;
static const int I2C_SCL = 22;

// 設定
static const uint32_t SAMPLE_US      = 10000;   // 10ms = 100Hz
static const uint32_t MIN_TRIAL_MS   = 1000;    // 1秒未満のtrialは無視
static const uint32_t TICK_PER_TRIAL = 300;     // 1トライアルのadv数（TICKで終了）
static const uint32_t FALLBACK_MS    = 660000;  // 念のためのフォールバック（11分）

HardwareSerial Debug(0);
Adafruit_INA219 ina;
File f;

volatile uint32_t tickCountRaw=0;
uint32_t tickStart=0;
uint32_t tickCount=0;
bool logging=false;
uint32_t t0_ms=0, nextSampleUs=0;
uint32_t lineN=0, badLines=0;
uint32_t lastTickSnapshot=0;

// 統計
double sumP=0.0, sumV=0.0, sumI=0.0; uint32_t sampN=0;
bool   hasSample=false; uint32_t firstMs=0, lastMs=0;

static inline String nextPath(){
  SD.mkdir("/logs");
  char p[64];
  for (uint32_t id=1;;++id){ snprintf(p,sizeof(p),"/logs/trial_%03lu_off.csv",(unsigned long)id); if(!SD.exists(p)) return String(p); }
}

void IRAM_ATTR onTickRaw(){ tickCountRaw++; }

static void startTrial(){
  String path = nextPath();
  f = SD.open(path, FILE_WRITE);
  if (!f){ Debug.println("[SD] open FAIL"); return; }
  f.println("ms,mV,µA,p_mW");
  f.printf("# meta, firmware=TXSD_OFF_1201, trial_index=auto, adv_interval_ms=0\r\n");
  logging=true; t0_ms=millis(); nextSampleUs=micros()+SAMPLE_US; lineN=badLines=0; tickCount=0;
  tickStart = (tickCountRaw>0)? (tickCountRaw-1) : 0;
  lastTickSnapshot = tickCountRaw;
  sumP=sumV=sumI=0.0; sampN=0; hasSample=false; firstMs=lastMs=0;
  Debug.printf("[PWR-OFF] start %s\n", path.c_str());
}

static void endTrial(){
  if (!logging) return;
  logging=false;
  uint32_t ms_total = millis() - t0_ms;
  if (ms_total < MIN_TRIAL_MS){
    Debug.printf("[PWR-OFF] ignore short trial ms_total=%lu\n", (unsigned long)ms_total);
    if (f){ f.flush(); f.close(); }
    return;
  }

  double meanP = (sampN>0)? (sumP/sampN) : 0.0;
  double meanV = (sampN>0)? (sumV/sampN) : 0.0;
  double meanI = (sampN>0)? (sumI/sampN) : 0.0;
  double E_mJ  = meanP * (ms_total/1000.0);
  double Eper_uJ = (tickCount>0)? (E_mJ*1000.0/tickCount) : 0.0;

  f.printf("# summary, ms_total=%lu, adv_count=%lu, E_total_mJ=%.3f, E_per_adv_uJ=%.1f\r\n",
           (unsigned long)ms_total, (unsigned long)tickCount, E_mJ, Eper_uJ);
  f.printf("# diag, samples=%lu, rate_hz=%.2f, mean_v=%.3f, mean_i=%.3f, mean_p_mW=%.1f, parse_drop=%lu\r\n",
           (unsigned long)sampN, (ms_total>0? (double)sampN/(ms_total/1000.0):0.0), meanV, meanI, meanP, (unsigned long)badLines);
  f.flush(); f.close();
  Debug.printf("[PWR-OFF] end ms=%lu Nadv=%lu E=%.3fmJ\n", (unsigned long)ms_total, (unsigned long)tickCount, E_mJ);
}

void setup(){
  Debug.begin(115200);
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)){ Debug.println("[SD] init FAIL"); while(1) delay(1000); }

  pinMode(TICK_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(TICK_IN), onTickRaw, RISING);

  Wire.begin(I2C_SDA, I2C_SCL); Wire.setClock(400000);
  ina.begin(); ina.setCalibration_16V_400mA();

  Debug.println("[PWR-OFF] ready");
}

void loop(){
  uint32_t nowMs = millis();

  // TICKで自動開始
  uint32_t tickDelta = tickCountRaw - lastTickSnapshot;
  if (!logging && tickDelta > 0){
    startTrial();
    Debug.printf("[PWR-OFF] trigger start by TICK (delta=%lu, raw=%lu)\n",
                 (unsigned long)tickDelta, (unsigned long)tickCountRaw);
  }

  if (logging){
    tickCount = tickCountRaw - tickStart;
    if (tickCount >= TICK_PER_TRIAL){
      Debug.printf("[PWR-OFF] force end by TICK (count=%lu)\n", (unsigned long)tickCount);
      endTrial();
    } else if ((nowMs - t0_ms) >= FALLBACK_MS){
      Debug.println("[PWR-OFF] Force end (fallback)");
      endTrial();
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
