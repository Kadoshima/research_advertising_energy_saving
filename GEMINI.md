# GEMINI.md: advertising-energy_saving

This document provides a comprehensive overview of the `advertising-energy_saving` research project. It is intended to be a living document that is updated as the project evolves.

## Directory Overview

This repository contains the data, code, and documents for a research project investigating energy savings in BLE advertising based on Human Activity Recognition (HAR) uncertainty. The project, named "ReFormHAR-Tiny," aims to develop a system that dynamically adjusts the BLE advertising interval to save energy while maintaining a specified Quality of Service (QoS).

The project is divided into several phases:
- **Phase 1 (Current):** A rule-based system to establish a baseline and validate the core concepts.
- **Phase 2 (Master's Thesis):** A Safe Contextual Bandit approach for online optimization.
- **Phase 3 (Long-term Vision):** A new paradigm of "Semantic-driven Communication" where the application's semantics autonomously control the communication layer.

The repository is organized into the following main directories:
- `data/`: Raw and processed data from the experiments.
- `docs/`: Project documentation, including the overall vision, meeting notes, and metric definitions.
- `esp32/` and `esp32_firmware/`: Firmware for the ESP32 devices used in the experiments.
- `har/`: Human Activity Recognition models and related code.
- `scripts/`: Python scripts for data analysis and processing.
- `results/`: Results of the data analysis.
- `修士論文/` and `修士論文アブスト/`: LaTeX source for the master's thesis and its abstract.

## Key Files

- **`README.md`**: The main README file for the project, containing information about the energy evaluation premise and key scripts.
- **`docs/全体像.md`**: A detailed document outlining the research vision, world model, and roadmap for the "ReFormHAR-Tiny" project.
- **`experiments_manifest.yaml`**: A manifest file that lists all the experimental trials, linking raw data files to experimental conditions.
- **`scripts/compute_delta_energy_off.py`**: A key script for calculating the energy difference between "ON" and "OFF" states.
- **`scripts/compute_pdr_join.py`**: A script for joining TX and RX data to compute the Packet Delivery Rate (PDR).
- **`修士論文/main.tex`**: The main LaTeX file for the master's thesis.

## Usage

This repository is intended for research and development. The primary workflow is as follows:

1.  **Data Collection:**
    -   Firmware from the `esp32/` and `esp32_firmware/` directories is flashed onto ESP32 devices.
    -   Data is collected from the devices and stored in the `data/` directory.

2.  **Data Processing and Analysis:**
    -   The `experiments_manifest.yaml` file is used to select the data to be analyzed.
    -   Scripts from the `scripts/` directory are used to process and analyze the data.
    -   The results of the analysis are stored in the `results/` directory.

3.  **Documentation and Publication:**
    -   The `docs/` directory is used for general project documentation.
    -   The `修士論文/` and `修士論文アブスト/` directories are used to write the master's thesis and its abstract.

### Building the Thesis

To build the PDF for the master's thesis, you can use the `latexmk` command in the `修士論文` directory:

```bash
cd 修士論文
latexmk -C
latexmk -lualatex main.tex
```

Similarly, to build the abstract:

```bash
cd 修士論文アブスト
latexmk -C
latexmk -lualatex main.tex
```
