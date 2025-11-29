// === TX_BLE_Adv.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// 役割：
//   - BLEアドバタイズを一定間隔で送出
//   - 各トライアルごとに SYNC_OUT パルスを出力（PowerLogger/RXの区切り）
//   - N_ADV_PER_TRIAL 回の広告送信後、GAP_BETWEEN_TRIALS_MS 待機して次トライアル
//   - 全interval (100, 500, 1000, 2000 ms) を自動で順次実行
//   - UART1 から INA219 の整数CSV（mv,uA）を 10ms周期で出力
//
// 自動実行シーケンス：
//   Group 1: 100ms  × 10 trials (各30秒, 計5分)
//   Group 2: 500ms  × 10 trials (各150秒, 計25分)
//   Group 3: 1000ms × 5 trials  (各300秒, 計25分)
//   Group 4: 2000ms × 5 trials  (各600秒, 計50分)
//   総計: 約105分 (1時間45分)
//
// 配線：
//   SYNC_OUT=25 → TXSD(26), RX(26)
//   TICK_OUT=27 → TXSD(33)
//   UART_TX=4   → TXSD RX=34
//   I2C SDA=21, SCL=22 → INA219 (Vcc=3.3V直結)
//

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <BLEDevice.h>

// ===== ユーザ設定 =====
static const uint32_t SAMPLE_US              = 10000;  // 計測周期 10ms ≒ 100Hz（固定）
static const uint16_t N_ADV_PER_TRIAL        = 300;    // 1トライアルあたりの広告回数（固定）
static const uint32_t GAP_BETWEEN_TRIALS_MS  = 5000;   // トライアル間の待機時間
static const uint32_t GAP_BETWEEN_GROUPS_MS  = 10000;  // グループ間の待機時間

// ===== interval別設定 =====
// intervals[]: 100, 500, 1000, 2000 ms
// trialsPerGroup[]: 各intervalでのトライアル回数
// START_GROUP_INDEX: 開始グループ (0=100ms, 1=500ms, 2=1000ms, 3=2000ms)
static const uint16_t intervals[]      = {100, 500, 1000, 2000};
static const uint8_t  trialsPerGroup[] = {10,  10,  5,    5};
static const uint8_t  N_GROUPS         = 4;
static const uint8_t  START_GROUP_INDEX = 0;  // 0から開始（変更可: 0-3）

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
static uint8_t  groupIndex   = 0;    // 0〜N_GROUPS-1 (interval切り替え)
static uint8_t  trialIndex   = 0;    // 0〜trialsPerGroup[groupIndex]-1
static bool     trialRunning = false;
static uint16_t advCountInTrial = 0;
static uint32_t trialEndMs   = 0;
static uint16_t currentIntervalMs = 100;
static bool     allDone      = false;

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

static void updateBLEInterval(uint16_t intervalMs){
  currentIntervalMs = intervalMs;
  uint16_t itv = (uint16_t)lroundf(intervalMs / 0.625f);
  adv->stop();
  adv->setMinInterval(itv);
  adv->setMaxInterval(itv);
  adv->start();
  Serial.printf("[TX] BLE interval updated to %u ms (0x%04X units)\n",
                (unsigned)intervalMs, (unsigned)itv);
}

static void startTrial(){
  advCountInTrial = 0;
  seq = 0;
  hold0 = 8;
  trialRunning = true;

  uint32_t nowMs = millis();
  nextSampleUs = micros() + SAMPLE_US;
  nextAdvMs    = nowMs + currentIntervalMs;

  // 100msパルスのみ（trial中はLED/SYNCを常時OFFにする）
  syncStart();
  delay(100);
  syncEnd();

  uint32_t expectedDurS = (uint32_t)N_ADV_PER_TRIAL * currentIntervalMs / 1000;
  Serial.printf("[TX] start trial group=%u, idx=%u/%u, interval_ms=%u, expected_dur=%lus\n",
                (unsigned)(groupIndex + 1),
                (unsigned)(trialIndex + 1),
                (unsigned)trialsPerGroup[groupIndex],
                (unsigned)currentIntervalMs,
                (unsigned long)expectedDurS);
}

