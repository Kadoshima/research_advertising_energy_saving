// === PowerLogger_UART_to_SD_SYNC_TICK_B_ON.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// 機能：TX(②)からの UART 受信(v,i,p)を SD に保存。SYNCで試行開始/終了。
//       TICKが配線されていれば N をパルスカウント、無ければ t/100ms で近似。
//       E_total は V×I の数値積分（mJ）。
//
// 配線：UART RX=34 ← ② TX=4（クロス）
//      SYNC_IN=26 ← ② SYNC_OUT=25
//      TICK_IN=33 ← ② TICK_OUT=27（任意）
//      SD: CS=5, SCK=18, MISO=19, MOSI=23
//
// 出力：/logs/trial_XXX_on.csv
//   ms,voltage,current,power
//   # summary, ms_total=..., adv_count=..., E_total_mJ=..., E_per_adv_uJ=...

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>

HardwareSerial uart1(1);

// パススルー設定（受信→SD を最短経路へ）
#define PASS_THRU_ONLY 1         // 数値パース/積分を止め、受信行をそのままSDへ
#define RXBUF_SIZE   16384       // UART受信バッファ拡張
#define SD_CHUNK      8192       // まとめ書きの塊サイズ（バイト）
static uint8_t sdBuf[SD_CHUNK];  // SDチャンクバッファ
static size_t  sdLen = 0;        // バッファ内有効バイト数

static const int RX_PIN  = 34;
static const int SD_CS   = 5;
static const int SYNC_IN = 26;
static const int TICK_IN = 33;

static const bool     USE_TICK_INPUT = true;    // TICK配線ありで厳密カウント
static const uint32_t TRIAL_MS       = 60000;   // 60s

File f;
volatile bool     syncLvl=false, syncEdge=false;
volatile uint32_t advCountISR=0;

bool     logging=false;
uint32_t t0_ms=0, tPrev=0, lineN=0;
double   E_mJ=0.0;              // パススルーでは未使用（0のまま）
String   lineBuf;
// Diagnostics（パースをせずに取得できる範囲のみ）
double sumDt=0.0, sumDt2=0.0;   // ms
uint32_t dtMin=0xFFFFFFFF, dtMax=0;
uint32_t badLines=0;            // PASS_THRU_ONLY では通常 0 のまま

void IRAM_ATTR onSync(){
  bool s = digitalRead(SYNC_IN);
  if (s != syncLvl) { syncLvl = s; syncEdge = true; }
}
void IRAM_ATTR onTick(){ if (logging && USE_TICK_INPUT) advCountISR++; }

String nextPath(){
  SD.mkdir("/logs");
  char p[64];
  for (uint32_t id=1;;++id){
    snprintf(p,sizeof(p),"/logs/trial_%03lu_on.csv",(unsigned long)id);
    if (!SD.exists(p)) return String(p);
  }
}

void startTrial(){
  String path = nextPath();
  f = SD.open(path, FILE_WRITE);
  if (!f) { Serial.println("[SD] open FAIL"); return; }
  f.println("ms,raw_payload");
  logging = true;
  t0_ms = millis(); tPrev = t0_ms; E_mJ = 0.0; lineN = 0; advCountISR = 0; sdLen = 0;
  Serial.printf("[PWR] start %s\n", path.c_str());
}

