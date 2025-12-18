# results/final（成果物の最終置き場）

目的: 実験全体の「最終的に参照される図表・表・メモ」を **1か所に集約**し、論文化/スライド化/再解析を楽にする。

## ルール（最重要）

- **元データはここに置かない**（`data/` が原本）。ここは「派生物（図表・集計）」のみ。
- 生成物は **必ず生成元（入力run/スクリプト/コマンド/生成日時）を `manifest.md` に残す**。
- 生成元（オリジナル）は基本的に `results/`, `uccs_*/metrics`, `uccs_*/plots` に残し、`results/final` は「固定版（提出物/貼り付け用）」として扱う。
- ファイル名は **用途が分かる**ように付ける（例: `fig_main_scan70_scan90.svg`）。

## 構成

- `results/final/fig/` : 最終図（SVG/PDF推奨）
- `results/final/tab/` : 最終表（CSV/Markdown/TeX）
- `results/final/meta/` : 生成メタ（入力run、バージョン、メモ）
- `results/final/meta/rx_log_schema.md` : 受信ログ（アプリ）CSV仕様（既存解析互換）
- `results/final/build.sh` : 図表を一括生成（入力runを環境変数で指定）
- `results/final/manifest.md` : 何がどこから生成されたかの台帳

## 一括生成

```bash
bash results/final/build.sh
```

入力runの切替は `build.sh` 冒頭の環境変数を参照。
