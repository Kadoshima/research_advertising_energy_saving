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

### Overleaf
- Compiler: **LuaLaTeX**
- Bibliography: **Biber**（biblatex使用）

---

## 3) 図の置き場

- `figures/` に入れて、拡張子なしで呼ぶのが楽です（PDF/PNG両対応）
```tex
\includegraphics[width=0.9\linewidth]{figures/fig_system_overview}
```

---

## 4) 引用の書き方

このテンプレートは biblatex です。

- 普通の引用（カンマ区切り）：`\cite{ref1,ref2}` → `[1,2]`
- 括弧を分けたい場合：`\scite{ref1,ref2}` → `[1][2]`

---

## 5) 体裁を変えたいとき

- 余白：`chubuthesis.sty` の `geometry` を編集
- 図表キャプション：`chubuthesis.sty` の `caption` 設定を編集
- 表紙/要旨ページ：`meta.tex`（値）と `chubuthesis.sty`（配置）を編集
- ページ番号（下右統一）：`chubuthesis.sty` の `fancyhdr` 設定を編集
- 章見出し（章扉の中央寄せ等）：`chubuthesis.sty` の `titlesec` 設定を編集
- 参考文献のURL表示：`chubuthesis.sty` の `biblatex` まわりを編集
