#line 1 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_SYNC_Pulse_Test\\TX_SYNC_Pulse_Test.ino"
// TX_SYNC_PULSE_TEST.ino
// Generates START/END pulses on GPIO26/25 for wiring verification.

#include <Arduino.h>

static const int START_PIN = 26;
static const int END_PIN = 25;
static const uint32_t START_PERIOD_MS = 2000;
static const uint32_t END_DELAY_MS = 500;
static const uint32_t PULSE_MS = 50;

uint32_t nextStartMs = 0;
bool endPending = false;
uint32_t endAtMs = 0;

#line 16 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_SYNC_Pulse_Test\\TX_SYNC_Pulse_Test.ino"
void setup();
#line 26 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_SYNC_Pulse_Test\\TX_SYNC_Pulse_Test.ino"
void loop();
#line 16 "C:\\Users\\tp240\\Documents\\Arduino_MCP_Sketches\\TX_SYNC_Pulse_Test\\TX_SYNC_Pulse_Test.ino"
void setup() {
  Serial.begin(115200);
  pinMode(START_PIN, OUTPUT);
  pinMode(END_PIN, OUTPUT);
  digitalWrite(START_PIN, LOW);
  digitalWrite(END_PIN, LOW);
  nextStartMs = millis() + 1000;
  Serial.println("[TX_TEST] SYNC pulse test ready");
}

void loop() {
  uint32_t now = millis();

  if (!endPending && (int32_t)(now - nextStartMs) >= 0) {
    digitalWrite(START_PIN, HIGH);
    delay(PULSE_MS);
    digitalWrite(START_PIN, LOW);
    Serial.printf("[TX_TEST] START pulse t=%lu\n", (unsigned long)now);

    endPending = true;
    endAtMs = now + END_DELAY_MS;
    nextStartMs = now + START_PERIOD_MS;
  }

  if (endPending && (int32_t)(now - endAtMs) >= 0) {
    digitalWrite(END_PIN, HIGH);
    delay(PULSE_MS);
    digitalWrite(END_PIN, LOW);
    Serial.printf("[TX_TEST] END pulse t=%lu\n", (unsigned long)now);
    endPending = false;
  }

  delay(1);
}

