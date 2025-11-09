// === PowerLogger_UART_to_SD_SYNC_TICK_B_OFF.ino ===
// Board: ESP32 Dev Module (Arduino-ESP32 v3.x)
//
// 機能：TX(②)からの UART 受信(v,i,p)を SD に保存。SYNCで試行開始/終了。
//       広告OFFのベースライン計測用：サマリの adv_count は 0 とし、
//       E/adv は 0 を出力（ΔE = E_on − E_off の算出目的）。
//
// 配線：UART RX=34 ← ② TX=4（クロス）
//      SYNC_IN=26 ← ② SYNC_OUT=25
//      SD: CS=5, SCK=18, MISO=19, MOSI=23
//
// 出力：/logs/trial_XXX_off.csv
//   ms,voltage,current,power
//   # summary, ms_total=..., adv_count=0, E_total_mJ=..., E_per_adv_uJ=0.0

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>

HardwareSerial uart1(1);

static const int RX_PIN  = 34;
static const int SD_CS   = 5;
static const int SYNC_IN = 26;

static const uint32_t TRIAL_MS       = 60000;   // 60s

File f;
volatile bool     syncLvl=false, syncEdge=false;

bool     logging=false;
uint32_t t0_ms=0, tPrev=0, lineN=0;
double   E_mJ=0.0;
String   lineBuf;

void IRAM_ATTR onSync(){
  bool s = digitalRead(SYNC_IN);
  if (s != syncLvl) { syncLvl = s; syncEdge = true; }
}

String nextPath(){
  SD.mkdir("/logs");
  char p[64];
  for (uint32_t id=1;;++id){
    snprintf(p,sizeof(p),"/logs/trial_%03lu_off.csv",(unsigned long)id);
    if (!SD.exists(p)) return String(p);
  }
}

void startTrial(){
  String path = nextPath();
  f = SD.open(path, FILE_WRITE);
  if (!f) { Serial.println("[SD] open FAIL"); return; }
  f.println("ms,voltage,current,power");
  logging = true;
  t0_ms = millis(); tPrev = t0_ms; E_mJ = 0.0; lineN = 0;
  Serial.printf("[PWR] start %s (mode=OFF)\n", path.c_str());
}

void endTrial(){
  if (!logging) return;
  logging = false;
  uint32_t t_ms = millis() - t0_ms;
  const uint32_t N = 0; // 広告OFF: adv_countは0
  const double Eper_uJ = 0.0;
  f.printf("# summary, ms_total=%lu, adv_count=%lu, E_total_mJ=%.3f, E_per_adv_uJ=%.1f\r\n",
           (unsigned long)t_ms, (unsigned long)N, E_mJ, Eper_uJ);
  f.flush(); f.close();
  Serial.printf("[PWR] end t=%lums N=%lu E=%.3fmJ (mode=OFF)\n",
                (unsigned long)t_ms, (unsigned long)N, E_mJ);
}

void setup(){
  Serial.begin(115200);

  // SD
  SPI.begin(18,19,23,SD_CS);
  if (!SD.begin(SD_CS)) { Serial.println("[SD] init FAIL"); while(1) delay(1000); }

  // UART
  uart1.begin(230400, SERIAL_8N1, RX_PIN, -1);

  // SYNC
  pinMode(SYNC_IN, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(SYNC_IN), onSync, CHANGE);

  syncLvl = digitalRead(SYNC_IN);
  if (syncLvl) startTrial();
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

  // UART受信→SD保存＆エネルギー積分（V×I）
  while (uart1.available()){
    char c = uart1.read();
    if (c == '\n'){
      if (logging && f){
        uint32_t tNow = millis();
        uint32_t dt   = tNow - tPrev;
        tPrev = tNow;

        double v=0, i=0, p=0;
        sscanf(lineBuf.c_str(), "%lf,%lf,%lf", &v,&i,&p);

        double p_calc_mW = v * i;            // V[Volt] × I[mA] = mW
        E_mJ += p_calc_mW * (dt / 1000.0);

        uint32_t tRel = tNow - t0_ms;
        f.printf("%lu,%.3f,%.1f,%.1f\r\n",
                 (unsigned long)tRel, v, i, p);
        if ((++lineN % 200) == 0) f.flush();
      }
      lineBuf = "";
    } else if (c != '\r'){
      lineBuf += c;
    }
  }
}

