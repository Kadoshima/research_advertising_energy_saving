# uccs_d1_scan90 metrics (01)

## Input

- RX: `/Users/kadoshima/Documents/research_advertising-energy_saving/uccs_d1_scan90/data/01/RX`
- TXSD: `/Users/kadoshima/Documents/research_advertising-energy_saving/uccs_d1_scan90/data/01/TX`
- Filter: `ms_total >= 50000`

## Power (TXSD)

| tag | n | mean_p_mW | std_p_mW |
| --- | ---: | ---: | ---: |
| fixed100 | 3 | 205.10 | 2.79 |
| fixed500 | 3 | 185.50 | 0.98 |
| policy | 3 | 192.17 | 0.55 |

- ΔP (fixed100 - fixed500) = **19.60 mW**
- ΔP (policy - fixed100) = **-12.93 mW**
- ΔP (policy - fixed500) = **6.67 mW**
- share100 (time-weight, from power mix) ≈ **0.340**

## RX rate

| condition_label | n | rate_hz_mean | rate_hz_std |
| --- | ---: | ---: | ---: |
| F100 | 3 | 7.94 | 0.21 |
| F500 | 3 | 1.63 | 0.09 |
| P500 | 3 | 3.71 | 0.11 |

## Policy mix (from RX labels)

- Policy RX files are labeled `P100`/`P500` (current interval).
- share100 (time-weight, from RX counts) ≈ **0.294 ± 0.010**

