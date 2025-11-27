# レター論文用インデックス（Phase0-1/A_tiny + 既存BLEリサーチノート）
更新日: 2025-11-26  
注意: BLEのKPIや非理想スキャンに関する記述は `docs/paper` 配下のリサーチノートに集約。`har/` 配下には置かない。

## 新規（A_tiny / Phase0-1）
- 論文仕様書（ACM/IEEE対応）: `har/001/docs/A_tiny_paper_spec_acm_ieee.md`
- Tiny学習スクリプト: `har/004/tools/train_phase0-1_tiny.py`
- Tiny設定: `har/004/configs/phase0-1.acc.v2_tiny.yaml`
- Tiny学習結果: `har/004/runs/phase0-1-acc-tiny/fold90/metrics.json`, `har/004/runs/phase0-1-acc-tiny/fold90/best_model.pth`
- A0サマリ: `har/001/docs/A0_acc_v1_baseline_summary.md`
- A0 TFLite/ckpt/manifest: `har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite`, `har/004/runs/phase0-1-acc/fold90/best_model.pth`, `har/004/export/acc_v1_keras/manifest.json`
- split定義: `docs/フェーズ0-1/splits_subject90.yaml`
- データ前処理済: `har/001/data_processed/subject{XX}.npz`

## 既存BLE関連ドキュメント（docs/paper 配下）
- `docs/paper/literature_review_ble_dynamic_adv.md` … 動的adv制御の先行研究サーベイ。実機で電力×到達性同時計測の希少性を指摘
- `docs/paper/repomix-output.xml` … 証拠集メタ（本文引用は不要）

## リサーチノート（調査・考察）
- `docs/paper/BLE非理想スキャン_RL最適化_リサーチノート.md` … 非理想スキャン挙動、Valley Area、高調波、Opportunistic scan、MAB/RL報酬設計例
- `docs/paper/TinyML制約付き学習_リサーチノート.md` … MCU上のMAB/LinUCB制約と高速化、RAMクラス別指針
- `docs/paper/不確実性駆動送信制御_リサーチノート.md` … 不確実性指標/温度スケーリング/Early Exit/ファジィ制御など実装例

## Phase0-1 関連（参照のみ）
- 引き継ぎ: `har/001/docs/Phase0-1_引き継ぎ資料_2025-11-26.md`
- 再評価/作業ログ: `har/001/docs/Phase0-1再評価報告書_2025-11-25.md`, `har/001/docs/Phase0-1_作業ログ_2025-11-25.md`
- 評価表: `har/001/docs/HAR_model_evaluation_phase0-1.md`
- A/B比較・TinyML v1: `har/004/docs/HAR_model_evaluation_phase0-1_v1.md`, `har/004/docs/decision_log_2025-11-26.md`

## BLE要件・共通ルール
- フェーズ1要件: `docs/フェーズ1/要件定義.md`
- リポジトリルール: `AGENTS.md`, `CLAUDE.md`

## 備考
- A_tinyのTFLiteサイズ、FLOPs、Reliability図、4クラス混同行列（方向別誤り率）は要計測・要生成。論文化時に追記すること。
- BLE KPIに関する設計・考察は docs/paper 配下のリサーチノートを優先的に参照。`har/` 配下には書かない。
- リサーチノート類は調査・考察枠。実測データやモデル結果は har/ 配下および仕様書で取得・記載。

---

## IEEE論文化向け 参照ガイド & 必須記載ポイント

### どのデータをどこで見るか
- **モデル仕様・実装**: `har/001/src/model.py`（DSCNN定義）  
  - A_tiny/A0のレイヤ構成・パラメータ算出の根拠。
- **設定/分割**: `har/004/configs/phase0-1.acc.v2_tiny.yaml`（Tiny）、`har/004/configs/phase0-1.acc.v1.yaml`（A0）、`docs/フェーズ0-1/splits_subject90.yaml`（fold90）。
- **学習結果**: `har/004/runs/phase0-1-acc-tiny/fold90/metrics.json`、`har/004/runs/phase0-1-acc/fold90/metrics.json`。  
  - 12c/4cのBAcc/F1、calibration/T/τはここを引用。
- **導出メタ**: A0 manifest/meta (`har/004/export/acc_v1_keras/manifest.json`, `har/004/export/acc_v1/meta.json`) → sha256, rep_data, PT↔TFLite誤差。
- **データセット**: 前処理済 `har/001/data_processed/subject{XX}.npz`（胸Acc）。元データは mHealth（公開データセット）であることを明記。
- **BLE要件・KPI**: `docs/フェーズ1/要件定義.md`（KPI/閾値の根拠）、docs/paper 配下のリサーチノート（非理想スキャン/動的adv/TinyML制約/不確実性制御）。

### IEEE論文で必ず書くべき項目（抜け防止）
1. **タスク・設定**: 3軸胸Acc, 1.0s/0.5s窓, 12→4クラス集約（表で定義）。
2. **データ分割**: fold90（subject10 test）、train/val/test人数と窓数。
3. **モデル**: A0/A_tinyの全レイヤ表（出力形状・パラメータ数・FLOPs）、int8サイズ。
4. **学習条件**: CE, Adam, lr/batch/epoch/early-stop、augment（5種の範囲を明記）。
5. **指標（12c/4c）**: Acc/BAcc/Macro-F1/Weighted-F1、4c混同行列と Stationary↔Loc 誤り率（方向別）。
6. **較正/U/S/CCS**: T最適化法、T値、ECE(4c)、τ (Unknown 5–15%)、CCS式と θ_low/high、Reliability図。
7. **TinyML**: PT↔TFLite誤差（argmax一致/MAE）、int8サイズ、ESP32-S3の t_inf(p95/avg)、Arena最小/推奨。
8. **BLE制御**: ポリシー仕様（ACTIVE/UNCERTAIN/QUIET, θ, ヒステリシス, min_stay, max_rate, fallback）、状態遷移図。
9. **BLE実験設計**: 環境E1/E2、条件（固定{100,500,1000,2000}+不確実度）、反復回数、ログ項目（CCS/U/S/adv_interval, ΔE/adv, avg current, Pout, TL）。
10. **KPI判定**: 省電力（平均電流5–10%改善）、品質（Pout+1pt, TL p95 +10%）、再現性（±5%）。
11. **再現性**: コード/設定パス一覧、SHA256（TFLite, rep_data）、データライセンス（mHealth公開、プライバシー懸念なし）。
12. **Threats/Limitations/Future**: 3軸のみ、fold90依存、S3のみ評価、将来は多センサ/ポリシ適応/PHY拡張。

### よく参照する図・表
- 4クラス混同行列（row=true, col=pred）A0/A_tiny
- Reliability図（4クラス）
- モデルレイヤ表（A0/A_tiny）
- BLE状態遷移図
- 総合サマリ表（HAR性能/Calibration/TinyML/BLE KPI）

### メモ
- A_tiny: TFLiteサイズ、FLOPs、Reliability図、4c混同行列（方向別）は要生成・要記載。
- BLE KPIに関する設計・考察は docs/paper 配下のリサーチノートを優先的に参照。`har/` 配下には書かない。
