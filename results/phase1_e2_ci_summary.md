# Phase1 E2 CI Summary

Bootstrap: n_boot=20000, seed=20260123

## Pairwise differences (CCS - baseline)

| Pair | Metric | N(CCS) | N(Base) | Mean CCS | Mean Base | Delta (CCS-Base) | 95% CI | Effect Size (Hedges g) | Unit | Notes | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | --- | --- |
| CCS vs FIXED100 | Avg Current | 5 | 3 | 90.12 | 96.93 | -6.80 | [-7.80, -5.94] | -8.12 | mA | reference | results/phase1_e2_ccs_2026-01-22_v03.md;results/phase1_e2_baseline_2026-01-22_v01.md;results/phase1_e2_ccs_2026-01-22_v03_input;results/phase1_e2_baseline_2026-01-22_v01_input;data/esp32_sessions/session_manifest.json;scripts/analyze_ccs_experiment.py |
| CCS vs FIXED100 | Pout(2s) | 5 | 3 | 10.77 | 0.00 | 10.77 | [3.08, 21.54] | 0.98 | pp | reference | results/phase1_e2_ccs_2026-01-22_v03.md;results/phase1_e2_baseline_2026-01-22_v01.md;results/phase1_e2_ccs_2026-01-22_v03_input;results/phase1_e2_baseline_2026-01-22_v01_input;data/esp32_sessions/session_manifest.json;scripts/analyze_ccs_experiment.py |
| CCS vs FIXED100 | TL p95 | 5 | 3 | 4116.6 | 251.7 | 3864.9 | [2043.3, 5829.5] | 1.66 | ms | reference | results/phase1_e2_ccs_2026-01-22_v03.md;results/phase1_e2_baseline_2026-01-22_v01.md;results/phase1_e2_ccs_2026-01-22_v03_input;results/phase1_e2_baseline_2026-01-22_v01_input;data/esp32_sessions/session_manifest.json;scripts/analyze_ccs_experiment.py |
| CCS vs FIXED2000 | Avg Current | 5 | 3 | 90.12 | 87.78 | 2.35 | [-0.75, 4.33] | 1.21 | mA | reference | results/phase1_e2_ccs_2026-01-22_v03.md;results/phase1_e2_baseline_2026-01-22_v01.md;results/phase1_e2_ccs_2026-01-22_v03_input;results/phase1_e2_baseline_2026-01-22_v01_input;data/esp32_sessions/session_manifest.json;scripts/analyze_ccs_experiment.py |
| CCS vs FIXED2000 | Pout(2s) | 5 | 3 | 10.77 | 11.11 | -0.34 | [-8.03, 10.43] | -0.03 | pp | reference | results/phase1_e2_ccs_2026-01-22_v03.md;results/phase1_e2_baseline_2026-01-22_v01.md;results/phase1_e2_ccs_2026-01-22_v03_input;results/phase1_e2_baseline_2026-01-22_v01_input;data/esp32_sessions/session_manifest.json;scripts/analyze_ccs_experiment.py |
| CCS vs FIXED2000 | TL p95 | 5 | 3 | 4116.6 | 3689.3 | 427.3 | [-1669.5, 2697.7] | 0.17 | ms | reference | results/phase1_e2_ccs_2026-01-22_v03.md;results/phase1_e2_baseline_2026-01-22_v01.md;results/phase1_e2_ccs_2026-01-22_v03_input;results/phase1_e2_baseline_2026-01-22_v01_input;data/esp32_sessions/session_manifest.json;scripts/analyze_ccs_experiment.py |

## Source notes
- Avg Current/TL p95 per-trial values align with results/phase1_e2_ccs_2026-01-22_v03.md and results/phase1_e2_baseline_2026-01-22_v01.md.
- Pout(2s) per-trial values derived from RX logs in results/phase1_e2_ccs_2026-01-22_v03_input and results/phase1_e2_baseline_2026-01-22_v01_input using scripts/analyze_ccs_experiment.py with data/esp32_sessions/session_manifest.json.
- Metric definition: docs/metrics_definition.md.

## Caveats
- Small N (CCS n=5, FIXED100 n=3, FIXED2000 n=3). Treat as reference values.
- Pout(2s) per-trial values are derived from RX logs via scripts/analyze_ccs_experiment.py; see sources above.
