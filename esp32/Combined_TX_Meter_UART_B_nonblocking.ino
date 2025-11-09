// === Combined_TX_Meter_UART_B_nonblocking.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// 役割：BLEアドバタイズ(100ms) + SYNCパルス + (任意)TICKパルス
//       ＋ INA219で2ms周期計測 → UART(230400bps)で v,i,p をCSV送出（非ブロッキング）
//
// 配線：SYNC_OUT=GPIO25 → PowerLogger(26) & RX Logger(26)
//      TICK_OUT=GPIO27  → PowerLogger(33)   ※任意
//      UART1 TX=GPIO4   → PowerLogger RX=GPIO34（クロス）
//      I2C SDA=21/SCL=22→ INA219（VCCは3.3V_B推奨）
// 電源：このボード(②)は PMM25の 3.3V_A（測定対象）。GNDは全台共通。
//      INA219のVCCは 3.3V_B（ロガ電源側）。VIN+→シャント→VIN−→ESP32(②)3V3。

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <BLEDevice.h>

// ===== ユーザ設定 =====
static const uint16_t ADV_INTERVAL_MS = 100;     // アドバタイズ間隔（固定）
static const uint32_t SAMPLE_US       = 2000;    // 計測周期 2ms ≒ 500Hz
static const bool     USE_TICK_OUT    = true;    // TICKパルスを出すか（未配線でも害なし）
static const esp_power_level_t TX_PWR = ESP_PWR_LVL_N0; // 送信出力 0dBm

// ピンアサイン
static const int SYNC_OUT_PIN = 25;  // 100ms High を1回だけ出す
static const int TICK_OUT_PIN = 27;  // 100msごと 200us High（任意）
static const int LED_PIN      = 2;   // オンボードLED
static const int I2C_SDA      = 21;
static const int I2C_SCL      = 22;
static const int UART_TX      = 4;   // UART1 TX → PowerLogger RX=34
static const long UART_BAUD   = 230400;

// ===== グローバル =====
HardwareSerial uart1(1);
Adafruit_INA219 ina;
BLEAdvertising* adv = nullptr;

uint16_t seq  = 0;
uint8_t  hold0 = 8; // SYNC直後に "MF0000" を数フレーム出してソフト同期補助

static inline String makeMFD(uint16_t s) {
  char b[7];
  snprintf(b, sizeof(b), "MF%04X", (unsigned)s); // "MF0000"〜"MFFFFF"
  return String(b);
}

static void syncPulse() {
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(SYNC_OUT_PIN, HIGH);
  delay(100);                         // 100ms High（取りこぼしに強い）
  digitalWrite(SYNC_OUT_PIN, LOW);
  seq   = 0;
  hold0 = 8;
  digitalWrite(LED_PIN, LOW);
}

// タイマ（非ブロッキング）
static uint32_t nextSampleUs;
static uint32_t nextAdvMs;

void setup() {
  // Serial.begin(115200); // デバッグ時のみ

  // GPIO
  pinMode(LED_PIN, OUTPUT);       digitalWrite(LED_PIN, LOW);
  pinMode(SYNC_OUT_PIN, OUTPUT);  digitalWrite(SYNC_OUT_PIN, LOW);
  if (USE_TICK_OUT) { pinMode(TICK_OUT_PIN, OUTPUT); digitalWrite(TICK_OUT_PIN, LOW); }

  // BLE 初期化
  BLEDevice::init("TXM_ESP32");
  BLEDevice::setPower(TX_PWR);
  BLEAdvertising* a = BLEDevice::getAdvertising();
  a->setScanResponse(false);
  a->setMinPreferred(0);
  uint16_t itv = (uint16_t)(ADV_INTERVAL_MS / 0.625f); // 0.625ms単位
  a->setMinInterval(itv);
  a->setMaxInterval(itv);
  BLEAdvertisementData ad;
  ad.setName("TXM_ESP32");
  ad.setManufacturerData(makeMFD(0));
  a->setAdvertisementData(ad);
  a->start();
  adv = a;

  // INA219
  Wire.begin(I2C_SDA, I2C_SCL);
  ina.begin();
  ina.setCalibration_16V_400mA();   // 代表レンジ（必要に応じ変更）

  // UART1（TX専用）
  uart1.begin(UART_BAUD, SERIAL_8N1, -1, UART_TX);

  // 起動2秒後に同期パルス
  delay(2000);
  syncPulse();

  // タイマ開始
  nextSampleUs = micros() + SAMPLE_US;
  nextAdvMs    = millis() + ADV_INTERVAL_MS;
}

void loop() {
  // ---- 2ms周期の計測（追いつき処理あり・非ブロッキング）----
  uint32_t nowUs = micros();
  int guard = 0; // 1ループでの最大サンプル数（暴走防止）
  while ((int32_t)(nowUs - nextSampleUs) >= 0 && guard < 8) {
    nextSampleUs += SAMPLE_US;
    // センサ取得
    float v = ina.getBusVoltage_V();
    float i = ina.getCurrent_mA();   // 向きは配線依存。必要なら i = -i;
    float p = ina.getPower_mW();     // 使わなくても送っておく

    // UARTへCSV吐き（短めのフォーマットで帯域節約）
    uart1.printf("%.3f,%.1f,%.1f\n", v, i, p);

    guard++;
    nowUs = micros();
  }

  // ---- 100msごとのアドバタイズ更新（非ブロッキング）----
  uint32_t nowMs = millis();
  if ((int32_t)(nowMs - nextAdvMs) >= 0) {
    nextAdvMs += ADV_INTERVAL_MS;

    // 送るseq（同期後の一定期間は0を維持）
    uint16_t sendSeq = (hold0 > 0) ? 0 : seq;

    BLEAdvertisementData ad;
    ad.setName("TXM_ESP32");
    ad.setManufacturerData(makeMFD(sendSeq));
    adv->setAdvertisementData(ad);

    if (hold0 > 0) --hold0;
    else           ++seq;

    if (USE_TICK_OUT) {
      digitalWrite(TICK_OUT_PIN, HIGH);
      delayMicroseconds(200);
      digitalWrite(TICK_OUT_PIN, LOW);
    }
  }

  // 他タスクに譲る（WiFi/BLEタスク進行用）
  delay(0);
}

