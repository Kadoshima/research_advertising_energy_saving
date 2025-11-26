// Auto-generated HAR model configuration for ESP32 - Phase 1 Optimized
// Generated from best_model.pth (fold2)
// Updated with Phase 1 recommended thresholds based on CCS distribution analysis

#ifndef HAR_CONFIG_H
#define HAR_CONFIG_H

// Model architecture
#define HAR_INPUT_LENGTH 100
#define HAR_INPUT_CHANNELS 3
#define HAR_N_CLASSES 12
#define HAR_UNKNOWN_CLASS_ID 12

// Calibration parameters (from recalibration)
#define HAR_TEMPERATURE 0.7320f
#define HAR_TAU_UNKNOWN 0.5800f

// U/S/CCS parameters
#define CCS_ALPHA 0.6f  // U weight
#define CCS_BETA 0.4f   // (1-S) weight

// *** PHASE 1 RECOMMENDED THRESHOLDS ***
// Original (0.40, 0.70) resulted in 0% ACTIVE usage
// Updated based on CCS distribution analysis (median=0.010, mean=0.102)
#define CCS_THETA_LOW 0.15f   // Lowered from 0.40
#define CCS_THETA_HIGH 0.35f  // Lowered from 0.70

#define CCS_WINDOW_SIZE 10

// *** PHASE 1 RECOMMENDED DWELL TIME ***
// Original 2000ms eliminated all ACTIVE states due to transient spikes
// Options:
// - 1000ms: Faster response, moderate switching cost
// - 500ms: Very responsive, higher switching cost
// - 0ms (disabled): Maximum reactivity, measure switching cost in experiments
#define CCS_MIN_DWELL_MS 1000  // Reduced from 2000

// BLE advertising intervals (ms)
#define BLE_INTERVAL_QUIET 2000   // CCS < theta_low
#define BLE_INTERVAL_UNCERTAIN 500  // theta_low <= CCS < theta_high
#define BLE_INTERVAL_ACTIVE 100   // CCS >= theta_high
#define BLE_INTERVAL_FALLBACK 1000  // Error state

// Expected state distribution with Phase 1 thresholds (fold2, no dwell filter):
// - QUIET: ~75%
// - UNCERTAIN: ~13%
// - ACTIVE: ~12%
//
// With 1s dwell filter:
// - QUIET: ~65-70%
// - UNCERTAIN: ~20-25%
// - ACTIVE: ~5-10%

// Class names (12-class internal)
static const char* HAR_CLASS_NAMES[13] = {
    "Standing",   // 0
    "Sitting",    // 1
    "Lying",      // 2
    "Walking",    // 3
    "Stairs",     // 4
    "Bends",      // 5
    "Arms",       // 6
    "Crouch",     // 7
    "Cycling",    // 8
    "Jogging",    // 9
    "Running",    // 10
    "Jump",       // 11
    "Unknown"     // 12
};

// 4-class operational mapping
// Returns: 0=Locomotion, 1=Transition, 2=Stationary, 3=Unknown
static inline int map_to_4class(int class_12) {
    if (class_12 == 12) return 3;  // Unknown
    if (class_12 == 3 || class_12 == 8 || class_12 == 9 || class_12 == 10) return 0;  // Locomotion
    if (class_12 == 4 || class_12 == 5 || class_12 == 6 || class_12 == 7 || class_12 == 11) return 1;  // Transition
    if (class_12 == 0 || class_12 == 1 || class_12 == 2) return 2;  // Stationary
    return 3;  // Fallback to Unknown
}

#endif // HAR_CONFIG_H
