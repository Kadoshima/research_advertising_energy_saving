// test.ino - SYNC信号の送受信デバッグ用
// 送信側: GPIO25で一定周期のSYNCパルスを出し続ける
// 受信側: GPIO26でエッジ検出とレベル読みをし、シリアルに時刻とカウントを出力
// 両方このスケッチで動く（TX用・RX用で役割をスイッチ）。

#include <Arduino.h>

// ==== 設定 ====
// 送信周期 [ms]（SYNC HIGHパルス間隔）
static const uint32_t SYNC_INTERVAL_MS = 1000;  // 1秒ごと
// HIGHパルスの幅 [ms]
static const uint32_t SYNC_PULSE_WIDTH_MS = 100; // 100ms High
// ロール: trueなら送信器、falseなら受信器
static const bool ROLE_SENDER = true; // 送信側にする場合はtrue、受信側にする場合はfalse

// ピン割り当て
static const int SYNC_OUT_PIN = 25;
static const int SYNC_IN_PIN  = 26;

// ==== 送信側用 ====
uint32_t nextPulseMs = 0;
bool pulseActive = false;

// ==== 受信側用 ====
volatile bool syncEdge = false;
volatile bool syncLvl = false;
volatile uint32_t edgeCount = 0;

void IRAM_ATTR onSync(){
  bool s = digitalRead(SYNC_IN_PIN);
  syncLvl = s;
  syncEdge = true;
  edgeCount++;
}

void setup(){
  Serial.begin(115200);
  if (ROLE_SENDER){
    pinMode(SYNC_OUT_PIN, OUTPUT);
    digitalWrite(SYNC_OUT_PIN, LOW);
    nextPulseMs = millis() + 1000; // 1秒後に最初のパルス
    Serial.println("[SENDER] SYNC pulse generator ready");
  } else {
    pinMode(SYNC_IN_PIN, INPUT_PULLDOWN);
    attachInterrupt(digitalPinToInterrupt(SYNC_IN_PIN), onSync, CHANGE);
    Serial.println("[RECEIVER] SYNC edge monitor ready");
  }
}

void loop(){
  if (ROLE_SENDER){
    uint32_t now = millis();
    if (!pulseActive && (int32_t)(now - nextPulseMs) >= 0){
      // パルス開始
      digitalWrite(SYNC_OUT_PIN, HIGH);
      pulseActive = true;
      nextPulseMs = now + SYNC_INTERVAL_MS;
    }
    if (pulseActive && (millis() - (nextPulseMs - SYNC_INTERVAL_MS)) >= SYNC_PULSE_WIDTH_MS){
      // パルス終了
      digitalWrite(SYNC_OUT_PIN, LOW);
      pulseActive = false;
    }
    vTaskDelay(1);
  } else {
    // 受信側: 1秒ごとに状態を出力
    static uint32_t lastPrint = 0;
    uint32_t now = millis();
    if (now - lastPrint >= 1000){
      noInterrupts();
      uint32_t edges = edgeCount;
      bool lvl = syncLvl;
      syncEdge = false;
      interrupts();
      Serial.printf("[RECV] t=%lums, level=%d, edges=%lu\n", (unsigned long)now, (int)lvl, (unsigned long)edges);
      lastPrint = now;
    }
    vTaskDelay(1);
  }
}
