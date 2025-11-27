# Phase0-1 → Phase1 ハンドオーバー（レター執筆向け・次AIへの指示）
更新日: 2025-11-26  
目的: Phase0-1での意思決定／要件調整／現状の到達点を整理し、Phase1担当AIがレター執筆と実験を継続できるようにする。

## 1. 背景とゴール
- ゴール: 「3軸の小型HAR + U/S/CCS で adv interval を動的制御し、固定100msより平均電流を5–10%削減しつつ Pout/TL を劣化させない」ことを実機で示す。
- レター論文は docs/paper 配下で執筆。BLE設計・非理想スキャン・制御戦略の考察は既存リサーチノートに集約。

## 2. 要件・優先度（調整済み）
- HAR/TinyML 必須: 4c BAcc ≥ 0.80（MUST）、Stationary↔Loc誤り ≤10%（MUST）。F1目標は 0.80–0.85 に柔軟化（当初0.85必須は厳しすぎと判断）。
- キャリブレーション: ECE(4c) 目標 0.05（0.05–0.10 なら注記の上可）、Unknown率 5–15%。
- TinyML: t_inf ≤20ms @ESP32-S3、Arena ≤64–80KB、TFLiteサイズ目標22KB（多少の超過は理由付きで可）。
- BLE KPI: 平均電流 5–10% 改善 vs 100ms、Pout(1s)+1pt以内、TL p95 +10%以内、再現性±5%。

## 3. モデル現状
- A0（参照）: 3軸 acc.v1, params 63,180, TFLite 92,768B。fold90 test: 12c BAcc 0.828 / 4c BAcc 0.960 / 4c F1 0.7345 / ECE≈0.092 / Unknown≈4.35%。PT↔TFLite: 0.98 / MAE 0.0277。
- A_tiny（現行 v2_tiny, stem32/dw48-64/FC64, dropout0.2）: fold90 test: 12c BAcc 0.858 / 4c BAcc 0.730 / 4c F1 0.728（4c未達）。TFLite未生成/未測定。
- 課題: fold90特有の4c性能低下。TFLiteサイズ・FLOPs・Reliability図・方向別混同行列が未取得。

## 4. 次AIへの最優先TODO（Phase1開始前）
1) A_tiny改良 or 代替幅の検討  
   - 4c BAcc ≥0.80・Stationary誤り≤10%を満たすまで微調整（層/幅/FC/epoch）。fold90で固定条件。  
   - 4c F1は 0.80–0.85 で現実ライン設定（A0が0.734）。
2) 量子化・TFLite計測  
   - PTQ int8（rep_data.npy）→ TFLiteサイズ実測、PT↔TFLite一致率/MAE取得。  
   - TFLite出力で τ/θ_low/high を再キャリブ。Reliability図と4c混同行列（方向別誤り）を生成。  
   - FLOPs、モデルパラメータ精算、TFLite SHA256記録。
3) ESP32-S3 実測  
   - t_inf（avg/p95, 1000回, esp-nn有無明記）、Arena最小/推奨を測定。  
4) BLE実験設計・実施  
   - Policy: ACTIVE(100ms)/UNCERTAIN(500ms)/QUIET(2000ms), θ_low/high, ヒステリシス, min_stay=2s, max_rate=1Hz, fallback=1000ms。  
   - 条件: 固定{100,500,1000,2000} + 不確実度（A_tiny）× 環境E1/E2 × ≥3反復。  
   - ログ: TX(CCS/U/S/adv_interval), TXSD(ΔE/adv, avg current), RX(Pout 1/2/3s, TL p50/p95)。  
   - KPI判定を表にまとめる。
5) レター執筆  
   - 仕様書 `har/001/docs/A_tiny_paper_spec_acm_ieee.md` をベースに、docs/paper のインデックスとリサーチノートを参照。  
   - 参考図表: モデルレイヤ表、4c混同行列、Reliability図、BLE状態遷移図、総合サマリ表（HAR/Calibration/TinyML/BLE）。

## 5. 重要な意思決定（履歴）
- 要件緩和: 4c F1 必須0.85→現実ライン0.80–0.85、サイズ22KBは目標（理由付き超過可）。  
- 評価軸: BLE制御に直結する4c/Stationary誤りを最優先、12cは監視レベル。  
- CCS定義: conf=max_prob, CCS=0.7*conf+0.3*S、θ_low/highは再キャリブ前提（旧0.40/0.70）。  
- ポリシー: ACTIVE/UNCERTAIN/QUIET 3状態、ヒステリシス±0.05, min_stay=2s, max_rate=1Hz, fallback=1000ms。  
- 非理想スキャン・KPI考察は docs/paper のリサーチノートを正にする（har/配下には書かない）。

## 6. 参照パス（主要）
- 仕様: `har/001/docs/A_tiny_paper_spec_acm_ieee.md`
- Tiny実験: `har/004/configs/phase0-1.acc.v2_tiny.yaml`, `har/004/tools/train_phase0-1_tiny.py`, `har/004/runs/phase0-1-acc-tiny/fold90/metrics.json`
- A0: `har/001/docs/A0_acc_v1_baseline_summary.md`, `har/004/runs/phase0-1-acc/fold90/metrics.json`, `har/004/export/acc_v1_keras/manifest.json`
- 分割: `docs/フェーズ0-1/splits_subject90.yaml`
- BLE要件: `docs/フェーズ1/要件定義.md`
- リサーチノート（考察枠）: `docs/paper/BLE非理想スキャン_RL最適化_リサーチノート.md`, `docs/paper/literature_review_ble_dynamic_adv.md`, `docs/paper/TinyML制約付き学習_リサーチノート.md`, `docs/paper/不確実性駆動送信制御_リサーチノート.md`
- インデックス: `docs/paper/index.md`

## 7. 未完タスク（明示）
- A_tiny: 4c性能回復、TFLite生成/誤差/サイズ、FLOPs算出、Reliability図、4c混同行列（方向別）、τ/θ再キャリブ。
- ESP32: t_inf・Arena計測（esp-nn有/無明記）。
- BLE実験: 条件別 KPI 表作成（省電力/品質/再現性）。

## 8. 注意（編集禁止領域）
- `docs/フェーズ0-1/` はマスター（変更禁止）。参照のみ。
- BLE KPI・非理想スキャンの考察は `docs/paper` 側に集約し、har/ 配下には書かない。
