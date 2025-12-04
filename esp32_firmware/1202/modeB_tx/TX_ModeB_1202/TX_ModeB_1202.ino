// Mode B: 待機ベースライン（ライトスリープ＋低頻度センサ読み想定）
// BLEはOFF。一定周期で軽い処理を行い、間は light sleep。
// 計測対象: 「実運用待機」想定の消費電力。

#include <WiFi.h>
#include <Arduino.h>
#include <esp_wifi.h>
#include <esp_bt.h>

static const uint32_t POLL_MS    = 40;     // 擬似センサ読み間隔 (~25Hz)
static const uint32_t WORK_US    = 500;    // 疑似計算時間 (微小)
static const uint32_t TRIAL_MS   = 300000; // 記録ウィンドウ

uint32_t t0_ms=0;

void setup(){
  delay(50);
  WiFi.mode(WIFI_OFF);
  btStop();
  esp_wifi_stop();
  Serial.begin(115200);
  Serial.println("[TX-B] standby mode start");
  t0_ms = millis();
}

void loop(){
  uint32_t now = millis();
  if (now - t0_ms >= TRIAL_MS){
    Serial.println("[TX-B] done window -> deep sleep");
    esp_sleep_enable_timer_wakeup(0); // 無期限
    esp_deep_sleep_start();
  }

  // 疑似センサ読み＋軽い処理
  volatile uint32_t acc=0;
  uint32_t start = micros();
  while (micros() - start < WORK_US){
    acc += 1;
  }

  // light sleepで待機
  esp_sleep_enable_timer_wakeup((uint64_t)POLL_MS * 1000ULL);
  esp_light_sleep_start();
}
