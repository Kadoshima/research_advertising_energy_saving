// TX_DeltaE_V3_ON_2000ms.ino
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
// Role: BLE advertising at fixed interval, SYNC for trial boundary, TICK per adv.

#include <Arduino.h>
#include <BLEDevice.h>
#include <string>

static const char FW_TAG[] = "TX_DeltaE_V3_ON_2000ms";
static const char PROGRAM_ID[] = "TX_DELTAE_V3_ON_2000MS_20260114";

static const uint16_t ADV_INTERVAL_MS = 2000;
static const uint32_t TRIAL_MS = 60000;
static const uint8_t N_TRIALS = 10;
static const uint32_t GAP_BETWEEN_TRIALS_MS = 5000;
static const bool USE_TICK_OUT = true;
static const esp_power_level_t TX_PWR = ESP_PWR_LVL_N0; // 0 dBm

static const int SYNC_OUT_PIN = 25;
static const int SYNC_ALT_OUT_PIN = 26; // optional mirror of SYNC_OUT
static const bool USE_SYNC_ALT_OUT = true;
static const int TICK_OUT_PIN = 27;
static const int LED_PIN = 2;

BLEAdvertising* adv = nullptr;
static std::string g_mfd;
static char g_mfd_buf[7];

uint16_t seq = 0;
uint8_t hold0 = 8;
uint32_t nextAdvMs = 0;
uint32_t trialStartMs = 0;
uint8_t trialIndex = 0;
bool trialRunning = false;
uint32_t advCount = 0;
uint32_t trialEndMs = 0;

static inline const std::string& makeMFD(uint16_t s) {
  snprintf(g_mfd_buf, sizeof(g_mfd_buf), "MF%04X", (unsigned)s);
  g_mfd.assign(g_mfd_buf, 6);
  return g_mfd;
}

static void syncStart() {
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
  if (USE_SYNC_ALT_OUT) digitalWrite(SYNC_ALT_OUT_PIN, HIGH);
}

static void syncEnd() {
  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_SYNC_ALT_OUT) digitalWrite(SYNC_ALT_OUT_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
}

static void updateBLEInterval(uint16_t intervalMs) {
  uint16_t itv = (uint16_t)lroundf(intervalMs / 0.625f);
  adv->stop();
  adv->setMinInterval(itv);
  adv->setMaxInterval(itv);
  adv->start();
  Serial.printf("[TX] interval=%u ms\n", (unsigned)intervalMs);
}

static void startTrial() {
  trialRunning = true;
  trialStartMs = millis();
  nextAdvMs = trialStartMs + ADV_INTERVAL_MS;
  advCount = 0;
  seq = 0;
  hold0 = 8;
  syncStart();
  Serial.printf("[TX] start trial %u/%u interval=%u ms\n",
                (unsigned)(trialIndex + 1), (unsigned)N_TRIALS, (unsigned)ADV_INTERVAL_MS);
}

static void endTrial() {
  trialRunning = false;
  trialEndMs = millis();
  syncEnd();
  Serial.printf("[TX] end trial %u/%u adv_sent=%lu\n",
                (unsigned)(trialIndex + 1), (unsigned)N_TRIALS, (unsigned long)advCount);
}

void setup() {
  Serial.begin(115200);
  Serial.printf("[FW] %s program_id=%s\n", FW_TAG, PROGRAM_ID);
  g_mfd.reserve(6);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);
  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_SYNC_ALT_OUT) {
    pinMode(SYNC_ALT_OUT_PIN, OUTPUT);
    digitalWrite(SYNC_ALT_OUT_PIN, LOW);
  }
  if (USE_TICK_OUT) {
    pinMode(TICK_OUT_PIN, OUTPUT);
    digitalWrite(TICK_OUT_PIN, LOW);
  }

  BLEDevice::init("TX_DELTAE_V3");
  BLEDevice::setPower(TX_PWR);
  BLEAdvertising* a = BLEDevice::getAdvertising();
  a->setScanResponse(false);
  a->setMinPreferred(0);
  uint16_t itv = (uint16_t)lroundf(ADV_INTERVAL_MS / 0.625f);
  a->setMinInterval(itv);
  a->setMaxInterval(itv);
  BLEAdvertisementData ad;
  ad.setName("TX_DELTAE_V3");
  ad.setManufacturerData(makeMFD(0));
  a->setAdvertisementData(ad);
  a->start();
  adv = a;

  updateBLEInterval(ADV_INTERVAL_MS);
  delay(1000);
  trialIndex = 0;
  startTrial();
}

void loop() {
  uint32_t nowMs = millis();

  if (trialRunning) {
    if ((int32_t)(nowMs - nextAdvMs) >= 0) {
      nextAdvMs += ADV_INTERVAL_MS;
      uint16_t sendSeq = (hold0 > 0) ? 0 : seq;
      BLEAdvertisementData ad;
      ad.setName("TX_DELTAE_V3");
      ad.setManufacturerData(makeMFD(sendSeq));
      adv->setAdvertisementData(ad);
      if (hold0 > 0) {
        --hold0;
      } else {
        ++seq;
      }

      if (USE_TICK_OUT) {
        digitalWrite(TICK_OUT_PIN, HIGH);
        delayMicroseconds(200);
        digitalWrite(TICK_OUT_PIN, LOW);
      }
      advCount++;
    }

    if ((nowMs - trialStartMs) >= TRIAL_MS) {
      endTrial();
    }
  } else {
    if (trialIndex + 1 < N_TRIALS) {
      if (nowMs - trialEndMs >= GAP_BETWEEN_TRIALS_MS) {
        trialIndex++;
        startTrial();
      }
    } else {
      static bool done = false;
      if (!done) {
        done = true;
        Serial.printf("[TX] All %u trials completed.\n", (unsigned)N_TRIALS);
      }
      vTaskDelay(100);
    }
  }

  vTaskDelay(1);
}
