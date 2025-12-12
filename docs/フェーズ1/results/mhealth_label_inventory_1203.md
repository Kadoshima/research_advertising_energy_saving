# mHealth ラベル・CCS時系列インベントリ (2025-12-03)

## 概要
- ソース: `data/ccs_sequences/subject*_ccs.csv`（現行ファイルは CCS = 0.6U + 0.4(1−S) 基準で生成済み）。
- Phase 1 の正規定義は **CCS = 0.7 × (1 − U) + 0.3 × S** であるため、正式利用時はこの式で再生成する。
- 件数: 10 被験者, 合計 6,768 サンプル（0.5–1.0s刻み相当）。
- ラベル分布（全体）: `1: 2521`, `0: 2431`, `2: 1816`（ラベルIDの意味は元データの定義に依存）。
- Interval分布（generation_summary.json 集計）: 100ms=1,714, 500ms=630, 2000ms=4,424（合計=6,768）。
- 総時間: 約 6,768 秒（約 112.8 分）。

## 目的と利用
- Mode C2'/D/C3 の「ラベル再生＋固定/可変広告」実験で使う入力列（`t,label,ccs,uncertainty`）。
- HAR ラベルの遅延・ミス率基準線（C2'）と、不確実性駆動・学習ポリシー（D/C3/Phase2）の比較に利用。

## 参考: generation_summary.json 抜粋
- 各 subject のキー: `n_windows`, `duration_s`, `ccs_mean/std`, `interval_distribution`, `n_transitions`。
- interval_distribution は分布準拠グリッドに合わせた（θ_low/θ_high → 100/500/2000ms）静的マッピング結果。
