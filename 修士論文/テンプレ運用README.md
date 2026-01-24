# テンプレ運用README（構成切替と編集運用）

## 1. 目的
- 構成Aと構成Bの切替手順と編集ルールを明文化する。
- 章構成の切替と本文修正の混乱を避ける。

## 2. 構成Aと構成Bの概要
### 構成A（従来構成）
- 章の並びは `chapters/_order_a.tex` に定義する。
- `main.tex` から `\input{chapters/_order_a}` を読み込む。

### 構成B（実験中心構成）
- 章の並びは `chapters/_order_b.tex` に定義する。
- 実験章は `chapters/ch5_experiments.tex` に集約し，個別実験は `\input{...}` で読み込む。

## 3. 構成の切替手順
1. `修士論文/main.tex` の `\thesisstructure` を切り替える。
   - `\newcommand{\thesisstructure}{a}` または `b`
2. `main.tex` の `\input{chapters/_order_\thesisstructure}` により構成が切り替わる。

## 4. 章の追加・移動ルール
- 新規章は `chapters/chXX_*.tex` を作成し，必ず `\chapter{...}` と `\label{ch:...}` を付ける。
- 参照は `\chapref{ch:...}` で統一し，ラベルの重複を避ける。
- 参照先を変更した場合，本文の参照ラベルも合わせて更新する。

## 5. 構成Bの編集ルール
- 実験の追加は `chapters/ch5_experiments.tex` に `\section` 単位で追加し，本文は別ファイル化して `\input{...}` する。
- 章内の節数は原則7以内，必要なら10以内を上限とする。
- 章全体の考察は別章（考察章）に集約し，個別実験内の考察は簡潔にまとめる。

## 6. プロンプトルール（AI依頼時の指示）
- 目的，構成（A/B），対象ファイルを明示する。
- 変更範囲は指定されたファイルのみとする。
- である調，句読点「，」「．」，用語は「アドバタイジング」に統一する。
- 強調目的の太字導入句は使わず，完全な文章で記述する。
- 章節番号と参照ラベルの整合を必ず確認する。

## 7. 切替後の確認手順
1. `修士論文` 配下でビルドする。
   - 例：`latexmk -g -lualatex -interaction=nonstopmode -halt-on-error main.tex`
2. `??` 参照や警告が出た場合，該当ラベルを修正する。
3. 目次の章並び，章扉，図表参照の整合を確認する。

## 8. 既知のラベル注意
- 構成Bでは評価章が `ch:experiments` になるため，`ch:evaluation` を参照している場合は更新が必要になる。
