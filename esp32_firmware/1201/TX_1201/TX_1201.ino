// === TX_1201.ino (with debug) ===
// BLE広告専用の被測定体。SYNC/TICKを出しつつ、シリアルにtrialとSYNCの長さを出力。
// intervalごとにN_ADV_PER_TRIAL回送信し、全グループを順次実行。

#include <Arduino.h>
#include <BLEDevice.h>

// ---- ユーザ設定 ----
static const uint16_t intervals[]      = {100, 500, 1000, 2000};
static const uint8_t  trialsPerGroup[] = {10,  10,   5,    5};
static const uint8_t  N_GROUPS         = 4;
static const uint8_t  START_GROUP      = 0;     // 0=100ms から開始
static const uint16_t N_ADV_PER_TRIAL  = 300;   // 広告回数/トライアル
static const uint32_t GAP_TRIAL_MS     = 5000;  // トライアル間隔
static const uint32_t GAP_GROUP_MS     = 10000; // グループ間隔
static const bool     USE_TICK_OUT     = true;
static const bool     USE_LIGHT_SLEEP_LONG = true; // 長いintervalではCPUをlight sleepさせる
static const uint32_t SLEEP_THRESHOLD_MS  = 400;   // これ以上のintervalでsleep検討
static const uint32_t SLEEP_GUARD_MS      = 5;     // 復帰ガード
static const esp_power_level_t TX_PWR  = ESP_PWR_LVL_N0; // 0 dBm

// ピン
static const int SYNC_OUT_PIN = 25;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN      = 2;
static const long UART_BAUD   = 115200; // デバッグ用

// 内部状態
BLEAdvertising* adv = nullptr;
uint32_t nextAdvMs    = 0;
uint8_t  groupIdx     = 0;
uint8_t  trialIdx     = 0;
bool     trialRunning = false;
uint16_t advCount     = 0;
uint16_t currentInterval = 100;
bool     allDone      = false;

// DEBUG用
static uint32_t dbgSyncHighMs    = 0;   // SYNCをHIGHにした時刻
static uint32_t dbgTrialStartMs  = 0;   // trial開始時刻

static inline String makeMFD(uint16_t seq){
  char b[7];
  snprintf(b, sizeof(b), "MF%04X", (unsigned)seq);
  return String(b);
}

static void syncStart(){
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
  dbgSyncHighMs = millis();  // DEBUG
  Serial.printf("[TX][SYNC] HIGH at %lums\n", (unsigned long)dbgSyncHighMs);
}

