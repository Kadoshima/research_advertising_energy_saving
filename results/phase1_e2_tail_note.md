# Phase1 E2 CCS Tail Note

## CCS trials ranked by Pout(2s) (desc)

| Rank | Trial | Pout(2s) % | TL p95 (ms) | Avg Current (mA) |
| ---: | --- | ---: | ---: | ---: |
| 1 | 02632641_48e55466_sweep | 30.77 | 5589 | 89.63 |
| 2 | 03842746_23f87c31_sweep | 7.69 | 7590 | 89.42 |
| 3 | 02027588_eac2cafb_sweep | 7.69 | 3576 | 90.77 |
| 4 | 01413883_94c2b81c_sweep | 7.69 | 2233 | 89.98 |
| 5 | 03237693_f58d6dac_sweep | 0.00 | 1595 | 90.82 |

## CCS trials ranked by TL p95 (desc)

| Rank | Trial | TL p95 (ms) | Pout(2s) % | Avg Current (mA) |
| ---: | --- | ---: | ---: | ---: |
| 1 | 03842746_23f87c31_sweep | 7590 | 7.69 | 89.42 |
| 2 | 02632641_48e55466_sweep | 5589 | 30.77 | 89.63 |
| 3 | 02027588_eac2cafb_sweep | 3576 | 7.69 | 90.77 |
| 4 | 01413883_94c2b81c_sweep | 2233 | 7.69 | 89.98 |
| 5 | 03237693_f58d6dac_sweep | 1595 | 0.00 | 90.82 |

## Tail note
- Highest Pout(2s) trial: 02632641_48e55466_sweep (Pout(2s)=30.77%, TL p95=5589 ms).
- Highest TL p95 trial: 03842746_23f87c31_sweep (TL p95=7590 ms, Pout(2s)=7.69%).
- Tail sensitivity: a small number of CCS trials sit far above the median on Pout/TL, indicating tail-dominant behavior.

## Sources
- results/phase1_e2_ccs_2026-01-22_v03.md
- results/phase1_e2_ccs_2026-01-22_v03_input
- data/esp32_sessions/session_manifest.json
- scripts/analyze_ccs_experiment.py
- docs/metrics_definition.md
