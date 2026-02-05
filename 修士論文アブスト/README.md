# 修士論文アブスト（2ページ二段組）

本ディレクトリは，修士論文提出時に別途求められる「修論用アブスト（短報形式）」を作成するための作業フォルダである．
大学公式の執筆要領は手元にないため，先輩の方針準拠PDF（TP22004）を事実上の基準として体裁を合わせる．

## 体裁ルール（固定）

- 用紙: A4
- ページ数: 2ページ（超過しない）
- 組版: 二段組（2カラム）
- ページ番号: 出さない
- 先頭（1ページ目上部）の順:
  - 題目（中央）
  - 氏名（学生）＋指導教員名（併記）
  - 所属「中部大学大学院 工学研究科 情報工学専攻」（中央）
- 見出し: `1. はじめに` のように番号付き（section単位）
- 図表: 図は `図 1 ...`，表は `表 1 ...` の通し番号（章番号は付けない）
  - キャプション区切りは「空白」（コロンは使わない）
  - 表キャプションは上，図キャプションは下
- 引用: 本文中は番号参照（例: `[1][2]`），末尾に文献一覧を置く

## ファイル構成

- `main.tex`: 本文（2ページ二段組）
- `meta.tex`: 題目・氏名・所属など（先頭ブロック用）
- `references.bib`: 参考文献（biblatex/biber）
- `figures/`: 図（PDF/PNG/JPG等）。拡張子なしで参照する

## ビルド

```bash
latexmk -lualatex main.tex
```

- 出力: `build/main.pdf`
- 一時ファイル/キャッシュ: `build/` 配下（`latexmkrc` で固定）

## 注意

- 2ページ制約があるため，図は1〜2枚を基本とし，数値は本文で要点を言い切る．
- 本文（修士論文）の体裁ルールは `../修士論文/README.md` に集約する．

## 数値出典（アブスト用）

- 実機（scan90, 遷移期S4, uccs_d4b_scan90）のPout/電力/TL平均/PDR/share100およびfixed100/500比較: `results/final/tab/tab_summary_by_condition.csv`
- 実機（scan70, 遷移期S4, uccs_d3_scan70）のPout/電力/TL平均/PDR/share100およびfixed100/500比較: `results/final/tab/tab_summary_by_condition.csv`
- アブレーション（scan90, S4_ablation_ccs_off vs S4_policy）のPout/TL平均/share100: `results/final/tab/tab_summary_by_condition.csv`
- シミュレーション（E2_actions_500_1000_2000_cold, tau=1.0, epsilon=0.1, methods=oracle/safe_ucb/ucb）: `results/phase2_offline_studies_2026-01-25_v04b/sim_summary.csv`
