static const int SYNC_OUT_PIN = 26;

void setup() {
  Serial.begin(115200);
  delay(200);
  pinMode(SYNC_OUT_PIN, OUTPUT);
  digitalWrite(SYNC_OUT_PIN, LOW);
  Serial.printf("[AGENT] TX_SYNC_TOGGLE boot pin=%d\n", SYNC_OUT_PIN);
}

void loop() {
  static uint32_t lastMs = 0;
  static bool level = false;
  uint32_t nowMs = millis();
  if (nowMs - lastMs >= 500) {
    level = !level;
    digitalWrite(SYNC_OUT_PIN, level ? HIGH : LOW);
    Serial.printf("[AGENT] TX_SYNC_TOGGLE nowMs=%lu level=%d\n",
                  (unsigned long)nowMs, level ? 1 : 0);
    lastMs = nowMs;
  }
}
