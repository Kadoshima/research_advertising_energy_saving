# Phase1 E2 / CCS vs Baseline 分析依頼パッケージ

## 0) 目的（最短で論文化につなげる）
- 最短の論文主張を補強するための分析を実施する
- 実験装置は使わず、PC上の既存データのみで完結
- ゴールは「トレードオフ成立＋Phase2必然」を数値/図で支えること

## 1) 必達ゴール（分析アウトプット）

### A. 差分の不確かさ（CI/効果量）
- 対象: CCS FIXED100 / CCS FIXED2000
- 指標:
  - Avg Current
  - Pout(2s)
  - TL p95
- bootstrap CI（Nが小さいため必須）
- 形式: Markdown表 + CSV

### B. 論文図（1枚）
- 横軸 = Avg Current
- 縦軸 = Pout(2s)（または TL p95）
- 3点（FIXED100 / CCS / FIXED2000）＋CI
- 形式: PNG（論文図用）
- 図タイトル例: E2 Tradeoff: Avg Current vs Pout(2s)

### C. Tail分析（最小）
- CCSのPout(2s)に寄与した試行のランキング
- 重尾支配を示す根拠メモ（数行でOK）

## 2) 使用するデータ（固定）

### データソース
- CCS結果: `results/phase1_e2_ccs_2026-01-22_v03.md`
- Baseline結果: `results/phase1_e2_baseline_2026-01-22_v01.md`

### 補助参照（定義の正本）
- 指標定義: `docs/metrics_definition.md`

### 比較表（すでに整理済）
- `docs/フェーズ1/phase1_e2_compare_2026-01-22/README.md`

## 3) 絶対にやってはいけないこと（禁止事項）
- 生データ改変（`data/` 配下のCSVは触らない）
- 数値の捏造/補完（不足分を推測で埋めない）
- 固定閾値の勝手な変更（Pout閾値などは必ず定義に従う）
- 指標定義の自己流変更（必ず `docs/metrics_definition.md` に準拠）

## 4) 分析ルール
- 数値は必ず参照元ファイルパスを明記
- 可能なら pertrial から bootstrap
- Nが小さい場合は「参考値」と明記
- 出力は Markdown + CSV + PNG を基本

## 5) 実際の作業（他AIがやるべき内容）

### Task 1: CI（bootstrap）
- 入力: pertrial（`results/*.md` の表を抽出）
- 出力:
  - `results/phase1_e2_ci_summary.md`
  - `results/phase1_e2_ci_summary.csv`

### Task 2: 図の生成
- 出力:
  - `results/phase1_e2_tradeoff_plot.png`

### Task 3: Tailの簡易分析
- CCS試行ごとに Pout(2s) or TL p95 を並べ、
  「どの試行が支配しているか」を簡潔に記述
- 出力:
  - `results/phase1_e2_tail_note.md`

## 6) 成功判定（PMが見るポイント）
- CIが出ていること
- 図が1枚で理解できること
- 「CCSは中間解」「tailが支配的」を定量的に裏付けられていること

## 7) 次フェーズ（強い主張を狙う場合）
- 追加実験は不要（今回は分析だけ）
- もし追試するなら 遷移直後100msガードで Pout(2s) 改善を確認

## 8) 今回の結論（他AIに渡す短文）
> E2では CCS は FIXED100 より省電力だが、Pout(2s)/TL p95 が悪化し、
> FIXED2000 と同程度の尾部を持つ。
> ただし中央値TLは改善しており、「Pareto中間解」＋「tailaware制約が必要」という
> Phase2の必然性を示せる。
