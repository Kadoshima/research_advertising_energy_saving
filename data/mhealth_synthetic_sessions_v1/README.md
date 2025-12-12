# mHealth 高遷移セッション（合成） v1.0
- 生成日時: 2025-12-12
- 仕様: `docs/フェーズ1/mhealth_synthetic_sessions_spec_v1.md` に準拠（15s断片、類似度>0.95除外、0.5sクロスフェード、境界±1s除外、TRUTH_DT_MS=100ms）
- 入力: `data/MHEALTHDATASET/mHealth_subject{1..10}.log`
- HARモデル: `har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite`（TFLite, 2s窓/1sストライド）
- 正規化: train subjects(1-8) の胸部ACCでグローバル z-score
- 断片抽出: test subjects(9-10) から 15s 非重複。各ラベル内で類似度>0.95（mean/std/RMS/主周波数）を除外。
- ラベル: 4クラス (0:Locomotion, 1:Transition, 2:Stationary, 3:Unknown 未使用)
- セッション構成: 15s滞在×60セグメント（計59遷移）。0.5sクロスフェードの分だけ実長 ≈870.5s（約14.5分）。
- 境界処理: クロスフェード0.5s、境界±1.0sを mask_eval=0。truth/har 集計時に除外用。
- U/CCS: U=正規化エントロピー、CCS=1−内積(p_t,p_{t-1}) を 4クラス確率で算出。EMA α=0.2 を併記。

## 生成コマンド
```bash
# 依存: .venv_mhealth310 (python3.10), tensorflow-macos==2.15.0, pandas
.venv_mhealth310/bin/python scripts/generate_mhealth_synthetic_sessions.py \
  --sessions-per-seed 1 \
  --train-subjects 1 2 3 4 5 6 7 8 \
  --test-subjects 9 10 \
  --seeds 0 1 2 \
  --sim-threshold 0.95
```

## 出力ファイル（sessions/）
- `*_sensor.csv` : time_s, acc_xyz(z-score), truth_label4, mask_eval
- `*_truth100ms.csv` : 100ms truth列（mask_eval付き）
- `*_script.csv` : 断片の出所（subject, start/end, reuse回数）
- `*_har.csv` : HAR推論ログ（p0..p3, y_hat, U/U_ema, CCS/CCS_ema, mask_eval_window）
- `summary.json` : 生成パラメータとセッション要約

## サマリ（summary.json 抜粋）
- seeds: [0,1,2], sessions_per_seed=1（計3本）
- segments=60, transitions=59, duration≈870.5s（クロスフェードで約29.5s短縮）
- mean_U / mean_CCS
  - seed0_run0: U≈0.233, CCS≈0.235
  - seed1_run0: U≈0.239, CCS≈0.245
  - seed2_run0: U≈0.262, CCS≈0.260

## 留意点
- 実長を15分ぴったりにする場合はクロスフェード長を短縮するか、セグメント数を増やす必要あり（現状は0.5s重ねで短縮）。
- mask_eval が 0 の区間（境界±1s）は TL/Pout 集計から除外する想定。
