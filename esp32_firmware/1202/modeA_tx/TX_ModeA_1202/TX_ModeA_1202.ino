// Mode A: true OFF baseline
// 起動直後に最低限の初期化だけ行い、すぐにDeep Sleepへ移行する。
// BLE/WiFiは使わない。wake源はタイマーのみ（無効化に近い）。

#include <WiFi.h>
#include <Arduino.h>
#include <esp_wifi.h>
#include <esp_bt.h>

// Wake なしで無期限 Deep Sleep。外部リセットのみで復帰。

void setup() {
  delay(50);                  // 安定化待ち
  WiFi.mode(WIFI_OFF);
  btStop();
  esp_wifi_stop();
  // 必要に応じてGPIOのプルダウン等をここで設定

  Serial.begin(115200);
  Serial.println("[TX-A] entering deep sleep (true OFF baseline, no wake source)");
  Serial.flush();

  // すべてのウェイクアップソースを無効化したうえでDeep Sleepへ
  esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
  esp_deep_sleep_start();
}

void loop() {
  // 到達しない
}
