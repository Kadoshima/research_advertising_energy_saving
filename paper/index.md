# レター論文用インデックス（参照ファイル一覧）
更新日: 2025-11-26  
目的: レター執筆時に参照する仕様書・モデル成果物・設定ファイルをまとめる。

## A_tiny（Tiny HAR for BLE制御）
- 論文仕様書（ACM/IEEE対応）: `har/001/docs/A_tiny_paper_spec_acm_ieee.md`
- Tiny学習スクリプト: `har/004/tools/train_phase0-1_tiny.py`
- Tiny設定: `har/004/configs/phase0-1.acc.v2_tiny.yaml`
- Tiny学習結果: `har/004/runs/phase0-1-acc-tiny/fold90/metrics.json`, `har/004/runs/phase0-1-acc-tiny/fold90/best_model.pth`
- 代表データ（PTQ用）: `har/004/export/acc_v1/rep_data.npy`

## A0（ベースライン、参照用）
- A0サマリ: `har/001/docs/A0_acc_v1_baseline_summary.md`
- A0 ckpt: `har/004/runs/phase0-1-acc/fold90/best_model.pth`
- A0 TFLite: `har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite`
- A0 manifest/meta: `har/004/export/acc_v1_keras/manifest.json`, `har/004/export/acc_v1/meta.json`
- A0 metrics: `har/004/runs/phase0-1-acc/fold90/metrics.json`

## 共通設定・分割
- split定義: `docs/フェーズ0-1/splits_subject90.yaml`
- データ（前処理済）: `har/001/data_processed/subject{XX}.npz`（mHealth胸Acc）

## Phase0-1 関連ドキュメント（参照のみ）
- 引き継ぎ資料: `har/001/docs/Phase0-1_引き継ぎ資料_2025-11-26.md`
- 再評価/作業ログ: `har/001/docs/Phase0-1再評価報告書_2025-11-25.md`, `har/001/docs/Phase0-1_作業ログ_2025-11-25.md`
- 評価表: `har/001/docs/HAR_model_evaluation_phase0-1.md`
- A/B比較・TinyML v1: `har/004/docs/HAR_model_evaluation_phase0-1_v1.md`
- 意思決定ログ: `har/004/docs/decision_log_2025-11-26.md`

## BLE要件・実験指針
- フェーズ1要件: `docs/フェーズ1/要件定義.md`
- リポジトリ共通ルール: `AGENTS.md`, `CLAUDE.md`

## 実行環境メモ
- Tiny学習用venv: `har/001/.venv_tiny`（torch/numpy/pyyamlのみ想定）
- 評価・ツール用venv: `har/001/.venv310`

備考:
- A_tinyのTFLiteサイズ、FLOPs、Reliability図、4クラス混同行列（方向別誤り率）は要計測・要生成。論文化時に追記すること。
