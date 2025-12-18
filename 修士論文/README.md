# 修士論文 LaTeX テンプレート（LuaLaTeX）

Word→PDF の修論の体裁を参考に、表紙・要旨・目次・本文・図表キャプション・参考文献を一式で用意したテンプレートです。

---

## 1) まず編集するファイル

- `meta.tex`（タイトル・氏名など）
- `frontmatter/abstract.tex`（要旨）
- `chapters/*.tex`（本文）
- `references.bib`（参考文献）

---

## 2) コンパイル方法（LuaLaTeX推奨）

### ローカル（TeX Live）
```bash
latexmk main.tex
```

生成物は `build/main.pdf` に出力されます（ビルド用の一時ファイル/キャッシュも `build/` 配下）。
ページ数は `build/main.log` の `Output written on main.pdf (XX pages, ...)` で確認できます。

### Overleaf
- Compiler: **LuaLaTeX**
- Bibliography: **Biber**（biblatex使用）

---

## 3) 図の置き場

- `figures/` に入れて、拡張子なしで呼ぶのが楽です（PDF/PNG両対応）
```tex
\includegraphics[width=0.9\linewidth]{figures/fig_system_overview}
```

- 写真も提出用には `figures/` に置く（元データはリポジトリ直下の `image/` に保存し、提出用は向き補正・メタデータ除去・リサイズした派生物を `figures/` へ置く）。

---

## 4) 引用の書き方

このテンプレートは biblatex です。

- 普通の引用（カンマ区切り）：`\cite{ref1,ref2}` → `[1,2]`
- 括弧を分けたい場合：`\scite{ref1,ref2}` → `[1][2]`

---

## 5) 大学体裁に寄せる追加ルール（固定）

このテンプレートは「先輩修論（大学方針の体裁）」に寄せるため、以下を**ルールとして固定**する。

- ページ番号：目次はローマ数字（i〜）、本文（第1章）からアラビア数字（1〜）
- ページ番号の位置：全ページ下右（章扉など `plain` も同じ）
- 章扉：各章は `\chapter{...}\clearpage` で「章タイトルだけのページ」を挟む（`chapters/*.tex` 側で徹底）
- 章見出し：中央寄せ・太字にしない（日本語太字のゴシック化を避ける）
- 目次：`section` まで（`tocdepth=1`）
- 図表キャプション：`図 4-1 タイトル` / `表 4-1 タイトル`（章-連番、区切りはスペース）
- 参照：章番号・節番号を手で書かない（`\secref{...}` / `\figref{...}` / `\tabref{...}` を使う）
- 参考文献：URLは載せるが `url:` / `visited on` は出さない（体裁側で抑制）

---

## 6) 体裁を変えたいとき

- 余白：`chubuthesis.sty` の `geometry` を編集
- 図表キャプション：`chubuthesis.sty` の `caption` 設定を編集
- 表紙/要旨ページ：`meta.tex`（値）と `chubuthesis.sty`（配置）を編集
- ページ番号（下右統一）：`chubuthesis.sty` の `fancyhdr` 設定を編集
- 章見出し（章扉の中央寄せ等）：`chubuthesis.sty` の `titlesec` 設定を編集
- 参考文献のURL表示：`chubuthesis.sty` の `biblatex` まわりを編集

---

## 7) Repomix（共有用パック）

他のAIに共有して状況を再現しやすくするため、修論（LaTeX）＋主要ログ＋実機評価の集計結果を `repomix_thesis_bundle_light.xml` にまとめる（軽量版）。

注:
- `repomix` はテキストファイルのみをパックする（PDF/PNG/JPGなどのバイナリは含まれない）ため、必要に応じて `build/main.pdf` や `uccs_*/plots/*.pdf` を別送する。

```bash
repomix --output repomix_thesis_bundle_light.xml --style xml --parsable-style \
  --compress --remove-comments --remove-empty-lines \
  --include "修士論文/**,logs/worklog_2025-12-17_thesis_setup.txt,logs/worklog_2025-12-17_letter_route.txt,logs/worklog_2025-12-16_letter_route.txt,logs/worklog_2025-12-16_letter_route_continued.txt,logs/worklog_2025-12-15_thesis_setup.txt,uccs_d2_scan90/README.md,uccs_d2_scan90/metrics/**,uccs_d3_scan70/README.md,uccs_d3_scan70/metrics/**,uccs_d4_scan90/README.md,uccs_d4_scan90/metrics/**,uccs_d4b_scan90/README.md,uccs_d4b_scan90/metrics/**" \
  --ignore "docs/**,**/src/**,**/analysis/**,**/plots/**,**/data/**"
```
