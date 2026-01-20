#ifndef DBG_LEVEL
#define DBG_LEVEL 3
#endif

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.printf("[AGENT] RX_DIAG_PING boot dbg_level=%d\n", (int)DBG_LEVEL);
}

void loop() {
  static uint32_t lastMs = 0;
  uint32_t nowMs = millis();
  if (nowMs - lastMs >= 1000) {
    Serial.printf("[AGENT] RX_DIAG_PING nowMs=%lu\n", (unsigned long)nowMs);
    lastMs = nowMs;
  }
}
