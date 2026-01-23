# 修論テンプレ比較（2026-01-23）

## 目的/範囲
- 大学配布の修論テンプレ（Word + LaTeX）と現在の 修士論文/ の体裁を比較し、確定ルールとして明文化する。
- 体裁の根拠は配布テンプレと master_thesis_cls.cls を優先し、差分は明記する。

## 入力データ（出所/版/SHA256）
- 配布テンプレ（Word）
  - C:\Users\tp240\Documents\修論\6576adc236339900688dc16f\01-02-graduate-engineering-2025m.docx
    - SHA256: 4523C4496BFD5D33E66A72967578AAD9C26E20BB2BFFA386147B98B49CA5E1D0
  - C:\Users\tp240\Documents\修論\6576adc236339900688dc16f\01-03-graduate-engineering-2025m.docx
    - SHA256: 61E50EEF251E9BB0B36DCEDA745969AD342B5175B60DF8E2CF201EBA371955D3
  - C:\Users\tp240\Documents\修論\6576adc236339900688dc16f\01-04-graduate-engineering-m.docx
    - SHA256: FB7390B8F6C465635801FC922FCE5A3083946DF0C0B6AE6D0A638FE39D67C536
- 配布テンプレ（LaTeX）
  - C:\Users\tp240\Documents\修論\6576adc236339900688dc16f\Masters_Thesis\master_thesis_cls.cls
    - SHA256: 6DA67040C1B9BEEEE5A4FB4F3957EF56254B2111727821BE2BC24FE9E8330DB3
  - C:\Users\tp240\Documents\修論\6576adc236339900688dc16f\Masters_Thesis\Thesis.tex
    - SHA256: D24B26CA4A241A62DA33CD542543B9FF4CD995F947B748C985CD561B651FF87D

## 抽出ルール（要点）
- 本文領域: 160mm x 232mm
- 余白: 左右 25mm
- フォント: 12pt、行送り 18pt
- ヘッダーなし、フッター右下ページ番号
- 表紙: 外枠の太線が必要、年度は漢数字
- 背表紙: 縦書き（英字/元素記号は横向き）
- 要旨: 40字 x 30行、1ページ以内。見出し「論文要旨」に下線は不要

## 出力物（生成日/生成スクリプト）
- 解析メモ: 修士論文/WRITING_RULES.md
- 反映先: 修士論文/chubuthesis.sty
- 生成日: 2026-01-23
- 抽出スクリプト: python による docx の word/document.xml 抽出

## 再現手順（コマンド）
`powershell
python - <<'PY'
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

root = Path(r'C:\Users\tp240\Documents\修論\6576adc236339900688dc16f')
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

def extract(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read('word/document.xml')
    tree = ET.fromstring(xml)
    return '\n'.join([n.text for n in tree.findall('.//w:t', ns) if n.text])

for name in ['01-02-graduate-engineering-2025m.docx','01-03-graduate-engineering-2025m.docx','01-04-graduate-engineering-m.docx']:
    print('====', name, '====')
    print(extract(root / name))
PY
`

## 状態
- draft

## 関連リンク
- 修士論文/WRITING_RULES.md
- 修士論文/chubuthesis.sty

## 更新履歴（YYYY-MM-DD）
- 2026-01-23 初版（配布テンプレの抽出・要点整理）
