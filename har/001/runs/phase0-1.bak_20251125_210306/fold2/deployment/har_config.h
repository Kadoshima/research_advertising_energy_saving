// Auto-generated HAR model configuration for ESP32
// Generated from best_model.pth

#ifndef HAR_CONFIG_H
#define HAR_CONFIG_H

// Model architecture
#define HAR_INPUT_LENGTH 100
#define HAR_INPUT_CHANNELS 3
#define HAR_N_CLASSES 12
#define HAR_UNKNOWN_CLASS_ID 12

// Calibration parameters
#define HAR_TEMPERATURE 0.7320f
#define HAR_TAU_UNKNOWN 0.5800f

// U/S/CCS parameters
#define CCS_ALPHA 0.6f  // U weight
#define CCS_BETA 0.4f   // (1-S) weight
#define CCS_THETA_LOW 0.40f
#define CCS_THETA_HIGH 0.70f
#define CCS_WINDOW_SIZE 10
#define CCS_MIN_DWELL_MS 2000

// BLE advertising intervals (ms)
#define BLE_INTERVAL_QUIET 2000   // CCS < theta_low
#define BLE_INTERVAL_UNCERTAIN 500  // theta_low <= CCS < theta_high
#define BLE_INTERVAL_ACTIVE 100   // CCS >= theta_high
#define BLE_INTERVAL_FALLBACK 1000  // Error state

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
