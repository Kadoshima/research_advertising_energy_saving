# フェーズ0-1 HARレーン意思決定ログ (2025-11-26)

- 方針変更: LOSO→「被験者ベース9:1」への学習集中。train=被験者1–9、test=被験者10を基本とし、valはtrain側から10%サブサンプル（データリーク回避のため被験者跨ぎはしない）。  
- 目的: BLE評価を優先し、汎化よりも学習量とKPI改善を優先。HAR研究精度は二次。  
- 追加データ拡張: オンザフライで軽量Augを適用  
  - 時間伸縮 ±10%  
  - 小角度回転（±5〜10°）  
  - Gaussianノイズ (SNR>20dB)  
  - （任意）軸スケーリング ±5%、位相シフト ±2サンプル  
- モデル設定: 現行の強化DS-CNN(Acc+Gyro, in_ch=6, Dropout0.3)を継続し、エポック短めで反復。  
- 次アクション: 新splits生成（train1-9/test10、valはtrain抽出）、DataLoaderにAug実装→再学習→KPI確認（BAcc/ECE/Unknown率）。  
- 2025-11-26 追加判断: ECE優先で追加再キャリブレーション（Tレンジ0.3–4.0, ece_bins=20）。3軸版と6軸版を比較し、BLE用途では「ECE/Unknown重視なら3軸、検出率優先なら6軸」で採用判断。
- 2025-11-26 採用決定: Phase0-1 正式ベースライン = 3軸版 (config: har/001/configs/phase0-1.acc.v1.yaml, model: har/001/runs/phase0-1-acc/fold90/best_model.pth, model_id[sha256]=d9fcb1364f888c98e0b61f034519f5e5d794e3e5574cb275b6e4c0083024fd30)。理由: Test BAcc≈0.828, 4クラスBAcc≈0.960, ECE≈0.083, Unknown≈0.067 と Phase0-1要件(BAcc≥0.80, Unknown∈[5,15%])を満たし、安全側マージンとして十分。6軸版は検出率優先の比較候補として保持。
- 2025-11-26 CCS定義（Phase1適用）: conf = max_prob, CCS = 0.7 * conf + 0.3 * S, θ_low/θ_high はバリデーションで再キャリブ（デフォルト 0.40/0.70 は置き換え可）。旧式(0.6*U+0.4*(1−S))は使わない。
