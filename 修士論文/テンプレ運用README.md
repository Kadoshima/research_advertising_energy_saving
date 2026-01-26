# テンプレ運用README（構成A/B切替）

本READMEは，修士論文の構成A/Bを切り替えるための運用手順と，構成編集時の注意点をまとめる．

## 1. 構成A/Bの概要
- 構成A：現行の章構成（背景→提案→計測→評価→結論）を維持する構成．
- 構成B：実験中心に整理する構成．実験を1章に集約し，目的・条件・結果・考察を実験単位で記述する．

具体的な章の順序は `chapters/_order_a.tex` / `chapters/_order_b.tex` に定義する．

## 2. 切替方法（main.tex）
`main.tex` の `\thesisstructure` を `A` または `B` に設定する．

```tex
\newcommand{\thesisstructure}{A} % A または B
...
\input{chapters/_order_\thesisstructure}
```

## 3. 章順の管理（_order_A.tex / _order_B.tex）
- `chapters/_order_a.tex`：構成Aの章順
- `chapters/_order_b.tex`：構成Bの章順

章順を変更する場合は，`_order_*.tex` の `\input{...}` の順序を調整する．

## 4. 構成Bの編集方針
構成Bでは `chapters/ch5_experiments.tex` を実験章のラッパとして利用する．
- `ch5_experiments.tex` の本文は短い導入のみとし，実験節は `\input{...}` で追加する．
- 各実験ファイルは `\section{...}` で開始し，目的→条件→結果→考察の流れを維持する．

## 5. ビルド
論文ルート（`修士論文/`）で以下を実行する．

```bash
latexmk -g -lualatex -interaction=nonstopmode -halt-on-error main.tex
```

## 6. 編集時のルール（プロンプトルール）
- 内容の事実（数値・実験条件）は変更しない．
- 章節の整理・見出しの統合は行うが，`\label` と `\ref` は保持する．
- 付録に置く資料は本文に移さない（指示がある場合を除く）．
- 文体は「である調」，句読点は「，」「．」に統一する．
- ファイルパスやコード断片は本文から排除し，付録へ回す（必要な場合のみ）．
