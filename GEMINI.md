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

## Documentation Rules (追加)

- New documents should live under `docs/フェーズN/<task_slug>/` (do not create new phases without agreement).
- Each task directory must include a `README.md` that indexes code/data/results/config paths.
- README required fields: purpose/scope, input data (source/version/row count/SHA256), outputs (generation date/script), reproduction commands, status (draft/frozen/obsolete), related links, update history (YYYY-MM-DD).
- For TXSD/RX `.ino` sketches that write CSV logs, include a unique `program_id` column in every row (TX excluded).

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

---
## Data Integrity Rules（データ取り扱い厳守事項）
### 禁止事項
- データの捏造・作成は禁止（実測データを勝手に生成しない）
- 定数・閾値・パラメータの勝手な設定は禁止（根拠なく値を決めない）
- 存在しないファイルパスやデータを参照しない
### 許可事項
- ソースコード（スクリプト）を用いて既存データから導出されるデータは可
- 既存の凍結済みパラメータ（docs/TODO.md の凍結仕様セクション参照）の引用は可
- シミュレーションは明示的にシミュレーションと記載した上で実行可
### 確認義務
- 数値を引用する際は必ず参照元ファイルパスを明記する
- 新規パラメータを提案する場合は根拠（論文、既存データ、計算式）を示す
- 不明な場合は推測せずユーザーに確認する
---
## Research Rules（研究ルール）
### 再現性（Reproducibility）
- 実験には必ず manifest.csv を作成し、条件（trial_id, session, interval, mode等）を記録する
- 使用したファームウェアの PROGRAM_ID またはgit commit hashをログに残す
- 乱数シードは固定し、使用した値を明記する（例: seed=0xD4B40201）
- 解析スクリプトは引数やconfigで再実行可能な形にする
### 失敗実験の扱い
- 失敗・中断した試行は削除せず mode=ABORT や status=failed でマークする
- 失敗理由を logs/worklog_*.txt に記録する（同じ失敗を繰り返さないため）
- 短いabort試行は manifest.csv から除外するか、除外理由を明記する
### 統計的報告
- n=1 の結果は「参考値」「形式検証」と明記し、統計的主張に使用しない
- 結果報告時は n, mean, std（または95% CI）を併記する
- 都合の良い試行だけ選ばない（全試行を報告し、除外した場合は理由を明記）
- p値を報告する場合は検定手法と前提条件を明記する
### ハードウェア状態
- 配線変更時は docs/フェーズ0-0/実験装置仕様書_v3.md を更新する
- ファームウェア変更時は変更理由をコミットメッセージまたはREADMEに記載する
- 使用機材（ESP32型番、INA219、SDカード等）のバージョンを実験ログに残す
### 時刻同期
- TX/RX/TXSDのログは同期方法を明記する（SYNC信号、tl_time_offset_ms、seq×interval_ms等）
- 同期が取れていないデータは解析対象外とするか、その旨を明記する
- タイムスタンプのズレが疑われる場合は gap_stats 等で検証してから使用する