static void endTrial(){
  trialRunning = false;
  trialEndMs = millis();
  syncEnd();
  Serial.printf("[TX] end trial group=%u, idx=%u, adv_sent=%u\n",
                (unsigned)(groupIndex + 1),
                (unsigned)(trialIndex + 1),
                (unsigned)advCountInTrial);
}

static void startGroup(){
  currentIntervalMs = intervals[groupIndex];
  trialIndex = 0;

  Serial.printf("\n[TX] ========== Starting Group %u ==========\n", (unsigned)(groupIndex + 1));
  Serial.printf("[TX] interval=%u ms, n_trials=%u, n_adv_per_trial=%u\n",
                (unsigned)currentIntervalMs,
                (unsigned)trialsPerGroup[groupIndex],
                (unsigned)N_ADV_PER_TRIAL);

  updateBLEInterval(currentIntervalMs);
  delay(1000);  // BLE interval変更後の安定待ち
  startTrial();
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
  uint16_t itv = (uint16_t)lroundf(100 / 0.625f);  // 初期値100ms
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

  // 実行計画を表示
  Serial.println("\n[TX] ===== Automatic Multi-Interval Baseline Measurement =====");
  Serial.printf("[TX] N_ADV_PER_TRIAL = %u (fixed)\n", (unsigned)N_ADV_PER_TRIAL);
  Serial.printf("[TX] START_GROUP_INDEX = %u (%u ms)\n",
                (unsigned)START_GROUP_INDEX, (unsigned)intervals[START_GROUP_INDEX]);
  uint32_t totalSeconds = 0;
  for (int g = START_GROUP_INDEX; g < N_GROUPS; g++){
    uint32_t trialSec = (uint32_t)N_ADV_PER_TRIAL * intervals[g] / 1000;
    uint32_t groupSec = trialSec * trialsPerGroup[g] + GAP_BETWEEN_TRIALS_MS/1000 * (trialsPerGroup[g]-1);
    const char* marker = (g == START_GROUP_INDEX) ? " <-- START" : "";
    Serial.printf("[TX]   Group %d: %4u ms × %u trials (each %lus, total ~%lus)%s\n",
                  g+1, intervals[g], trialsPerGroup[g],
                  (unsigned long)trialSec, (unsigned long)groupSec, marker);
    totalSeconds += groupSec;
  }
  Serial.printf("[TX] Estimated total runtime: ~%lu min\n", (unsigned long)(totalSeconds/60 + 1));
  Serial.println("[TX] Starting in 2 seconds...\n");

  // 起動2秒後に開始グループから開始
  delay(2000);
  groupIndex = START_GROUP_INDEX;
  startGroup();
}

void loop(){
  if (allDone){
    vTaskDelay(100);
    return;
  }

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
      nextAdvMs += currentIntervalMs;
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
    // トライアル間の待機 / 次トライアル or 次グループ開始
    if (trialIndex + 1 < trialsPerGroup[groupIndex]){
      // 同じグループ内の次トライアル
      if (nowMs - trialEndMs >= GAP_BETWEEN_TRIALS_MS){
        trialIndex++;
        startTrial();
      }
    } else if (groupIndex + 1 < N_GROUPS){
      // 次のグループへ
      if (nowMs - trialEndMs >= GAP_BETWEEN_GROUPS_MS){
        groupIndex++;
        startGroup();
      }
    } else {
      // 全グループ完了
      if (!allDone){
        allDone = true;
        Serial.println("\n[TX] ========================================");
        Serial.println("[TX] All groups completed!");
        Serial.println("[TX] ========================================\n");
        // BLE広告を停止（省電力）
        adv->stop();
      }
    }
  }

  // 他タスクに譲る
  vTaskDelay(1);
}
