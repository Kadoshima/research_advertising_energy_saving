// TX_ModeC2prime_1210.ino (sleep_eval_scan90)
// 目的:
// - sleep ON/OFF × adv_interval(100/500/1000/2000ms) を 1回の実行で全条件取得する。
//
// Step1（sleep効果の最大見積もり）方針:
// - 固定長/固定内容のManufacturerData（ダミー）。周期的なpayload更新はしない。
// - 広告間隔は controller に設定して任せる（CPU側で周期処理を作らない）。
// - trial開始/終了で adv->start/stop と SYNC(25) を揃える（trial外の広告＝余計な消費を混ぜない）。
// - TXSD向けに trial開始直後のTICK(27)パルス数で「条件ID（sleep×interval）」を送る（preamble）。周期TICKは出さない。
//
// 注意:
// - sleep ON/OFF は esp_pm_lock(ESP_PM_NO_LIGHT_SLEEP) の acquire/release で切替する。
// - 実際にlight-sleepが入るかは build設定/PM/tickless 等にも依存。

#include <Arduino.h>
#include <BLEDevice.h>
#include <math.h>

#ifdef ARDUINO_ARCH_ESP32
#include "esp_pm.h"
#endif

// ==== 設定（計測スケジュール） ====
static const uint32_t TRIAL_DURATION_MS = 60000; // 1条件 約1分
static const uint32_t GAP_MS = 5000;             // 条件間の休止
static const uint8_t N_CYCLES = 2;               // 8条件×2 = 16試行（必要なら1に落とす）

// ==== 設定（ノイズ要因の抑制） ====
static const bool USE_LED = false;               // LEDは電力を汚すので基本OFF
static const bool ENABLE_TICK_PREAMBLE = true;   // trial開始直後だけ条件ID送信用にTICKを打つ

// ==== ピン ====
static const int SYNC_OUT_PIN = 25; // TX -> RX/TXSD SYNC
static const int TICK_OUT_PIN = 27; // TX -> TXSD TICK (preamble)
static const int LED_PIN = 2;

// ==== BLE ====
static BLEAdvertising* adv = nullptr;
static bool trialRunning = false;
static uint32_t trialStartMs = 0;
static uint32_t gapStartMs = 0;
static uint8_t condIndex = 0;
static uint8_t cycleIndex = 0;

#ifdef ARDUINO_ARCH_ESP32
static esp_pm_lock_handle_t noLightSleepLock = nullptr;
static bool sleepBlocked = false;
#endif

struct Condition {
  uint16_t adv_ms;
  bool allow_light_sleep;
  uint8_t cond_id;     // 1..8（TXSD側で同じマップを使う）
  const char* label;   // <= 11 chars（RXのlabel[12]想定）
};

// 条件ID（TXSD側のデコードと一致させること）
// 1: 100ms_OFF, 2: 100ms_ON
// 3: 500ms_OFF, 4: 500ms_ON
// 5: 1000ms_OFF, 6: 1000ms_ON
// 7: 2000ms_OFF, 8: 2000ms_ON
static const Condition CONDS[] = {
  {100,  false, 1, "I100_OFF"},
  {100,  true,  2, "I100_ON"},
  {500,  false, 3, "I500_OFF"},
  {500,  true,  4, "I500_ON"},
  {1000, false, 5, "I1000_OFF"},
  {1000, true,  6, "I1000_ON"},
  {2000, false, 7, "I2000_OFF"},
  {2000, true,  8, "I2000_ON"},
};
static const uint8_t N_CONDS = sizeof(CONDS) / sizeof(CONDS[0]);

static inline uint16_t ms_to_0p625(float ms) {
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

static void setSleepAllowed(bool allowSleep) {
#ifdef ARDUINO_ARCH_ESP32
  if (!noLightSleepLock) return;
  if (allowSleep) {
    if (sleepBlocked) {
      esp_pm_lock_release(noLightSleepLock);
      sleepBlocked = false;
    }
  } else {
    if (!sleepBlocked) {
      esp_pm_lock_acquire(noLightSleepLock);
      sleepBlocked = true;
    }
  }
#else
  (void)allowSleep;
#endif
}

static void tickPreamble(uint8_t nPulses) {
  if (!ENABLE_TICK_PREAMBLE) return;
  for (uint8_t i = 0; i < nPulses; i++) {
    digitalWrite(TICK_OUT_PIN, HIGH);
    delayMicroseconds(200);
    digitalWrite(TICK_OUT_PIN, LOW);
    delay(20);
  }
}

static void configureAdvertising(const Condition& c) {
  const uint16_t adv_units = ms_to_0p625((float)c.adv_ms);
  adv->setMinInterval(adv_units);
  adv->setMaxInterval(adv_units);

  BLEAdvertisementData ad;
  ad.setName("TX_SLEEP_EVAL");
  // RXパーサ互換: "<seq>_<label>"
  String mfd = String("0000_") + String(c.label);
  ad.setManufacturerData(mfd);
  adv->setAdvertisementData(ad);
}

static void startTrial(const Condition& c) {
  trialStartMs = millis();
  trialRunning = true;

  setSleepAllowed(c.allow_light_sleep);
  configureAdvertising(c);

  syncStart();
  if (adv) adv->start();

  // TXSD側が SYNC を検出して preamble計数に入る猶予を与える
  delay(200);

  // TXSDへ条件IDを送る（preamble）
  tickPreamble(c.cond_id);
}

static void endTrial() {
  trialRunning = false;
  if (adv) adv->stop();
  syncEnd();
  gapStartMs = millis();
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

#ifdef ARDUINO_ARCH_ESP32
  (void)esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP, 0, "sleep_eval", &noLightSleepLock);
#endif

  condIndex = 0;
  cycleIndex = 0;
  gapStartMs = 0;

  startTrial(CONDS[condIndex]);
}

void loop() {
  const uint32_t nowMs = millis();

  if (trialRunning) {
    if ((nowMs - trialStartMs) >= TRIAL_DURATION_MS) {
      endTrial();
    }
    vTaskDelay(pdMS_TO_TICKS(500));
    return;
  }

  // gap中
  if (gapStartMs == 0) gapStartMs = nowMs;
  if ((nowMs - gapStartMs) < GAP_MS) {
    vTaskDelay(pdMS_TO_TICKS(200));
    return;
  }

  // 次条件へ
  condIndex++;
  if (condIndex >= N_CONDS) {
    condIndex = 0;
    cycleIndex++;
  }
  if (cycleIndex >= N_CYCLES) {
    // 終了（SYNC LOW、広告停止、sleepは許可側へ）
    setSleepAllowed(true);
    vTaskDelay(pdMS_TO_TICKS(1000));
    return;
  }

  gapStartMs = 0;
  startTrial(CONDS[condIndex]);
  vTaskDelay(pdMS_TO_TICKS(200));
}
