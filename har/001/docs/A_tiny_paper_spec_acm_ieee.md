# A_tiny 論文仕様書（ACM/IEEE対応版・根拠パス付き）
作成日: 2025-11-26  
用途: 他AIに「この仕様に従って論文データシート＋実験セクションを作成せよ」と指示するための完全仕様。ACM/IEEEテンプレにそのまま流し込める構造。

---

## 根拠ファイル（現状ベース）
- モデル定義: `har/001/src/model.py`（可変幅DSCNN）
- Tiny学習スクリプト: `har/004/tools/train_phase0-1_tiny.py`
- Tiny config: `har/004/configs/phase0-1.acc.v2_tiny.yaml`
- Tiny出力: `har/004/runs/phase0-1-acc-tiny/fold90/metrics.json`, `best_model.pth`
- A0サマリ: `har/001/docs/A0_acc_v1_baseline_summary.md`
- A0 ckpt/TFLite/manifest: `har/004/runs/phase0-1-acc/fold90/best_model.pth`, `har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite`, `har/004/export/acc_v1_keras/manifest.json`
- split: `docs/フェーズ0-1/splits_subject90.yaml`
- データ: `har/001/data_processed/subject{XX}.npz`（mHealth胸Acc前処理済み）
- rep_data: `har/004/export/acc_v1/rep_data.npy`

---

# I. Model Specification

### I-A. Inputs and Preprocessing
- Sensor: chest 3-axis accelerometer (mHealth互換)
- Window: 1.0 s (100 samples @ 50 Hz), hop 0.5 s
- Preprocess: subject-wise z-score、フィルタなし
- Input shape: (100, 3)

### I-B. Model Architecture: A_tiny (Proposed)
- 要求: レイヤ表（出力形状付き）
- Stem Conv1D: k=5, s=1, ch=32
- DWConv1: ch=48
- DWConv2: ch=64
- GAP → FC hidden=64 → 12-way softmax
- Dropout=0.2
- Params: ~10k（正確値算出）
- FLOPs: 理論値算出
- Model size: float32推定、int8 TFLite実測
  - TFLiteサイズは要計測（未取得）

### I-C. Baseline Model: A0
- Stem=48, DW=96→128, FC=128→12, dropout=0.3
- Params=63,180
- TFLite int8=92,768 bytes
- float32サイズ ≈ 246 KB
- 要求: 同じフォーマットのレイヤ表

---

# II. Training Setup

### II-A. Environment
- OS/CPU（Mac CPU-only）
- Python/PyTorch version（例: torch 2.9.1 in `.venv_tiny`）
- Seed=42

### II-B. Data Splits
- Protocol: LOSO fold90 (subject10=test)
- splits YAML: `docs/フェーズ0-1/splits_subject90.yaml`
- Train/Val/Test subjects & window countsを表で

### II-C. Optimization
- Loss: 12-class CrossEntropyLoss
- Optimizer: Adam (lr=1e-3, weight_decay=1e-4)
- Epochs/batch: config参照 (例: max_epoch=5, batch=128, early_stop_patience=2)
- Augmentation（`train_phase0-1_tiny.py`実装）:
  - Time stretch ±10%
  - Rotation jitter ±10°
  - Amplitude scaling ±5%
  - Phase shift ±2 samples
  - Gaussian noise (SNR≈20 dB)

---

# III. Evaluation Protocol

### III-A. 12-Class
- Metrics: Acc, BAcc, Macro-F1, Weighted-F1
- Confusion matrix（図を要求）

### III-B. 4-Class (BLE Control)
- Mapping表を明記:
  - Locomotion = walk/run/stairs 等
  - Transition = stand-up/sit-down/bends/arms/crouch/jump
  - Stationary = sitting/standing/lying
  - Ignore = その他/Unknown
- Metrics: BAcc, Macro-F1
- Directional errors: Stationary→Loc, Loc→Stationary
- 4×4 混同行列（図要求）
- 注: BLE制御で用いる運用クラス

---

# IV. Calibration and Uncertainty

### IV-A. Temperature Scaling
- valロジットでT最適化（NLL/ECE）
- 報告: T*, ECE(4c) after calibration

### IV-B. Unknown Threshold τ
- 定義: max softmax < τ を Unknown
- 5–15%カバレッジ制約で τ 選択、値とカバレッジを報告

