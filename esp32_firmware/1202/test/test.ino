// test.ino - SYNC/TICK疎通テスト
// ROLE_SENDER: GPIO27で1HzのTICKパルスを出力（幅100ms）
// ROLE_RECEIVER: GPIO33でTICKを受信し、割込みカウントとレベルを1秒ごとに出力
// GPIO25/26のSYNCも簡易的にトグルしてテスト可能（オプション）

#include <Arduino.h>

// ==== 設定 ====
static const bool ROLE_SENDER = false; // trueで送信、falseで受信
static const uint32_t TICK_INTERVAL_MS = 1000; // 1Hz
static const uint32_t TICK_PULSE_MS    = 100;  // パルス幅100ms

// ピン割り当て
static const int TICK_OUT_PIN = 27;
static const int TICK_IN_PIN  = 33;
static const int SYNC_OUT_PIN = 25;
static const int SYNC_IN_PIN  = 26;

// 送信側
uint32_t nextTickMs = 0; bool tickActive=false;
uint32_t nextSyncMs = 0; bool syncState=false;

// 受信側
volatile uint32_t tickCount=0; volatile uint32_t syncCount=0;
volatile bool tickLevel=false; volatile bool syncLevel=false;

void IRAM_ATTR onTick(){ tickCount++; tickLevel = digitalRead(TICK_IN_PIN); }
void IRAM_ATTR onSync(){ syncCount++; syncLevel = digitalRead(SYNC_IN_PIN); }

void setup(){
  Serial.begin(115200);
  if (ROLE_SENDER){
    pinMode(TICK_OUT_PIN, OUTPUT); digitalWrite(TICK_OUT_PIN, LOW);
    pinMode(SYNC_OUT_PIN, OUTPUT); digitalWrite(SYNC_OUT_PIN, LOW);
    nextTickMs = millis() + 1000;
    nextSyncMs = millis() + 2000; // 2秒ごとにトグルしてみる
    Serial.println("[SENDER] Tick/SYNC pulse generator ready");
  } else {
    pinMode(TICK_IN_PIN, INPUT_PULLDOWN);
    pinMode(SYNC_IN_PIN, INPUT_PULLDOWN);
    attachInterrupt(digitalPinToInterrupt(TICK_IN_PIN), onTick, CHANGE);
    attachInterrupt(digitalPinToInterrupt(SYNC_IN_PIN), onSync, CHANGE);
    Serial.println("[RECEIVER] Tick/SYNC monitor ready");
  }
}

void loop(){
  if (ROLE_SENDER){
    uint32_t now = millis();
    // TICK発生
    if (!tickActive && (int32_t)(now - nextTickMs) >= 0){
      digitalWrite(TICK_OUT_PIN, HIGH);
      tickActive = true;
      nextTickMs = now + TICK_INTERVAL_MS;
    }
    if (tickActive && (millis() - (nextTickMs - TICK_INTERVAL_MS)) >= TICK_PULSE_MS){
      digitalWrite(TICK_OUT_PIN, LOW);
      tickActive = false;
    }
    // SYNCトグル（オプション）
    if ((int32_t)(now - nextSyncMs) >= 0){
      syncState = !syncState;
      digitalWrite(SYNC_OUT_PIN, syncState ? HIGH : LOW);
      nextSyncMs = now + 2000; // 2秒周期
    }
    vTaskDelay(1);
  } else {
    static uint32_t lastPrint=0; uint32_t now=millis();
    if (now - lastPrint >= 1000){
      noInterrupts();
      uint32_t tc=tickCount, sc=syncCount; bool tl=tickLevel, sl=syncLevel;
      tickCount=0; syncCount=0; // 1秒ごとに差分を表示
      interrupts();
      Serial.printf("[RECV] t=%lums, tick=%lu (lvl=%d), sync=%lu (lvl=%d)\n",
                    (unsigned long)now, (unsigned long)tc, (int)tl, (unsigned long)sc, (int)sl);
      lastPrint = now;
    }
    vTaskDelay(1);
  }
}
