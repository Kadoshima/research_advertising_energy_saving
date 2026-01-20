# 1210_ble_rx_rules

## purpose_scope
- Define baseline RX/TX/TXSD implementation rules derived from the 1210 series.
- Apply the same scan policy to deltae v3rig sweep and related experiments.

## input_data
- source: 1210 reference firmware (paths below)
- version: repo snapshot (no tag)
- rows: n/a (code only)
- sha256: n/a (code only)

## outputs
- generated_at: 2026-01-19
- generated_by: manual curation
- script: n/a

## reproduction_steps
- `arduino-cli compile --fqbn esp32:esp32:esp32wroverkit <sketch_dir>`
- `arduino-cli upload --fqbn esp32:esp32:esp32wroverkit -p COMx <sketch_dir>`

## status
- draft

## rules
- RX must use NimBLE passive scan: active_scan=false, scan_interval_ms=100, scan_window_ms=90, dup_filter=false.
- RX must allow duplicates (NimBLE setScanCallbacks(..., true)).
- RX must gate logging by SYNC with debounce and keep a fallback timeout.
- RX must log program_id in each CSV row and record scan parameters in the meta line.
- TX must refresh advertisement payload each interval and call adv->start() after setAdvertisementData.
- TX must emit SYNC high during the trial and TICK pulse per advertisement.
- TXSD must count tick_raw on GPIO33 RISING and report adv_count; if adv_count=0, treat wiring as primary suspect.

## references
- `esp32_firmware/1210/modeC2prime_rx/RX_ModeC2prime_1210/RX_ModeC2prime_1210.ino`
- `esp32_firmware/1210/modeC2prime_tx/TX_ModeC2prime_1210.ino`
- `esp32_firmware/1210/modeC2prime_txsd/TXSD_ModeC2prime_1210/TXSD_ModeC2prime_1210.ino`
- `esp32_firmware/20260115_deltae_v3rig_sweep/RX_DeltaE_Sweep/RX_DeltaE_Sweep.ino`
- `esp32_firmware/20260115_deltae_v3rig_sweep/TX_DeltaE_Sweep/TX_DeltaE_Sweep.ino`
- `esp32_firmware/20260115_deltae_v3rig_sweep/TXSD_DeltaE_Sweep/TXSD_DeltaE_Sweep.ino`

## update_history
- 2026-01-19: initial rules extracted from 1210 baseline.