static void syncEnd(){
  uint32_t now = millis();
  digitalWrite(SYNC_OUT_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
  uint32_t dur = (dbgSyncHighMs > 0) ? (now - dbgSyncHighMs) : 0; // DEBUG
  Serial.printf("[TX][SYNC] LOW  at %lums (dur=%lums)\n",
                (unsigned long)now, (unsigned long)dur);
}

static void updateBLEInterval(uint16_t ms){
  currentInterval = ms;
  uint16_t itvUnits = (uint16_t)lroundf(ms / 0.625f);
  adv->stop();
  adv->setMinInterval(itvUnits);
  adv->setMaxInterval(itvUnits);
  adv->start();
  Serial.printf("[TX] interval=%u ms (0x%04X)\n",
                (unsigned)ms, (unsigned)itvUnits);
}

static void startTrial(){
  advCount = 0;
  uint32_t now = millis();
  dbgTrialStartMs = now;           // DEBUG
  nextAdvMs = now;                 // すぐ送信開始
  syncStart();
  Serial.printf("[TX] start group=%u/%u trial=%u/%u interval=%u ms (t=%lums)\n",
                (unsigned)(groupIdx+1), (unsigned)N_GROUPS,
                (unsigned)(trialIdx+1), (unsigned)trialsPerGroup[groupIdx],
                (unsigned)currentInterval,
                (unsigned long)now);
  trialRunning = true;
}

static void endTrial(){
  uint32_t now = millis();
  trialRunning = false;
  syncEnd();
  uint32_t trialDur = now - dbgTrialStartMs;  // DEBUG
  Serial.printf("[TX] end   group=%u trial=%u adv_sent=%u dur=%lums\n",
                (unsigned)(groupIdx+1),
                (unsigned)(trialIdx+1),
                (unsigned)advCount,
                (unsigned long)trialDur);
}

static void startGroup(){
  currentInterval = intervals[groupIdx];
  trialIdx = 0;
  Serial.printf("\n[TX] === Group %u start (interval=%u ms, n=%u) ===\n",
                (unsigned)(groupIdx+1),
                (unsigned)currentInterval,
                (unsigned)trialsPerGroup[groupIdx]);
  updateBLEInterval(currentInterval);
  delay(1000);
  startTrial();
}

void setup(){
  Serial.begin(UART_BAUD);
  delay(100); // 少し待ってから
  Serial.println("\n[TX] boot");  // DEBUG: リセット検出用

  pinMode(LED_PIN, OUTPUT);      digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT); digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_TICK_OUT){
    pinMode(TICK_OUT_PIN, OUTPUT);
    digitalWrite(TICK_OUT_PIN, LOW);
  }

  BLEDevice::init("TXM_ESP32");
  BLEDevice::setPower(TX_PWR);
  adv = BLEDevice::getAdvertising();
  adv->setScanResponse(false);
  adv->setMinPreferred(0);
  BLEAdvertisementData ad;
  ad.setName("TXM_ESP32");
  ad.setManufacturerData(makeMFD(0));
  adv->setAdvertisementData(ad);
  adv->start();

  groupIdx = START_GROUP;
  startGroup();
}

void loop(){
  if (allDone){
    vTaskDelay(100);
    return;
  }

  uint32_t nowMs = millis();

  if (trialRunning){
    if ((int32_t)(nowMs - nextAdvMs) >= 0){
      nextAdvMs += currentInterval;

      BLEAdvertisementData ad;
      ad.setName("TXM_ESP32");
      ad.setManufacturerData(makeMFD(advCount));
      adv->setAdvertisementData(ad);

      if (USE_TICK_OUT){
        digitalWrite(TICK_OUT_PIN, HIGH);
        delayMicroseconds(200);
        digitalWrite(TICK_OUT_PIN, LOW);
      }

      advCount++;

      // DEBUG: たまに進捗表示
      if ((advCount % 50) == 0){
        Serial.printf("[TX]   adv seq=%u at t=%lums\n",
                      (unsigned)advCount, (unsigned long)nowMs);
      }

      if (advCount >= N_ADV_PER_TRIAL){
        endTrial();
      } else if (USE_LIGHT_SLEEP_LONG && currentInterval >= SLEEP_THRESHOLD_MS){
        // 次の送信まで時間がある場合はLight Sleepで待機
        uint32_t now2 = millis();
        if (nextAdvMs > now2 + SLEEP_GUARD_MS){
          uint32_t sleepMs = nextAdvMs - now2 - SLEEP_GUARD_MS;
          esp_sleep_enable_timer_wakeup((uint64_t)sleepMs * 1000ULL);
          esp_light_sleep_start();
        }
      }
    }
  } else {
    // 次トライアル/グループへ
    if (trialIdx + 1 < trialsPerGroup[groupIdx]){
      if (nowMs - nextAdvMs >= GAP_TRIAL_MS){
        trialIdx++;
        Serial.printf("[TX] gap done, next trial=%u at t=%lums\n",
                      (unsigned)(trialIdx+1), (unsigned long)nowMs);  // DEBUG
        startTrial();
      }
    } else if (groupIdx + 1 < N_GROUPS){
      if (nowMs - nextAdvMs >= GAP_GROUP_MS){
        groupIdx++;
        Serial.printf("[TX] gap done, next group=%u at t=%lums\n",
                      (unsigned)(groupIdx+1), (unsigned long)nowMs);   // DEBUG
        startGroup();
      }
    } else {
      allDone = true;
      adv->stop();
      Serial.println("[TX] all groups done");
    }
  }

  vTaskDelay(1);
}
