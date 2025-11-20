// === TX_BLE_Adv_Meter_ON_sweep.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// 役割：
//   - BLEアドバタイズを一定間隔（ADV_INTERVAL_MS）で送出（100〜2000 msなど）。
//   - 各トライアルごとに SYNC_OUT を start/high → end/low で出力し、
//     PowerLogger / RX ロガの区切りに使えるようにする。
//   - 各トライアルで N_ADV_PER_TRIAL 回の広告を送ったら終了し、
//     GAP_BETWEEN_TRIALS_MS 待機して次のトライアルを自動実行。
//   - UART1 からは INA219 の整数CSV（mv,uA）を 10ms周期で出力。
//   - Serial にラベル（TX_group_trial）とトライアル開始/終了をログする。
//
// 想定運用：
//   - ADV_INTERVAL_MS を 100, 500, 1000, 2000 ms などに変更してビルド。
//   - RUN_GROUP_ID に条件ID（例: 1=100ms, 2=500ms ...）を設定。
//   - N_ADV_PER_TRIAL=300, N_TRIALS=2 などに設定して、1回セットしたら放置で計測。
//

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <BLEDevice.h>

// ===== ユーザ設定 =====
// 使用するアドバタイズ間隔候補（ms）の例: {100, 500, 1000, 2000}
// BLE仕様上のinterval単位は0.625 msなので、内部では ADV_INTERVAL_MS/0.625 を丸めて使用する。
// 将来150 msなど0.625 msの整数倍でない値を試す場合は、四捨五入（round）で最も近い値に合わせることを推奨。
static const uint16_t ADV_INTERVAL_MS   = 100;    // 100 / 500 / 1000 / 2000 などに変更
static const uint32_t SAMPLE_US         = 10000;  // 計測周期 10ms ≒ 100Hz（固定）
static const uint16_t N_ADV_PER_TRIAL   = 300;    // 1トライアルあたりの広告回数
static const uint8_t  N_TRIALS          = 10;      // トライアル回数
static const uint32_t GAP_BETWEEN_TRIALS_MS = 5000; // トライアル間の待機時間
static const uint8_t  RUN_GROUP_ID      = 1;      // 条件ID（例: 1=100ms, 2=500ms ...）

static const bool     USE_TICK_OUT      = true;
static const esp_power_level_t TX_PWR   = ESP_PWR_LVL_N0; // 0 dBm

// ピンアサイン
static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN      = 2;
static const int I2C_SDA      = 21;
static const int I2C_SCL      = 22;
static const int UART_TX      = 4;
static const long UART_BAUD   = 230400;

// シャント値（ミリオーム）
#define RSHUNT_MILLIOHM  100   // 実装が 0.1Ω=100 mΩ の場合

HardwareSerial uart1(1);
Adafruit_INA219 ina;
BLEAdvertising* adv = nullptr;

uint16_t seq  = 0;
uint8_t  hold0 = 8;   // SYNC直後は "MF0000" を数フレーム維持

// ランタイム状態
static uint32_t nextSampleUs = 0;
static uint32_t nextAdvMs    = 0;
static uint8_t  trialIndex   = 0;   // 0〜N_TRIALS-1
static bool     trialRunning = false;
static uint16_t advCountInTrial = 0;
static uint32_t trialEndMs   = 0;

static inline String makeMFD(uint16_t s){
  char b[7];
  snprintf(b, sizeof(b), "MF%04X", (unsigned)s);
  return String(b);
}

static void syncStart(){
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
}

