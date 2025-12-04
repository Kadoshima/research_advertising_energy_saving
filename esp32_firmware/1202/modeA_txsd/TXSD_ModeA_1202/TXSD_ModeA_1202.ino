// Mode A: logger for true OFF baseline
// 起動時に自動開始し、時間終了で1トライアルのみ記録。TICK/ SYNC は使用しない。
// 計測後はDeep Sleepへ移行し、追加消費を最小化する。

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
static const int I2C_SDA = 21;
static const int I2C_SCL = 22;

// 設定
static const uint32_t SAMPLE_US   = 10000;    // 100 Hz
static const uint32_t TRIAL_MS    = 300000;   // 5分 (必要に応じて変更)
static const uint64_t SLEEP_US    = 0ULL;     // 記録後のDeep Sleep (無期限)

HardwareSerial Debug(0);
Adafruit_INA219 ina;
File f;

double sumP=0.0, sumV=0.0, sumI=0.0;
uint32_t sampN=0, firstMs=0, lastMs=0;
bool hasSample=false;
uint32_t t0_ms=0, nextSampleUs=0;

static inline String nextPath(){
  SD.mkdir("/logs");
  char p[64];
  for(uint32_t id=1;;++id){
    snprintf(p,sizeof(p),"/logs/trial_%03lu_offA.csv",(unsigned long)id);
    if(!SD.exists(p)) return String(p);
  }
}

static void startTrial(){
  String path = nextPath();
  f = SD.open(path, FILE_WRITE);
  if (!f){
    Debug.println("[PWR] SD open FAIL");
    while(1) delay(1000);
  }
  f.println("ms,mV,µA,p_mW");
  f.printf("# meta, firmware=TXSD_ModeA_1202, trial_index=1, mode=A\n");
  t0_ms = millis();
  nextSampleUs = micros() + SAMPLE_US;
  Debug.printf("[PWR] start %s\n", path.c_str());
}

static void endTrial(){
  uint32_t ms_total = millis() - t0_ms;
  double meanP = (sampN>0)? (sumP/sampN) : 0.0;
  double meanV = (sampN>0)? (sumV/sampN) : 0.0;
  double meanI = (sampN>0)? (sumI/sampN) : 0.0;
  double E_mJ  = meanP * (ms_total/1000.0);

  f.printf("# summary, ms_total=%lu, adv_count=0, E_total_mJ=%.3f\n",
           (unsigned long)ms_total, E_mJ);
  f.printf("# diag, samples=%lu, rate_hz=%.2f, mean_v=%.3f, mean_i=%.3f, mean_p_mW=%.1f\n",
           (unsigned long)sampN,
           ms_total>0 ? (double)sampN/(ms_total/1000.0) : 0.0,
           meanV, meanI, meanP);
  f.flush();
  f.close();
  Debug.printf("[PWR] end ms=%lu E=%.3fmJ\n", (unsigned long)ms_total, E_mJ);
}

void setup() {
  Debug.begin(115200);
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)){
    Debug.println("[SD] init FAIL");
    while(1) delay(1000);
  }
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);
  ina.begin();
  ina.setCalibration_16V_400mA();

  startTrial();
}

void loop() {
  uint32_t nowMs = millis();
  uint32_t nowUs = micros();

  // サンプリング
  while ((int32_t)(nowUs - nextSampleUs) >= 0){
    nextSampleUs += SAMPLE_US;
    float v = ina.getBusVoltage_V();
    float i = ina.getCurrent_mA();
    int32_t mv = (int32_t)lroundf(v*1000.0f);
    int32_t uA = (int32_t)lroundf(i*1000.0f);
    double p_mW = v * i;
    uint32_t relMs = millis() - t0_ms;

    if (!hasSample){ hasSample=true; firstMs=relMs; }
    lastMs = relMs;
    sumP += p_mW; sumV += v; sumI += i; sampN++;

    char buf[64];
    int n = snprintf(buf,sizeof(buf),"%lu,%ld,%ld,%.1f\n",
                     (unsigned long)relMs, (long)mv, (long)uA, p_mW);
    if (n>0) f.write((uint8_t*)buf, n);
    nowUs = micros();
  }

  if (nowMs - t0_ms >= TRIAL_MS){
    endTrial();
    Debug.println("[PWR] deep sleep after trial");
    esp_sleep_enable_timer_wakeup(SLEEP_US);
    esp_deep_sleep_start();
  }

  vTaskDelay(1);
}
