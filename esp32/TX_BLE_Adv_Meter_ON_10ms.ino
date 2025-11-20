// === TX_BLE_Adv_Meter_ON_10ms.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// 役割：BLEアドバタイズ(100ms) + SYNC + TICK + INA219 取得（整数CSV: mv,uA）→ UART送出。
//       サンプリング周期のみ 10ms（100Hz）にした ON 用バージョン。
// 配線：SYNC_OUT=25, TICK_OUT=27, UART1 TX=4, I2C 21/22（VCCは3.3V_B推奨）
// 電源：DUT(②)=3.3V_A（測定対象）。INA219 VCCは3.3V_B（ロガ電源側）。
//
// CSV出力： "mv,uA\n" （例：3300,9150）
// 注意：RSHUNT_MILLIOHM は実装シャントに合わせて変更（初期=100 mΩ）

#include <Arduino.h>
#include <Wire.
#include <Adafruit_INA219.h>
#include <BLEDevice.h>

static const uint16_t ADV_INTERVAL_MS = 100;
static const uint32_t SAMPLE_US       = 10000;     // 10msサンプリング（100Hz）
static const bool     USE_TICK_OUT    = true;
static const esp_power_level_t TX_PWR = ESP_PWR_LVL_N0; // 0 dBm

static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN      = 2;
static const int I2C_SDA      = 21;
static const int I2C_SCL      = 22;
static const int UART_TX      = 4;
static const long UART_BAUD   = 230400;

// シャント値（ミリオーム）
#define RSHUNT_MILLIOHM  100   // 実装が 0.1Ω=100 mΩ の場合
// 別レンジ校正を使うなら setCalibration_* を差し替え

HardwareSerial uart1(1);
Adafruit_INA219 ina;
BLEAdvertising* adv = nullptr;

uint16_t seq  = 0;
uint8_t  hold0 = 8; // SYNC直後は "MF0000" を数フレーム

static inline String makeMFD(uint16_t s){
  char b[7]; snprintf(b,sizeof(b),"MF%04X",(unsigned)s); return String(b);
}
static void syncPulse(){
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
  delay(100);
  digitalWrite(SYNC_OUT_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
  seq = 0; hold0 = 8;
}

static uint32_t nextSampleUs, nextAdvMs;

void setup(){
  // GPIO
  pinMode(LED_PIN, OUTPUT);       digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_TICK_OUT){ pinMode(TICK_OUT_PIN, OUTPUT); digitalWrite(TICK_OUT_PIN, LOW); }

  // BLE
  BLEDevice::init("TXM_ESP32");
  BLEDevice::setPower(TX_PWR);
  BLEAdvertising* a = BLEDevice::getAdvertising();
  a->setScanResponse(false); a->setMinPreferred(0);
  uint16_t itv = (uint16_t)(ADV_INTERVAL_MS / 0.625f);
  a->setMinInterval(itv); a->setMaxInterval(itv);
  BLEAdvertisementData ad;
  ad.setName("TXM_ESP32"); ad.setManufacturerData(makeMFD(0));
  a->setAdvertisementData(ad); a->start(); adv = a;

  // INA219
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);               // I2C 400kHz
  ina.begin();
  ina.setCalibration_16V_400mA();      // 代表レンジ（0.1Ω想定）。実装に合わせて要調整。

  // UART
  uart1.begin(UART_BAUD, SERIAL_8N1, -1, UART_TX);

  // 起動2秒後に同期Pulse
  delay(2000);
  syncPulse();

  nextSampleUs = micros() + SAMPLE_US;
  nextAdvMs    = millis() + ADV_INTERVAL_MS;
}

void loop(){
  // 10ms周期（非ブロッキング・追いつき処理）
  uint32_t nowUs = micros();
  int guard = 0;
  while ((int32_t)(nowUs - nextSampleUs) >= 0 && guard < 8){
    nextSampleUs += SAMPLE_US;
    float v = ina.getBusVoltage_V();
    float i = ina.getCurrent_mA();

    // 整数化（mv,uA）→ UART
    int32_t mv = (int32_t)lroundf(v * 1000.0f);
    int32_t uA = (int32_t)lroundf(i * 1000.0f);
    char line[24];
    snprintf(line, sizeof(line), "%04ld,%06ld\n", (long)mv, (long)uA);
    uart1.print(line);

    guard++; nowUs = micros();
  }

  // 100msごとのアドバタイズ更新
  uint32_t nowMs = millis();
  if ((int32_t)(nowMs - nextAdvMs) >= 0){
    nextAdvMs += ADV_INTERVAL_MS;
    uint16_t sendSeq = (hold0>0)? 0 : seq;

    BLEAdvertisementData ad;
    ad.setName("TXM_ESP32"); ad.setManufacturerData(makeMFD(sendSeq));
    adv->setAdvertisementData(ad);

    if (hold0>0) --hold0; else ++seq;

    if (USE_TICK_OUT){
      digitalWrite(TICK_OUT_PIN, HIGH);
      delayMicroseconds(200);
      digitalWrite(TICK_OUT_PIN, LOW);
    }
  }

  // 低負荷化（ライトスリープ誘導）
  vTaskDelay(1);
}
