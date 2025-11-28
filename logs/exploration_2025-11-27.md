# ディレクトリ探索ログ (2025-11-27)

## 概要

docs/, har/001/, har/004/ の構造と関係性を調査した。

---

## 1. docs/ ディレクトリ構造

```
docs/
├── 全体像.md              # プロジェクトビジョン（Phase 1→2→3）
├── TODO.md                # 実験計画・TODO管理
├── paper/                 # 論文関連
├── トラブルシューティング/ # 問題解決記録
├── フェーズ0-0/           # Phase 0-0 (ΔEベースライン計測)
├── フェーズ0-1/           # Phase 0-1 HARモデル開発
│   ├── phase0-1_to_phase1_handover.md
│   ├── splits.yaml
│   ├── splits_subject90.yaml
│   └── 要件定義.md
├── フェーズ0-2/           # Phase 0-2
├── フェーズ1/             # Phase 1 要件・設計
│   ├── results/           # 実験結果（ΔE/adv, PDR等）
│   ├── 要件定義.md
│   └── 実験設計書.md
└── フェーズ2/             # Phase 2 要件・設計
    ├── 要件定義.md
    └── 実験設計書.md
```

### 主要ドキュメント

| ファイル | 内容 |
|----------|------|
| 全体像.md | Phase構造、CCS定義、研究ビジョン |
| フェーズ1/要件定義.md | ルールベース（CCS→T_adv写像）の要件 |
| フェーズ2/要件定義.md | Safe Contextual Banditの要件 |
| TODO.md | 実験計画、ハードウェアリスト、週次スケジュール |

---

## 2. har/001/ ディレクトリ（Phase 0-1 オリジナル）

### 概要

- **目的**: Phase 0-1 HARモデル開発（LOSO 10-fold評価）
- **データセット**: mHealth (12クラス → 4クラス統合)
- **学習方式**: Leave-One-Subject-Out (被験者1〜10の10-fold)

### 構造

```
har/001/
├── src/
│   ├── model.py           # DSCNN定義（004でも利用）
│   └── train_phase0-1.py  # 学習スクリプト
├── configs/               # YAMLコンフィグ
├── runs/                  # 学習済みモデル・メトリクス
├── export/                # ONNX/TFLiteエクスポート
├── data_processed/        # 前処理済みデータ（004でも利用）
├── docs/                  # 作業ログ・引き継ぎ資料
└── analysis/              # 混同行列等の分析
```

### 重要ファイル

| ファイル | 内容 |
|----------|------|
| src/model.py | DSCNN(in_ch, stem_ch, dw_channels, fc_hidden, dropout) |
| docs/Phase0-1_引き継ぎ資料_2025-11-26.md | 10-fold結果、ECE=0.0425(fold5最良) |
| data_processed/subject01-10.npz | 前処理済み窓データ |

### 10-fold LOSO結果（12クラス）

**注意**: har/001 は研究用LOSO評価。Phase 1実験には **har/004** の9:1分割モデルを採用。

| Fold | BAcc | 備考 |
|------|------|------|
| Best (fold5) | **90.98%** | ECE=0.0425 |
| Worst (fold2) | **51.31%** | |
| 平均 | **74.13%** | std=14.4% |

データソース: `har/001/runs/phase0-1/summary.json`

---

## 3. har/004/ ディレクトリ（Phase 1 採用モデル）★

### 概要

- **目的**: Phase 1 実験用のベースラインHARモデル確定
- **データセット**: mHealth (har/001/data_processed/ を流用)
- **学習方式**: 被験者ベース9:1分割（train=1-9, test=10）
- **採用モデル**: 3軸加速度のみ (acc.v1)
- **ステータス**: **Phase 1 正式採用** (2025-11-26決定)

### 構造

```
har/004/
├── configs/               # YAMLコンフィグ
│   ├── phase0-1.acc.yaml
│   ├── phase0-1.acc.v1.yaml  # 採用版
│   ├── phase0-1.gyro.yaml
│   └── phase0-1.acc.v2_tiny.yaml
├── runs/
│   ├── phase0-1-acc/      # 3軸加速度モデル
│   ├── phase0-1-gyro/     # ジャイロモデル
│   └── phase0-1-acc-tiny/ # 軽量版
├── export/
│   ├── acc_v1/            # ONNX
│   └── acc_v1_keras/      # TFLite int8 ★採用
├── tools/                 # エクスポート・比較スクリプト
└── docs/                  # 意思決定ログ
```

