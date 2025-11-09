# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ReFormHAR-Tiny**: Research project for BLE advertising energy optimization driven by Human Activity Recognition (HAR) uncertainty. The project evaluates power-saving strategies by dynamically adjusting BLE advertising intervals based on on-device HAR inference outputs (uncertainty U, stability S, and composite score CCS).

**Primary Goal**: Quantify energy savings with reproducible KPIs (event charge μC, average current mA, latency TL distribution, outage probability Pout(τ), PDR) while maintaining communication quality constraints.

## Repository Structure

- **`docs/フェーズN/`**: Phase deliverables (requirements, design documents, runbooks). Phase 1 focuses on fixed-baseline + uncertainty-driven (rule-based mapping) evaluation.
- **`data/`**: Curated datasets (mHealthDataset, experimental data). Source, version, and SHA256 must be documented when adding new data.
- **`ISWC22-HAR/`**: HAR model training codebase (TinyHAR and variants). Used for training lightweight models for deployment on ESP32-S3/C3.
- **`stm32ai-modelzoo/`**: Reference TinyML models (mostly STM32-focused). Included for model selection research.
- **`configs/`**: Reusable parameter sets. Filenames should align with document slugs (e.g., `要件定義_simulation.yaml`).
- **`results/`**: Derived tables, charts, summaries. Note generation date and script in adjacent Markdown.
- **`scripts/`**: Ad-hoc automation scripts. Run from repository root.

## Development Commands

### Python Environment

The project uses a virtual environment at `.venv_har/`:

```bash
# Activate the virtual environment
source .venv_har/bin/activate

# Install Python dependencies (ISWC22-HAR)
pip install -r ISWC22-HAR/requirements.txt
```

### HAR Model Training

Training scripts are located in `ISWC22-HAR/`:

```bash
# Train a HAR model using experiment.py with YAML config
python ISWC22-HAR/experiment.py --config ISWC22-HAR/SDIL.yaml

# Training configurations are in ISWC22-HAR/configs/
# - data.yaml: Dataset configurations
# - model.yaml: Model architecture parameters
```

Model configurations (`ISWC22-HAR/configs/model.yaml`) define architectures like:
- `deepconvlstm`: Deep convolutional LSTM
- `tinyhar`: Lightweight HAR model (ISWC22 Best Paper)
- `attend`, `sahar`: Attention-based variants
- `mcnn`: Multi-scale CNN

### Documentation Workflow

```bash
# Lint Markdown files before committing
markdownlint docs

# Preview rendered Markdown (if glow is installed)
glow docs/フェーズ1/要件定義.md

# Verify internal links before pushing
git diff  # Confirm table layout and diagram embeds

# Optional: Check external URLs (when refreshing references)
npx markdown-link-check docs/フェーズ1/要件定義.md
```

## Code Architecture

### HAR Model Training Pipeline (ISWC22-HAR)

**Entry Point**: `experiment.py` - Main experiment orchestration class (`Exp`)

**Key Components**:
1. **Dataloaders** (`dataloaders/`): Dataset-specific loaders inheriting from `BASE_DATA`
   - Supports multiple HAR datasets (DG, DSADS, HAPT, PAMAP, WISDM, etc.)
   - Handles sliding windows, normalization, data augmentation
   - Configurable window size, overlap, representation type (time/freq/time-freq)

2. **Models** (`models/`): Model architectures built via `model_builder.py`
   - `TinyHAR.py`: Lightweight architecture with individual conv subnets, transformer encoder, cross-channel fusion
   - `deepconvlstm.py`: ConvLSTM baseline
   - `Attend.py`, `SA_HAR.py`: Self-attention variants
   - `crossatten/`: Cross-attention components

3. **Training Utilities** (`utils.py`):
   - `EarlyStopping`: Early stopping with patience
   - `adjust_learning_rate_class`: Learning rate scheduling
   - `MixUpLoss`, `mixup_data`: Data augmentation

**Training Flow**:
```
YAML Config → Exp.__init__() → build_model() → train() → evaluate() → save()
```

### Phase 1 Implementation Guidelines

**Target Hardware**: ESP32-S3/C3 with TensorFlow Lite for Microcontrollers (TFLM)

**Model Constraints** (from `docs/フェーズ1/model定義.md`):
- Tensor Arena: ≤ 80 KB (start at 64 KB)
- Flash: ≤ 200 KB
- FLOPs: ≤ 8 M
- Inference time (t_inf): ≤ 20 ms/window
- Quantization: int8 only, use esp-nn optimization on S3

**Standard Profile - DS-CNN**:
- Input: 50×6 (1.0s window, 50Hz IMU, 50% overlap)
- Architecture: DWConv1D(k=5, s=1) → PWConv(16) → DWConv1D(k=5, dilation=2) → PWConv(24) → GAP → Dense(K) → Softmax
- ~1k params, ~0.03M FLOPs, ~5ms on S3@240MHz

