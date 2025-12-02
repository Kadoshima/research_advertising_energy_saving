// TX_OFF_1201.ino
// BLE/OFFの被測定体。BLEを起動せず、GPIO27で1HzのTICKパルスを出したら直ちにDeep Sleepに入る。
// 次のパルスもタイマ復帰で実行される（毎回リブートされるが、TXSDはTICKを数えるだけなので問題なし）。
// 配線: TICK_OUT=27 -> TXSD TICK_IN=33。BLE/ Wi-Fiは使わない。

#include <Arduino.h>
#include "esp_sleep.h"

// ユーザ設定
static const uint32_t TICK_INTERVAL_MS = 1000; // 次パルスまでの間隔
static const uint32_t TICK_PULSE_MS    = 100;  // パルス幅
static const int TICK_OUT_PIN = 27;
static const long UART_BAUD = 115200;  // デバッグ用（任意）

void pulseTick(){
  digitalWrite(TICK_OUT_PIN, HIGH);
  delay(TICK_PULSE_MS);
  digitalWrite(TICK_OUT_PIN, LOW);
}

void setup(){
  Serial.begin(UART_BAUD);
  pinMode(TICK_OUT_PIN, OUTPUT);
  digitalWrite(TICK_OUT_PIN, LOW);

  // デバッグ表示（sleep直前まで出力可能）
  Serial.println("[TX-OFF] wake, emit TICK then deep sleep");

  // TICKパルスを1回だけ出力
  pulseTick();

  // 次の起床タイマをセットしてDeep Sleepへ
  uint64_t sleep_us = (TICK_INTERVAL_MS - TICK_PULSE_MS) * 1000ULL;
  if (sleep_us < 1000) sleep_us = 1000; // ガード
  esp_sleep_enable_timer_wakeup(sleep_us);
  Serial.flush();
  esp_deep_sleep_start();
}

void loop(){
  // 実行されない（deep sleep運用）
}