### 重要ファイル

| ファイル | 内容 |
|----------|------|
| runs/phase0-1-acc/summary.json | BAcc=0.828, ECE=0.092 |
| export/acc_v1_keras/manifest.json | TFLiteアーティファクト情報 |
| docs/decision_log_2025-11-26.md | 採用判断の記録 |

---

## 4. har/001 と har/004 の関係

### 依存関係

```
har/004 ──依存──> har/001
  │                │
  │                ├── src/model.py (DSCNNクラス定義)
  │                └── data_processed/subject01-10.npz
  │
  └── configs, runs, export は独自管理
```

### 主な違い

| 項目 | har/001 | har/004 |
|------|---------|---------|
| 学習方式 | LOSO 10-fold | 9:1固定分割 |
| 目的 | HAR研究精度 | BLE評価用ベースライン |
| 入力チャネル | 6軸(acc+gyro) | 3軸(accのみ) ★採用 |
| テスト被験者 | 全員(fold別) | 被験者10固定 |
| 成果物 | 10個の.pth | 1個の.pth + TFLite |

### har/004が001から流用しているもの

1. **model.py**: DSCNNアーキテクチャ定義
2. **data_processed/**: 前処理済みの窓データ (100x6 or 100x3)
3. **rep_data.npy**: TFLite量子化用の代表データ

---

## 5. 採用ベースラインモデル (AI-A: acc.v1)

### スペック

| 項目 | 値 |
|------|-----|
| モデルID | d9fcb1364f888c98e0b61f034519f5e5d794e3e5574cb275b6e4c0083024fd30 |
| 入力形状 | [1, 100, 3] (2秒窓@50Hz, 3軸加速度) |
| Test BAcc | 0.828 |
| 4クラスBAcc | 0.960 |
| ECE | 0.092 |
| Unknown率 | 4.4% |

### TFLiteアーティファクト

| 項目 | 値 |
|------|-----|
| ファイル | har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite |
| SHA256 | e1c3ff0042badac5dd9bb478a17fac79991736c813143b45e5cb981d9db68610 |
| PyTorch vs TFLite | argmax一致率 0.98, max_prob MAE 0.0277 |

### CCS定義（Phase 1適用）

**仕様定義** (`docs/全体像.md`, `docs/フェーズ1/要件定義.md`):
```
U = 正規化エントロピー (不確実度) ∈ [0, 1]
S = 安定度 ∈ [0, 1]
confidence = 1 - U

CCS = 0.7 × (1 - U) + 0.3 × S
    = 0.7 × confidence + 0.3 × S
```

**現行設定** (`har/004/configs/phase0-1.acc.v1.yaml`):
```yaml
ccs:
  alpha: 0.6  # confidence係数
  beta: 0.4   # stability係数
```

**注意**: 仕様(0.7/0.3)と設定(0.6/0.4)に差異あり。感度分析で調整予定。

- θ_low = 0.40, θ_high = 0.70 → **0.80, 0.90に調整済み** (2025-11-27)
- 調整理由: mHealthのCCS分布が高め(0.84-0.93)のため

---

## 6. 次のアクション

1. ~~Phase 1実験開始前に、TFLiteモデルをESP32-S3にデプロイ~~ → PC側でTFLite推論実施
2. ~~CCS閾値（θ_low, θ_high）のバリデーション実験~~ → 0.80/0.90に調整済み
3. ESP32ファームウェアのCCSモード実装

---

## 7. 修正履歴

| 日付 | 内容 |
|------|------|
| 2025-11-27 | 初版作成 |
| 2025-11-28 | 誤記修正: (1) har/001 10-fold結果の値訂正 (Best=90.98%, Worst=51.31%, 平均=74.13%), (2) CCS定義を仕様に合わせて修正, (3) docs/構造を実態に合わせて修正, (4) har/004が採用モデルであることを明確化 |

---

*Last updated: 2025-11-28*
