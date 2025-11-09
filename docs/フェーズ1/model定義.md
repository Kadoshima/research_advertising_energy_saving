# フェーズ1 モデル定義（確定版）

本章は Phase‑1 におけるオンデバイス HAR 推論モデルの確定仕様を示す。無線（TL/Pout/電力）が主目的であるため、モデルは軽量・安定・再現可能性を最優先とする。

## 1. 目的と適用範囲
- 目的: Phase‑1 のポリシ評価に必要な U/S/CCS を0.5 s周期で安定供給する。
- 適用: ESP32‑S3/C3 + TFLM int8、IMU 50 Hz／1.0 s窓／50%重畳。

## 2. 実装制約（HW/Runtime）
- TFLM int8、S3 は `esp‑nn` 最適化推奨。
- 制約: Tensor Arena ≤ 80 KB（開始 64 KB 目安）、Flash ≤ 200 KB、FLOPs ≤ 8 M、t_inf ≤ 20 ms（1窓）。

## 3. 標準プロファイル（既定）: DS‑CNN（1.0 s, 6ch）
- 入力: 50×6（1.0 s/50%重畳）。前処理: z‑score、（任意）重力除去。
- 構成（例）:
  - DWConv1D(k=5, s=1) → PWConv(16)
  - DWConv1D(k=5, dilation=2) → PWConv(24)
  - GAP → Dense(K) → Softmax（K=クラス数）
- 目安: ~1k params／~0.03 M FLOPs／~5 ms（S3@240 MHz）。Arena ~48 KB 未満。
- 用途: 省リソース・高安定の既定実装。Phase‑1 の全条件で使用可。

## 4. 拡張プロファイル（任意）: DS‑CNN++（マルチスケール＋早期出口）
- 目的: 遷移 TL への追従と平均遅延・電力の Pareto 改善。
- 入力枝: A=50×6（1.0 s）, B=25×6（0.5 s, 2倍ストライドサンプリング）。
- 各枝: A: DW5→PW16→DW5(d=2)→PW24→GAP／B: DW3→PW12→DW3(d=2)→PW16→GAP。
- 融合: Concat(A_GAP, B_GAP)。
- Exit‑0（任意）: Dense(K)→Softmax（条件: `max_softmax≥0.90` かつ 温度スケーリング後≥0.85 で確定）。
- 最終: 小 Dense（例:16）→ Dense(K)→Softmax。
- 目安: 9–12k params／3–5 M FLOPs／8–12 ms（Exit‑0 命中時 3–5 ms）。Arena 48–64 KB。
- 既定: OFF（A/B 評価で ON 可）。

## 5. 代替プロファイル（任意）: MicroConv‑GRU（DWConv→GRU16）
- 目安: 12–18k params／6–8 M FLOPs／14–20 ms。
- 用途: 連続動作の平滑性を重視する評価に限定。

## 6. 学習・量子化（共通）
- 最適化: Adam, lr=1e‑3（Plateau 0.5×）、Weight Decay 1e‑4、早停=patience 10／max 120 epoch。
- 増強: 小回転、時軸伸縮(±10%)、ノイズ注入、サンプルドロップ(5%)、左右ミラー。
- 不均衡: 重み付き CE または Focal(γ=1–2)。
- 検証: 被験者分離（subject‑wise）K‑fold。
- QAT: FP32 収束後 8–15 epoch。Conv は per‑channel 量子化。
- 信頼度校正: 温度スケーリング（valid で最適 T）→ CCS/Exit 判定に適用。

## 7. エクスポート・デプロイ
- 生成物: 量子化 `.tflite`（int8）＋代表データ。C 配列化して組込み。
- 計測: `esp_timer` で t_inf を 1000 反復測定。Arena 実測／モデルハッシュをログ。
- 推奨設定: Arena=64 KB 開始、S3 は `esp‑nn` 有効化。

## 8. モデルID・命名と記録
- 命名例: `RHT_DSCNN_int8_v{MAJOR.MINOR}`／`RHT_DSCNNpp_int8_v{...}`。
- 記録: `model_id`, `commit_hash`, `q_scheme`, `arena_kb`, `t_inf_ms@S3/C3` を Runbook/レポートへ併記。

## 9. 受入基準（モデル観点）
- 標準（DS‑CNN）: `t_inf ≤ 20 ms`、`Arena ≤ 80 KB`、未サポート Op なし。
- 早期出口 ON（任意）: OFF 比で平均 `t_inf ≥ 20%` 短縮、F1 低下 `≤ 1.0 pt`、Pout(1 s)/TL p95 の劣化は受入基準内。

> 備考: Phase‑1 の主目的は無線（TL/Pout/電力）の評価。モデル比較はポリシ有効性の補助に留める。