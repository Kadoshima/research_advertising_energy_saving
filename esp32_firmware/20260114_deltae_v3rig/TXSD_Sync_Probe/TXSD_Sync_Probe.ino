void setup() {
  Serial.begin(115200);
  delay(200);
  pinMode(25, INPUT_PULLDOWN);
  pinMode(26, INPUT_PULLDOWN);
  pinMode(27, INPUT_PULLDOWN);
  pinMode(32, INPUT_PULLDOWN);
  pinMode(33, INPUT_PULLDOWN);
  Serial.println("[AGENT] TXSD_SYNC_PROBE boot");
}

void loop() {
  static uint32_t lastMs = 0;
  uint32_t nowMs = millis();
  if (nowMs - lastMs >= 1000) {
    int p25 = digitalRead(25);
    int p26 = digitalRead(26);
    int p27 = digitalRead(27);
    int p32 = digitalRead(32);
    int p33 = digitalRead(33);
    Serial.printf("[AGENT] TXSD_SYNC_PROBE nowMs=%lu pin25=%d pin26=%d pin27=%d pin32=%d pin33=%d\n",
                  (unsigned long)nowMs, p25, p26, p27, p32, p33);
    lastMs = nowMs;
  }
}
