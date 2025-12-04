// Auto-generated labels header (subject01-10)
// 各セッションのラベル系列をフラッシュに持たせて周回再生する。
// 生成元: data/ccs_sequences/subject{01-10}_ccs.csv （ラベル=0/1/2）

#pragma once
#include <stdint.h>

// 各セッションのラベル列（0/1/2）
// 最後に全長 (n) を付けている。
// 例ではデモとして短縮版を手書きしているが、実際は gen_labels_all.py 等で生成する想定。

static const uint8_t labels_01[] = {0,0,1,1,2,2,0,1,2,0};
static const uint16_t nLabels_01 = sizeof(labels_01)/sizeof(labels_01[0]);

static const uint8_t labels_02[] = {0,1,2,0,1,2,0,1,2,0};
static const uint16_t nLabels_02 = sizeof(labels_02)/sizeof(labels_02[0]);

static const uint8_t labels_03[] = {0,0,0,1,1,1,2,2,2,0};
static const uint16_t nLabels_03 = sizeof(labels_03)/sizeof(labels_03[0]);

static const uint8_t labels_04[] = {0,2,1,0,2,1,0,2,1,0};
static const uint16_t nLabels_04 = sizeof(labels_04)/sizeof(labels_04[0]);

static const uint8_t labels_05[] = {2,2,2,1,1,0,0,0,1,2};
static const uint16_t nLabels_05 = sizeof(labels_05)/sizeof(labels_05[0]);

static const uint8_t labels_06[] = {1,1,0,0,2,2,1,1,0,0};
static const uint16_t nLabels_06 = sizeof(labels_06)/sizeof(labels_06[0]);

static const uint8_t labels_07[] = {2,1,0,2,1,0,2,1,0,2};
static const uint16_t nLabels_07 = sizeof(labels_07)/sizeof(labels_07[0]);

static const uint8_t labels_08[] = {0,1,0,1,2,2,1,0,2,1};
static const uint16_t nLabels_08 = sizeof(labels_08)/sizeof(labels_08[0]);

static const uint8_t labels_09[] = {1,0,1,0,2,1,2,0,2,1};
static const uint16_t nLabels_09 = sizeof(labels_09)/sizeof(labels_09[0]);

static const uint8_t labels_10[] = {2,0,2,0,1,1,0,2,1,0};
static const uint16_t nLabels_10 = sizeof(labels_10)/sizeof(labels_10[0]);

struct SessionLabels {
  const char* id;
  const uint8_t* seq;
  uint16_t len;
};

static const SessionLabels SESSIONS[] = {
  {"01", labels_01, nLabels_01},
  {"02", labels_02, nLabels_02},
  {"03", labels_03, nLabels_03},
  {"04", labels_04, nLabels_04},
  {"05", labels_05, nLabels_05},
  {"06", labels_06, nLabels_06},
  {"07", labels_07, nLabels_07},
  {"08", labels_08, nLabels_08},
  {"09", labels_09, nLabels_09},
  {"10", labels_10, nLabels_10},
};

static const uint8_t NUM_SESSIONS = sizeof(SESSIONS)/sizeof(SESSIONS[0]);
