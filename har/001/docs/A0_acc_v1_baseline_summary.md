# A0 (acc.v1, fold90) 基準サマリ
作成日: 2025-11-26  
作成者: Codex  
対象: 3軸 Acc ベースライン（A0）を BLE 比較の基準として固定

## メタ情報
- model_id: `A0_acc_v1`
- config: `har/004/configs/phase0-1.acc.v1.yaml`
- ckpt: `har/004/runs/phase0-1-acc/fold90/best_model.pth`  
  - sha256: `d9fcb1364f888c98e0b61f034519f5e5d794e3e5574cb275b6e4c0083024fd30`
- TFLite int8: `har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite`  
  - sha256: `e1c3ff0042badac5dd9bb478a17fac79991736c813143b45e5cb981d9db68610`  
  - サイズ: 92,768 bytes（約90.6 KB）※22 KB目標未達
- rep_data: `har/004/export/acc_v1/rep_data.npy`（2000窓, 100×3, float32）
- calib_T: 0.7443（valロジット温度スケーリング）  
  tau_unknown: 0.66（Unknown率 5–15%内に調整）  
  θ_low/high: 0.40 / 0.70（未再調整）
- 推定パラメータ数: 63,180（float32換算 約0.25 MB）

## 指標（test fold90, 12→4クラス集約後）
- 12クラス: BAcc=0.8281, Macro F1=0.7473
- 4クラス: BAcc=0.9600, Macro F1=0.7345
- 校正: ECE=0.0924（T=0.7443 適用後）, Unknown率=4.35%（τ=0.66）
- PT↔TFLite: argmax一致=0.98, max_prob MAE=0.0277（200サンプル, `har/001/data_processed/subject01.npz`）

## 4クラス混同行列（row=true, col=pred）
| true \\ pred | Loc | Transition | Stationary | Unknown |
| --- | --- | --- | --- | --- |
| Locomotion | 231 | 0 | 0 | 12 |
| Transition | 0 | 224 | 0 | 17 |
| Stationary | 0 | 0 | 182 | 0 |
| Unknown | 0 | 0 | 0 | 0 |

- Stationary→Loc/Trans 誤り率: 0.0%（0/182）
- Loc→Stationary 誤り率: 0.0%（0/243）
- Unknown予測: 29件（全666サンプルの4.35%）すべて Loc/Transition 系で発生（Stationaryは未知なし）

## 備考
- A0 は「歴史的ベースライン」として再学習しない。今後の A_tiny との比較軸を本表に揃える。
- TFLiteサイズが90.6 KBと大きいので、Phase1 では軽量化版（A_tiny）のサイズ削減を最優先とする。
- θ_low/high は旧設定（0.40/0.70）のまま。TFLite出力で再キャリブする際は本値を置き換える。
