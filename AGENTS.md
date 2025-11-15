# Repository Guidelines

## Project structure & module organization
- `docs/フェーズ1/` contains phase-one deliverables such as `要件定義.md` and `Runbook.md`. Add new phases as `docs/フェーズN/` and mirror folder names inside references.
- `data/` stores curated datasets; log source, version, and SHA256 in the consuming document. Do not commit raw exports without documentation.
- `configs/` tracks reusable parameter sets; align filenames with the related doc slug (e.g., `要件定義_simulation.yaml`).
- `results/` captures derived tables, charts, or summaries. Note generation date and script in the adjacent Markdown file.
- `scripts/` keeps ad-hoc automation; run from the repository root (`python scripts/generate_summary.py`) and document dependencies.
- External experiments or firmware belong in sibling repositories such as `labs/`; leave references here that link outward.

## Build, test, and development commands
- `markdownlint docs` lint headings, lists, and fenced blocks before committing.
- `glow docs/フェーズ1/要件定義.md` preview the rendered Markdown; use any equivalent viewer if Glow is unavailable.
- `git diff` confirm table layout and diagram embeds before pushing.
- Optional: `npx markdown-link-check docs/フェーズ1/要件定義.md` verify external URLs when refreshing references.

## Coding style & naming conventions
- Write concise, declarative Japanese-first prose; introduce English terms in parentheses on first mention.
- Prefer Japanese filenames; when romanizing, use lowercase snake case (`yoken_teigi.md`). Keep new content ASCII unless quoting external text.
- Maintain parallel bullet structures, limit paragraphs to three sentences, and date entries as `YYYY-MM-DD`.
- Document dataset metrics with metric units and cite sources alongside quantitative claims.

## Testing guidelines
- No automated suite exists; manually confirm internal anchors, relative links, and cross-phase references.
- Preview diagrams and tables with a Markdown viewer; reconcile CCS thresholds with `docs/フェーズ1/Runbook.md`.
- When adjusting datasets, validate row counts against expectations and update recorded checksums.

## Commit & pull request guidelines
- Write imperative commit subjects such as `Update 要件定義.md`; keep each commit scoped to a single topic.
- PR descriptions should list affected documents, summarize impact, reference issues, and attach render diffs or screenshots for visual changes.
- Request at least one peer review and wait for required checks before merging.

## Agent-specific instructions
- Add new material to the appropriate phase directory and store supporting assets beside the referencing document with slugged filenames (e.g., `要件定義_図1.png`).
- Avoid introducing new tooling or build systems unless coordinated with maintainers.

## Recent experiment snapshot (Phase 0-0)
- Phase: 0-0 baseline. Conditions: E2 (high interference), distance 1 m, adv_interval=100 ms, TxPower=0 dBm, 60 s × 6 runs.
- Data (ON): `data/実験データ/研究室/1m_ad/` (collected with non-separated ON/OFF code). Directory checksums consolidated in `data/実験データ/SHA256.txt`.
- Data (OFF): `data/実験データ/研究室/1m_off/` (collected with separated OFF code).
- Results summary: `results/フェーズ0-0_E2_1m_100ms_2025-11-09.md`
- RX retry summary: `results/フェーズ0-0_E2_1m_100ms_retry_2025-11-09.md` (RX-only; power logs not present)
- ON retry summary: `results/フェーズ0-0_E2_1m_100ms_retry_latest_2025-11-09.md` (ON power+RX, n=2)
- OFF re-run summary: `results/フェーズ0-0_E2_1m_100ms_off_02_2025-11-09.md` (OFF power, n=2)
  - OFF_03: `results/フェーズ0-0_E2_1m_100ms_off_03_2025-11-09.md` (OFF power, n=2, TX-only)
  - OFF_04: `results/フェーズ0-0_E2_1m_100ms_off_04_2025-11-09.md` (OFF power, n=2, pass-through logger)
- Experiment log: `docs/フェーズ0-0/実験ログ_E2_1m_2025-11-09.md`
- ESP32 sketches
  - RX logger: `esp32/RX_BLE_to_SD_SYNC_B.ino`（旧 `RxLogger_BLE_to_SD_SYNC_B.ino`）
  - TX+INA (advertising ON): `esp32/TX_BLE_Adv_Meter_ON_nonblocking.ino`（旧 `Combined_TX_Meter_UART_B_nonblocking.ino`）
  - TX+INA (advertising OFF, 10 ms baseline): `esp32/TX_BLE_Adv_Meter_OFF_10ms.ino`（旧 `Combined_TX_Meter_UART_B_nonblocking_OFF.ino`）
  - Power logger (ON, TICKあり): `esp32/TXSD_PowerLogger_SYNC_TICK_ON.ino`（旧 `PowerLogger_UART_to_SD_SYNC_TICK_B_ON.ino`）
  - Power logger (OFF, adv_count=0): `esp32/TXSD_PowerLogger_SYNC_TICK_OFF.ino`（旧 `PowerLogger_UART_to_SD_SYNC_TICK_B_OFF.ino`）
  - Note: The `1m_ad` dataset was recorded with the earlier common variants `esp32/TX_BLE_Adv_Meter_blocking.ino` (旧 `Combined_TX_Meter_UART_B.ino`) and `esp32/TXSD_PowerLogger_PASS_THRU_ON_v2.ino` (旧 `PowerLogger_UART_to_SD_SYNC_TICK_B.ino`).
- Key metrics (this set)
  - E_total_mJ mean ≈ 1933.47 mJ (±10.06)
  - E_per_adv_uJ mean ≈ 3222.45 μJ (±16.75) with `adv_count≈600` (t/100 ms approximation)
  - PDR mean ≈ 0.858 (±0.009); RSSI median ≈ −35 dBm
- ΔE snapshot: ON−OFF ≈ −3.58 J/60s (OFF>ON; unexpected) — see `results/フェーズ0-0_E2_1m_100ms_deltaE_2025-11-09.md` and verify wiring/range/power domains/stack state.
  - Latest retry: ON−OFF ≈ −3.85 J/60s — see `results/フェーズ0-0_E2_1m_100ms_retry_latest_2025-11-09.md`.
  - With OFF_02: ON−OFF ≈ −10.07 J/60s — see `results/summary_1m_E2_100ms_deltaE_retry_off02.md`.
  - With OFF_03: ON−OFF ≈ −10.16 J/60s — see `results/summary_1m_E2_100ms_deltaE_retry_off03.md`.
- Next steps for ΔE
  - Collect OFF (60 s) under identical conditions and compute ΔE = E_on − E_off
  - Optionally wire TICK (TX 27 → Logger 33) and set `USE_TICK_INPUT=true` for exact `adv_count`
  - Extend analysis to TL distribution and Pout(τ) per Runbook
  - Ensure ON power logs are captured (`trial_*.csv`) when retrying; see `data/実験データ/研究室/1m_ad_retry/README.md`