void endTrial(){
  if (!logging) return;
  logging = false;
  uint32_t t_ms = millis() - t0_ms;
  uint32_t N = USE_TICK_INPUT ? advCountISR : (uint32_t)((t_ms / 100.0) + 0.5);
  // 未書き出しバッファをドレイン
  if (sdLen) { f.write(sdBuf, sdLen); sdLen = 0; }
  // パススルー中は E_total は現場では算出しない（0のまま）
  double Eper_uJ = (N > 0) ? (E_mJ * 1000.0 / N) : 0.0;
  f.printf("# summary, ms_total=%lu, adv_count=%lu, E_total_mJ=%.3f, E_per_adv_uJ=%.1f\r\n",
           (unsigned long)t_ms, (unsigned long)N, E_mJ, Eper_uJ);
  // 簡易診断: 受信行数と実効サンプリングレート、dt統計
  double samples = (double)lineN;
  double dur_s = t_ms / 1000.0;
  double rate_hz = (dur_s>0)? (samples / dur_s) : 0.0;
  double meanDt = (samples>0)? (sumDt / samples) : 0.0;
  double varDt = (samples>0)? (sumDt2 / samples) - (meanDt*meanDt) : 0.0;
  double stdDt = (varDt>0)? sqrt(varDt) : 0.0;
  f.printf("# diag, samples=%lu, rate_hz=%.2f\r\n",
           (unsigned long)lineN, rate_hz);
  f.printf("# diag, dt_ms_mean=%.3f, dt_ms_std=%.3f, dt_ms_min=%lu, dt_ms_max=%lu, parse_drop=%lu\r\n",
           meanDt, stdDt, (unsigned long)(dtMin==0xFFFFFFFF?0:dtMin), (unsigned long)dtMax, (unsigned long)badLines);
  f.flush(); f.close();
  Serial.printf("[PWR] end t=%lums N=%lu E=%.3fmJ E/adv=%.1f uJ\n",
                (unsigned long)t_ms, (unsigned long)N, E_mJ, Eper_uJ);
}

void setup(){
  Serial.begin(115200);

  // SD
  SPI.begin(18,19,23,SD_CS);
  if (!SD.begin(SD_CS)) { Serial.println("[SD] init FAIL"); while(1) delay(1000); }

  // UART
  uart1.begin(230400, SERIAL_8N1, RX_PIN, -1);
#if defined(ARDUINO_ARCH_ESP32)
  uart1.setRxBufferSize(RXBUF_SIZE);
#endif

  // SYNC/TICK
  pinMode(SYNC_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(SYNC_IN), onSync, CHANGE);
  if (USE_TICK_INPUT) {
    pinMode(TICK_IN, INPUT_PULLDOWN);
    attachInterrupt(digitalPinToInterrupt(TICK_IN), onTick, RISING);
  }

  syncLvl = digitalRead(SYNC_IN);
  if (syncLvl) startTrial(); // すでにHighなら即開始
}

void loop(){
  // SYNC立上りで開始（下降は無視）
  if (syncEdge){
    noInterrupts(); bool s=syncLvl; syncEdge=false; interrupts();
    if (s && !logging) startTrial();
  }

  // 固定窓で自動終了
  if (logging && (millis() - t0_ms >= TRIAL_MS)){
    endTrial();
  }

  // UART受信→SD保存（パススルー）
  while (uart1.available()){
    char c = uart1.read();
    if (c == '\n'){
      if (logging && f){
        uint32_t tNow = millis();
        // dt統計のみ計測
        uint32_t dt   = tNow - tPrev; tPrev = tNow;
        sumDt += dt; sumDt2 += (double)dt * (double)dt;
        if (dt < dtMin) dtMin = dt;
        if (dt > dtMax) dtMax = dt;

#if PASS_THRU_ONLY
        // 受信行をそのままSDへ（先頭に相対時刻msを付与）
        uint32_t tRel = tNow - t0_ms;
        char tbuf[16];
        int n = snprintf(tbuf, sizeof(tbuf), "%lu,", (unsigned long)tRel);
        if (sdLen + n + lineBuf.length() + 2 > SD_CHUNK) { f.write(sdBuf, sdLen); sdLen = 0; }
        memcpy(sdBuf + sdLen, tbuf, n);                 sdLen += n;
        memcpy(sdBuf + sdLen, lineBuf.c_str(), lineBuf.length()); sdLen += lineBuf.length();
        sdBuf[sdLen++] = '\r'; sdBuf[sdLen++] = '\n';
        lineN++;
        if (sdLen >= SD_CHUNK) { f.write(sdBuf, sdLen); sdLen = 0; }
#else
        // 既存の数値パース＋積分（停止中）
#endif
      }
      lineBuf = "";
    } else if (c != '\r'){
      lineBuf += c;
    }
  }
}
