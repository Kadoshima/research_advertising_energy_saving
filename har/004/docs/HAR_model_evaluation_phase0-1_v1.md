# HAR小型MLモデル 評価リスト（Phase0-1, 2025-11-26時点）

対象モデル
- AI-A（正式ベースライン）: 3軸 acc.v1  
  - config: `har/004/configs/phase0-1.acc.v1.yaml`  
  - ckpt: `har/004/runs/phase0-1-acc/fold90/best_model.pth` (sha256=d9fcb1364f888c98e0b61f034519f5e5d794e3e5574cb275b6e4c0083024fd30)  
  - TFLite: `har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite` (sha256=e1c3ff0042badac5dd9bb478a17fac79991736c813143b45e5cb981d9db68610)  
  - 評価元: `har/004/runs/phase0-1-acc/fold90/metrics.json`, `har/004/export/acc_v1_keras/manifest.json`
- AI-B（比較候補）: 6軸 gyro版  
  - config: `har/004/configs/phase0-1.gyro.yaml`  
  - ckpt: `har/004/runs/phase0-1-gyro/fold90/best_model.pth`  
  - 評価元: `har/004/runs/phase0-1-gyro/fold90/metrics.json`

---

## 1. モデル基本仕様
| 評価項目 | AI-A | AI-B | 備考 |
|---|---|---|---|
| パラメータ数 | 未算出 | 未算出 | 要 `keras.summary` など |
| FLOPs | 未算出 | 未算出 |  |
| float32サイズ (KB) | 未算出 | 未算出 |  |
| int8 TFLiteサイズ (KB) | 未計測（ファイル有） | 未生成 | 目標≤22 KB |
| Arena推定メモリ (KB) | 未測定 | 未測定 | ESP32要計測 |

## 2. 認識性能（出典: metrics.json）
| 評価項目 | AI-A | AI-B | 備考 |
|---|---|---|---|
| Test BAcc | 0.8281 | 0.8609 | `...acc/fold90/metrics.json`, `...gyro/fold90/metrics.json` |
| Macro F1 | 0.7473 | 0.7748 | 同上 |
| Weighted F1 | 未算出 | 未算出 |  |
| クラス別F1（最低） | 未算出 | 未算出 |  |

## 3. 較正性能（出典: metrics.json calibration）
| 評価項目 | AI-A | AI-B | 備考 |
|---|---|---|---|
| ECE | 0.083 | 0.110 | 目標≤0.06 |
| 最適温度 T | ― | 0.624 | gyroのみ出力 |
| Unknown閾値 τ | ― | 0.80 | gyroのみ出力 |
| 実際のUnknown率 | 0.067 | 0.132 |  |
| Reliability図 | 未生成 | 未生成 | 要可視化 |

## 4. U/S/CCS出力品質
| 評価項目 | AI-A | AI-B | 備考 |
|---|---|---|---|
| U分布の妥当性 | 未評価 | 未評価 | 要プロット |
| S追従性 | 未評価 | 未評価 |  |
| CCS分布範囲 | 想定0-1 | 想定0-1 | conf=max_prob, CCS=0.7*conf+0.3*S |
| 状態遷移安定性 | 未評価 | 未評価 | 実機ログ要 |

## 5. 推論効率
| 評価項目 | AI-A | AI-B | 備考 |
|---|---|---|---|
| 推論時間@ESP32 (ms) | 未測定 | 未測定 | 要 t_inf ベンチ |
| 推論時間@PC (ms) | 未測定 | 未測定 |  |
| 量子化による精度低下 | argmax一致0.98, MAE 0.0277 | 未実施 | `compare_pytorch_tflite.py` (200サンプル, subject01) |

## 6. 実用性
| 評価項目 | AI-A | AI-B | 備考 |
|---|---|---|---|
| 入力仕様整合性 | OK (100,3, 50Hz, 2s) | OK (100,6, 50Hz, 2s) |  |
| 出力12クラス | OK | OK | mHealth準拠 |
| 4クラス集約 | OK | OK | BAcc/F1(4クラス)算出済み |
| エラーハンドリング | 未記述 | 未記述 |  |

## 7. コード品質・再現性
| 評価項目 | AI-A | AI-B | 備考 |
|---|---|---|---|
| 学習コード実行可能性 | OK (`train_phase0-1.py`) | OK |  |
| シード固定 | seed=42 | seed=42 | config記載 |
| TFLite変換 | Yes (int8, PTQ) | 未実施 |  |
| 設定ファイル出力 | `...acc.v1.yaml` | `...gyro.yaml` | Cヘッダ未 |

## TinyMLアーティファクト v1（AI-A acc.v1）
- TFLite: `har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite` (sha256=e1c3ff0042badac5dd9bb478a17fac79991736c813143b45e5cb981d9db68610)
- PTQ: rep_data.npy（2000窓, 100x3, float32）
- PyTorch vs TFLite: argmax一致 0.98, max_prob MAE 0.0277（200サンプル, `har/001/data_processed/subject01.npz`）
- manifest: `har/004/export/acc_v1_keras/manifest.json`

## TODO / 推奨アクション
- θ_low/θ_high を TFLite出力ベースで再キャリブ（CCS式: conf=max_prob, CCS=0.7*conf+0.3*S）。
- ESP32/TFLM統合: har_model_infer ラッパ、HarOut/Policy skeleton、t_inf/Arena計測。
- パラメータ数/FLOPs/モデルサイズ/RelDiagram の補完。堅牢性評価（U/S/CCS分布, 状態遷移）も要実施。
