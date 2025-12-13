// TX_ModeC2prime_1210.ino (sleep_eval_scan90版)
// 目的: sleep ON/OFF × adv_interval(100ms/2000ms) の平均電力差を最短で確認するための最小TX。
// 方針:
// - 固定長/固定内容のManufacturerData（ダミー）。
// - 広告間隔は controller に設定して任せる（CPU側の周期処理で「擬似100ms」を作らない）。
// - SYNC(25) をHIGHで trial 開始、終了時にLOW（TXSD/RXのログゲート）。
// - 余計な周期処理（SD/ラベル再生/Serial/頻繁なpayload更新/TICK）はデフォルト無効。

#include <Arduino.h>
#include <BLEDevice.h>
#include <math.h>

// ==== 設定 ====
static const uint16_t ADV_MS = 2000;              // 100 or 2000（条件ごとに変更）
static const uint32_t TRIAL_DURATION_MS = 60000; // 条件間で固定（例: 60s）
static const bool REPEAT_TRIALS = false;         // 連続実行したい場合のみtrue
static const uint32_t IDLE_GAP_MS = 5000;        // REPEAT_TRIALS=true のときの休止

static const bool USE_LED = false;               // LEDは電力を汚すので基本OFF
static const bool ENABLE_TICK = false;           // sleep比較ではOFF（周期起床を増やすため）

// ==== ピン ====
static const int SYNC_OUT_PIN = 25; // TX -> RX/TXSD SYNC
static const int TICK_OUT_PIN = 27; // TX -> TXSD TICK (任意)
static const int LED_PIN = 2;

// ==== BLE ====
static BLEAdvertising* adv = nullptr;
static bool trialRunning = false;
static uint32_t trialStartMs = 0;
static uint32_t idleStartMs = 0;

static inline uint16_t ms_to_0p625(float ms) {
  // BLE HCI unit: 0.625 ms
  long v = lroundf(ms / 0.625f);
  if (v < 0x20) v = 0x20;       // 20ms minimum
  if (v > 0x4000) v = 0x4000;   // 10.24s maximum
  return (uint16_t)v;
}

static void syncStart() {
  if (USE_LED) digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
}

static void syncEnd() {
  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_LED) digitalWrite(LED_PIN, LOW);
}

static void startTrial() {
  trialStartMs = millis();
  trialRunning = true;
  syncStart();
  if (adv) adv->start();
}

static void endTrial() {
  trialRunning = false;
  if (adv) adv->stop();
  syncEnd();
  idleStartMs = millis();
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);
  digitalWrite(SYNC_OUT_PIN, LOW);
  pinMode(TICK_OUT_PIN, OUTPUT);
  digitalWrite(TICK_OUT_PIN, LOW);

  BLEDevice::init("TX_SLEEP_EVAL");
  BLEDevice::setPower(ESP_PWR_LVL_N0);
  adv = BLEDevice::getAdvertising();
  adv->setScanResponse(false);
  adv->setMinPreferred(0);

  // 広告間隔を明示（0.625ms単位）
  const uint16_t adv_units = ms_to_0p625((float)ADV_MS);
  adv->setMinInterval(adv_units);
  adv->setMaxInterval(adv_units);

  // 固定ダミーペイロード（固定長/固定内容）
  BLEAdvertisementData ad;
  ad.setName("TX_SLEEP_EVAL");
  // RX側の既存パーサ互換: "0000_DUMMY"
  ad.setManufacturerData(String("0000_DUMMY"));
  adv->setAdvertisementData(ad);

  startTrial();
}

void loop() {
  const uint32_t nowMs = millis();

  if (trialRunning) {
    if ((nowMs - trialStartMs) >= TRIAL_DURATION_MS) {
      endTrial();
    }
    // 監視は低頻度にして、sleep可否を汚さない
    vTaskDelay(pdMS_TO_TICKS(1000));
    return;
  }

  if (REPEAT_TRIALS) {
    if (idleStartMs != 0 && (nowMs - idleStartMs) >= IDLE_GAP_MS) {
      startTrial();
    }
  }

  vTaskDelay(pdMS_TO_TICKS(1000));
}