static void syncEnd(){
  digitalWrite(SYNC_OUT_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
}

static void startTrial(){
  advCountInTrial = 0;
  seq = 0;
  hold0 = 8;
  trialRunning = true;

  uint32_t nowMs = millis();
  nextSampleUs = micros() + SAMPLE_US;
  nextAdvMs    = nowMs + ADV_INTERVAL_MS;

  // 100msパルスのみ（trial中はLED/SYNCを常時OFFにする）
  syncStart();
  delay(100);
  syncEnd();
  Serial.printf("[TX] start trial group=%u, idx=%u, adv_interval_ms=%u\n",
                (unsigned)RUN_GROUP_ID,
                (unsigned)(trialIndex + 1),
                (unsigned)ADV_INTERVAL_MS);
}

static void endTrial(){
  trialRunning = false;
  trialEndMs = millis();
  syncEnd();
  Serial.printf("[TX] end trial group=%u, idx=%u, adv_sent=%u, dur_ms=%lu\n",
                (unsigned)RUN_GROUP_ID,
                (unsigned)(trialIndex + 1),
                (unsigned)advCountInTrial,
                (unsigned long)(trialEndMs)); // 相対時間はログ側で計算
}

void setup(){
  Serial.begin(115200);

  // GPIO
  pinMode(LED_PIN, OUTPUT);       digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_TICK_OUT){
    pinMode(TICK_OUT_PIN, OUTPUT);
    digitalWrite(TICK_OUT_PIN, LOW);
  }

  // BLE
  BLEDevice::init("TXM_ESP32");
  BLEDevice::setPower(TX_PWR);
  BLEAdvertising* a = BLEDevice::getAdvertising();
  a->setScanResponse(false);
  a->setMinPreferred(0);
  uint16_t itv = (uint16_t)lroundf(ADV_INTERVAL_MS / 0.625f);
  a->setMinInterval(itv);
  a->setMaxInterval(itv);
  BLEAdvertisementData ad;
  ad.setName("TXM_ESP32");
  ad.setManufacturerData(makeMFD(0));
  a->setAdvertisementData(ad);
  a->start();
  adv = a;

  // INA219
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);               // I2C 400kHz
  ina.begin();
  ina.setCalibration_16V_400mA();      // 代表レンジ（0.1Ω想定）

  // UART1（PowerLogger行き）
  uart1.begin(UART_BAUD, SERIAL_8N1, -1, UART_TX);

  // 起動2秒後に最初のトライアル開始
  delay(2000);
  trialIndex = 0;
  startTrial();
}

void loop(){
  uint32_t nowUs = micros();
  uint32_t nowMs = millis();

  if (trialRunning){
    // ---- 10ms周期で INA219 サンプリング ----
    int guard = 0;
    while ((int32_t)(nowUs - nextSampleUs) >= 0 && guard < 8){
      nextSampleUs += SAMPLE_US;
      float v = ina.getBusVoltage_V();
      float i = ina.getCurrent_mA();

      int32_t mv = (int32_t)lroundf(v * 1000.0f);
      int32_t uA = (int32_t)lroundf(i * 1000.0f);
      char line[24];
      snprintf(line, sizeof(line), "%04ld,%06ld\n", (long)mv, (long)uA);
      uart1.print(line);

      guard++;
      nowUs = micros();
    }

    // ---- adv_interval ごとのアドバタイズ更新 ----
    if ((int32_t)(nowMs - nextAdvMs) >= 0){
      nextAdvMs += ADV_INTERVAL_MS;
      uint16_t sendSeq = (hold0>0)? 0 : seq;

      BLEAdvertisementData ad;
      ad.setName("TXM_ESP32");
      ad.setManufacturerData(makeMFD(sendSeq));
      adv->setAdvertisementData(ad);

      if (hold0>0) --hold0;
      else         ++seq;

      if (USE_TICK_OUT){
        digitalWrite(TICK_OUT_PIN, HIGH);
        delayMicroseconds(200);
        digitalWrite(TICK_OUT_PIN, LOW);
      }

      advCountInTrial++;
      if (advCountInTrial >= N_ADV_PER_TRIAL){
        endTrial();
      }
    }
  } else {
    // トライアル間の待機 / 次トライアル開始
    if (trialIndex + 1 < N_TRIALS){
      if (nowMs - trialEndMs >= GAP_BETWEEN_TRIALS_MS){
        trialIndex++;
        startTrial();
      }
    } else {
      // 全トライアル終了後はアイドル（BLE広告はそのまま or 停止してもよい）
      vTaskDelay(10);
    }
  }

  // 他タスクに譲る
  vTaskDelay(1);
}