### IV-C. Stability S
- 定義: 遷移数に基づき10s窓などで算出（既存実装に準拠）

### IV-D. CCS
- CCS = 0.7 * confidence + 0.3 * S
- θ_low / θ_high とヒステリシス（up/downあれば両方）

### IV-E. Reliability Diagram
- 4クラス版の信頼性図（図要求）

---

# V. TinyML Implementation

### V-A. Quantization
- int8 PTQ（per-channel conv, per-tensor FC）
- Representative: `har/004/export/acc_v1/rep_data.npy` (2000 windows)
- 報告: argmax一致率, max_prob MAE, TFLite SHA256

### V-B. Size & Runtime (ESP32-S3)
- int8 TFLite size (bytes)
- Inference latency: avg/p95 over 1000 runs, CPU freq, esp-nn有無を明記
- Tensor Arena: minimum / recommended
- 表形式で要求

---

# VI. BLE Control Experiment (Phase 1)

### VI-A. Policy Engine
- States: ACTIVE(100ms), UNCERTAIN(500ms), QUIET(2000ms)
- Inputs: CCS, U, S
- Thresholds: θ_low, θ_high, hysteresis (up/down)
- Constraints: min state duration=2s, max transition rate=1 Hz, fallback=1000ms
- 状態遷移図（図要求）

### VI-B. Platform
- TX: ESP32-S3
- TXSD: ESP32-S3 + INA219
- RX: nRF52/ESP32
- BLE PHY: 1M, distance 1 m

### VI-C. Conditions
- Environments: E1 (low interference), E2 (high)
- Strategies: fixed {100,500,1000,2000} ms vs uncertainty-driven (A_tiny)
- Repetitions: ≥3 per condition

### VI-D. Logs
- TX: CCS, U, S, adv_interval
- TXSD: event charge (ΔE/adv), average current
- RX: Pout(1/2/3s), TL p50/p95

### VI-E. KPIs
- KPI-1 Energy: avg current, ΔE/adv, goal ≥5–10% better than 100ms
- KPI-2 Quality: Pout(1s) degradation ≤ +1.0 pt, TL p95 ≤ +10%
- KPI-3 Reproducibility: variation ≤ ±5%

---

# VII. Summary Tables (IEEE/ACM-ready)
- HAR Performance: Model | Params | 12c BAcc | 12c F1 | 4c BAcc | 4c F1 | Stat→Loc | Loc→Stat
- Calibration: Model | T | ECE(4c) | Unknown % | τ
- TinyML: Model | TFLite size | Argmax match | MAE | t_inf(ms) | Arena(KB)
- BLE: Condition | Avg Current | ΔE/adv | Pout(1s) | TL p95

---

# VIII. Reproducibility (Appendix)
- コードパス一覧: model, train, tiny-train, PTQ/TFLite exporter, CCS/Policy, BLE logger
- Config: 全YAML（モデル/学習/ポリシー）、split YAML
- SHA256: TFLiteモデル、rep_data.npy
- Dataset license: mHealth公開。プライバシー懸念なし。

---

# IX. Mandatory ACM/IEEE Sections
- Threats to validity: internal/external/construct/statistical
- Limitations: 3-axis only, fold90依存, ESP32-S3のみ
- Future work: multi-sensor, adaptive policy, PHY多様化

---

## 現状の参考数値（埋め込み例）
- A0 fold90 test: 12c BAcc 0.8281 / F1 0.7473, 4c BAcc 0.9600 / F1 0.7345, ECE(4c)≈0.092 (T=0.7443), Unknown率≈4.35%。TFLite=92,768B, PT↔TFLite=0.98/0.0277。
- A_tiny (stem32,dw48/64,FC64) fold90: 12c BAcc 0.8581 / F1 0.8373, 4c BAcc 0.7303 / F1 0.7281（要改善）, TFLite未測定。

---

## 他AIへの指示テンプレ
「この仕様書に従い、A_tiny（Tiny HAR for BLE制御）の論文データシート＋実験セクション草稿を作成してください。ACM/IEEEテンプレに貼り付け可能な形で、表番号・図番号プレースホルダを付け、未計測項目は“要計測”と明記してください。」