**Extended Profile - DS-CNN++** (optional):
- Multi-scale branches: A=50×6 (1.0s), B=25×6 (0.5s)
- Early-exit (Exit-0): Conditions: max_softmax≥0.90 AND temperature-scaled≥0.85
- 9-12k params, 3-5M FLOPs, 8-12ms (3-5ms with early exit)

### Policy Engine Architecture

**Components** (from `docs/フェーズ1/詳細設計定義書.md`):

1. **C1: Sensing & HAR**: IMU → preprocessing (1.0s window/50% overlap) → classification (pₖ) → U/S/CCS calculation
   - U (Uncertainty): Normalized entropy of output probabilities [0,1]
   - S (Stability): Based on state transitions in last W=10s
   - CCS (Composite Score): 0.7×confidence + 0.3×stability
   - Output: 0.5s period

2. **C2: Policy Engine (Rule)**: CCS → adv_interval mapping with hysteresis
   - States: ACTIVE(100ms), UNCERTAIN(500ms), QUIET(2000ms), FALLBACK(1000ms)
   - Thresholds: {θ_low, θ_high} recalibrated in P1 (initial: 0.40/0.70)
   - Hysteresis: ±0.05
   - Constraints: Min dwell time ≥2s, switch rate limit ≤1Hz

3. **C3: BLE Advertiser**: Apply interval, transmit on 3 channels (37/38/39)

4. **C4: Telemetry & KPI**: Unified logs (TX/RX/power/decision rationale), KPI generation

5. **C5: Power Meter I/F**: VBAT series measurement, event boundary marking, μC calculation

## Key Concepts

**Terminology** (see `docs/フェーズ1/用語集.md`):
- **TL (Time-to-first-Receive)**: Latency from activity change to first advertisement reception
- **Pout(τ)**: Outage probability - Pr[TL > τ] for τ=1/2/3s
- **PDR**: Packet Delivery Rate (after deduplication)
- **Event charge**: Current integral for one advertising event (3-channel transmission) in μC
- **CCS thresholds**: {θ_low, θ_high} recalibrated in P1 validation (replace initial 0.40/0.70)

**Experimental Setup**:
- Environments: E1 (low interference), E2 (high Wi-Fi interference)
- Conditions: Fixed intervals {100, 500, 1000, 2000}ms + uncertainty-driven (5 total)
- Repetitions: ≥3 per condition per environment
- Receiver: Android LOW_LATENCY scan mode

**Acceptance Criteria** (KPI-1 to KPI-3):
- KPI-1: Average current improvement ≥5-10% vs fixed 100ms baseline
- KPI-2: Pout(1s) degradation ≤+1.0%pt, TL p95 degradation ≤+10%
- KPI-3: Event charge/current reproducibility ±5%, log loss <1%

## Coding Conventions

**Documentation**:
- Write concise, declarative Japanese-first prose
- Introduce English terms in parentheses on first mention
- Prefer Japanese filenames; when romanizing, use lowercase snake_case
- Maintain parallel bullet structures, limit paragraphs to three sentences
- Date entries as YYYY-MM-DD
- Document dataset metrics with units and cite sources

**Commits**:
- Use imperative commit subjects (e.g., "Update 要件定義.md")
- Scope each commit to a single topic
- PR descriptions: list affected documents, summarize impact, reference issues
- Attach render diffs or screenshots for visual changes

**File Organization**:
- Add new material to appropriate phase directory (`docs/フェーズN/`)
- Store supporting assets beside referencing document with slugged filenames (e.g., `要件定義_図1.png`)
- Align config filenames with related doc slugs
- Log dataset source, version, SHA256 in consuming document

## Testing

**No automated test suite exists**. Manual validation:
- Confirm internal anchors, relative links, and cross-phase references
- Preview diagrams and tables with Markdown viewer
- Reconcile CCS thresholds with `docs/フェーズ1/Runbook.md`
- When adjusting datasets, validate row counts and update checksums

**HAR Model Validation**:
- Subject-wise K-fold cross-validation (leave-one-subject-out)
- Metrics: F1 (macro), accuracy, confusion matrix
- Model profiling: Arena usage, t_inf (1000 iterations via esp_timer), Flash size, FLOPs

## Phase Progression

**Phase 1** (current): Fixed baseline + uncertainty-driven rule-based mapping
- Deliverables: Requirement compliance report, unified logs (TX/RX/power/KPI), mapping table (CCS→adv_interval), event charge reference, reproducibility runbook

**Phase 2/3 接続** (handoff to future phases):
- Mapping table exported as CSV for MAB warm-start
- Event charge dictionary for MAB reward normalization
- Log schema extensible via column addition (arm/reward/context)
- KPI calculation scripts with Pout(τ) constraint check interface

## Important Notes

- Avoid introducing new tooling or build systems unless coordinated with maintainers
- Reconcile any threshold changes with Runbook and log schema
- Always cite external references when adding quantitative claims
- For model training, check ISWC22-HAR/configs/ for existing parameter sets before creating new configs
- When working with experimental data, verify sync markers and timestamp alignment across TX/RX/power logs
