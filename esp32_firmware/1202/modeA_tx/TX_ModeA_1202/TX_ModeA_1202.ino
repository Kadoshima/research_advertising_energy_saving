// Mode A: true OFF baseline
// 起動直後に最低限の初期化だけ行い、すぐにDeep Sleepへ移行する。
// BLE/WiFiは使わない。wake源はタイマーのみ（無効化に近い）。

#include <WiFi.h>
#include <Arduino.h>
#include <esp_wifi.h>
#include <esp_bt.h>

static const uint64_t DEEP_SLEEP_US = 0ULL;  // 0: 無期限

void setup() {
  delay(50);                  // 安定化待ち
  WiFi.mode(WIFI_OFF);
  btStop();
  esp_wifi_stop();
  // 全GPIOはデフォルトのまま。必要ならここで入力プルダウン等を設定。
  Serial.begin(115200);
  Serial.println("[TX-A] entering deep sleep (true OFF baseline)");

  // 無期限 Deep Sleep（外部リセットでのみ復帰）
  esp_sleep_enable_timer_wakeup(DEEP_SLEEP_US);
  esp_deep_sleep_start();
}

void loop() {
  // 到達しない
}
