// === TXSD_1201.ino ===
// INA219をTXSD側で直読みし、SDに ms,mV,µA,p_mW を記録する。
// SYNC_INで開始/終了、TICK_INでadv_countを取得。平均P×durationでE_total計算。
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
static const int SYNC_IN = 26;
static const int TICK_IN = 33;
static const int I2C_SDA = 21;
static const int I2C_SCL = 22;

// 設定
static const uint32_t SAMPLE_US  = 10000; // 10ms = 100Hz
static const bool USE_SYNC_END   = true;  // SYNC立下りで終了
static const uint32_t FALLBACK_MS= 660000; // SYNCなし時のフォールバック

HardwareSerial Debug(0);
Adafruit_INA219 ina;
File f;

volatile bool syncLvl=false, syncEdge=false;
volatile uint32_t tickCount=0;
bool logging=false;
uint32_t t0_ms=0, nextSampleUs=0, lastSyncMs=0;
uint32_t lineN=0, badLines=0;

// 統計
double sumP=0.0; double sumV=0.0; double sumI=0.0; uint32_t sampN=0;
uint32_t firstMs=0, lastMs=0; bool hasSample=false;

static inline String nextPath(){
  SD.mkdir("/logs");
  char p[64];
  for (uint32_t id=1;;++id){ snprintf(p,sizeof(p),"/logs/trial_%03lu_on.csv",(unsigned long)id); if(!SD.exists(p)) return String(p); }
}

void IRAM_ATTR onSync(){ bool s=digitalRead(SYNC_IN); if (s!=syncLvl){ syncLvl=s; syncEdge=true; } }
void IRAM_ATTR onTick(){ if (logging) tickCount++; }

static void startTrial(){
  String path=nextPath();
  f=SD.open(path, FILE_WRITE);
  if (!f){ Debug.println("[SD] open FAIL"); return; }
  f.println("ms,mV,µA,p_mW");
  f.printf("# meta, firmware=TXSD_1201, trial_index=auto, adv_interval_ms=0\r\n");
  logging=true; t0_ms=millis(); nextSampleUs=micros()+SAMPLE_US; lineN=badLines=0; tickCount=0;
  sumP=sumV=sumI=0.0; sampN=0; hasSample=false; firstMs=lastMs=0;
  Debug.printf("[PWR] start %s\n", path.c_str());
}

static void endTrial(){
  if (!logging) return;
  logging=false;
  uint32_t ms_total= hasSample && lastMs>=firstMs ? (lastMs-firstMs) : (millis()-t0_ms);
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
  Debug.printf("[PWR] end ms=%lu Nadv=%lu E=%.3fmJ\n", (unsigned long)ms_total, (unsigned long)tickCount, E_mJ);
}

void setup(){
  Debug.begin(115200);
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)){ Debug.println("[SD] init FAIL"); while(1) delay(1000); }

  pinMode(SYNC_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(SYNC_IN), onSync, CHANGE);
  pinMode(TICK_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(TICK_IN), onTick, RISING);

  Wire.begin(I2C_SDA, I2C_SCL); Wire.setClock(400000);
  ina.begin(); ina.setCalibration_16V_400mA();

  syncLvl=digitalRead(SYNC_IN);
  if (syncLvl) startTrial();
  Debug.println("[PWR] ready");
}

void loop(){
  if (syncEdge){
    noInterrupts(); bool s=syncLvl; syncEdge=false; interrupts();
    if (s && !logging) startTrial();
    else if (!s && logging && USE_SYNC_END) endTrial();
  }

  if (logging){
    uint32_t nowUs=micros();
    while ((int32_t)(nowUs - nextSampleUs) >= 0){
      nextSampleUs += SAMPLE_US;
      float v=ina.getBusVoltage_V();
      float i=ina.getCurrent_mA();
      int32_t mv=(int32_t)lroundf(v*1000.0f);
      int32_t uA=(int32_t)lroundf(i*1000.0f);
      double p_mW=v*i;
      uint32_t relMs=millis()-t0_ms;

      // 統計
      if (!hasSample){ hasSample=true; firstMs=relMs; }
      lastMs=relMs;
      sumP+=p_mW; sumV+=v; sumI+=i; sampN++;

      char buf[64];
      int n=snprintf(buf,sizeof(buf),"%lu,%ld,%ld,%.1f\r\n", (unsigned long)relMs, (long)mv, (long)uA, p_mW);
      if (n>0) f.write((uint8_t*)buf, n); else badLines++;
      lineN++;
      nowUs=micros();
    }

    // フォールバック終了
    if (!USE_SYNC_END && (millis()-t0_ms)>=FALLBACK_MS){ endTrial(); }
  }

  vTaskDelay(1);
}
