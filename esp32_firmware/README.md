# ESP32 Firmware for BLE Advertising Energy Measurement

3-node ESP32 system for BLE advertising power measurement.

## Directory Structure

```
esp32_firmware/
├── baseline_on/      # ON measurement (BLE advertising enabled)
│   ├── TX_BLE_Adv.ino         # Node 1: BLE TX + INA219
│   ├── TXSD_PowerLogger.ino   # Node 2: Power logger (SD)
│   └── RX_BLE_to_SD.ino       # Node 3: BLE RX logger (SD)
├── baseline_off/     # OFF measurement (BLE disabled, baseline power)
│   ├── TX_BLE_OFF.ino         # Node 1: No BLE, INA219 only
│   └── TXSD_PowerLogger.ino   # Node 2: Power logger (SD)
├── ccs_mode/         # CCS dynamic interval control
│   ├── TX_BLE_Adv_CCS_Mode.ino
│   ├── TXSD_PowerLogger_CCS_Mode.ino
│   ├── RX_BLE_to_SD.ino
│   └── ccs_session_data.h     # Generated session data
└── README.md
```

## Node Configuration

| Node | Role | Key Pins |
|------|------|----------|
| Node 1 (TX) | BLE Advertiser + INA219 | SYNC_OUT=25, TICK_OUT=27, UART_TX=4, I2C=21/22 |
| Node 2 (TXSD) | Power Logger | SYNC_IN=26, TICK_IN=33, UART_RX=34, SD_CS=5 |
| Node 3 (RX) | BLE Receiver | SYNC_IN=26, SD_CS=5 |

## Wiring

```
Node1 (TX)          Node2 (TXSD)        Node3 (RX)
  SYNC_OUT=25 ───────► SYNC_IN=26 ────────► SYNC_IN=26
  TICK_OUT=27 ───────► TICK_IN=33
  UART_TX=4   ───────► UART_RX=34

  INA219 (I2C)
    SDA=21
    SCL=22
```

## Usage

### Baseline ON Measurement (100ms interval)
1. Flash `baseline_on/TX_BLE_Adv.ino` to Node 1
2. Flash `baseline_on/TXSD_PowerLogger.ino` to Node 2
3. (Optional) Flash `baseline_on/RX_BLE_to_SD.ino` to Node 3 for PDR
4. Power on all nodes, measurement starts automatically

### Baseline OFF Measurement (P_off)
1. Flash `baseline_off/TX_BLE_OFF.ino` to Node 1
2. Flash `baseline_off/TXSD_PowerLogger.ino` to Node 2
3. Power on, 60s fixed-window measurement starts

### CCS Mode (Dynamic Interval)
1. Generate `ccs_session_data.h` using `scripts/convert_session_to_header.py`
2. Flash `ccs_mode/TX_BLE_Adv_CCS_Mode.ino` to Node 1
3. Flash `ccs_mode/TXSD_PowerLogger_CCS_Mode.ino` to Node 2
4. Flash `ccs_mode/RX_BLE_to_SD.ino` to Node 3

## Key Parameters

| Parameter | ON | OFF | CCS |
|-----------|-----|-----|-----|
| ADV_INTERVAL_MS | 100/500/1000/2000 | N/A | Dynamic |
| N_ADV_PER_TRIAL | 300 | N/A | Session-based |
| TRIAL_MS | Auto | 60000 | Auto |
| USE_TICK_INPUT | 1 | 0 | 1 |

## Output Files

- `trial_XXX_on.csv` - ON power data
- `trial_XXX_off.csv` - OFF power data
- `rx_trial_XXX.csv` - RX reception log

## Delta Energy Calculation

```
ΔE/adv = (E_total_ON - P_off × T) / N_adv
```

Where:
- E_total_ON: Total energy from ON measurement
- P_off: Baseline power from OFF measurement (mW)
- T: Measurement duration (s)
- N_adv: Number of advertisements (from TICK count)
