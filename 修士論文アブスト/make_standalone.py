#!/usr/bin/env python3
"""
修士論文アブストを単一ファイル化するスクリプト
- meta.tex を統合
- 参考文献を \begin{thebibliography} に手動変換
- 図を代替テキスト（[図: ...]）に置き換え
"""

import re
import os

def read_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def get_manual_bibliography():
    """手動で thebibliography を生成（確実性のためハードコード）"""
    return r"""\begin{thebibliography}{99}
\small
\bibitem{BluetoothSIGCore52} Bluetooth SIG, ``Core Specification 5.2,'' https://www.bluetooth.com/specifications/specs/core-specification-5-2/, accessed 2023-09-11.

\bibitem{Luo2021BLENeighborDiscoverySurvey} B. Luo, Y. Yao, Z. Sun, ``Performance analysis models of BLE neighbor discovery: a survey,'' IEEE Internet of Things Journal, vol.~8, no.~11, pp.~8734--8746, 2021.

\bibitem{Schrader2016BLEPower} R. Schrader et al., ``Advertising power consumption of Bluetooth Low Energy systems,'' Proc. 2016 3rd International Symposium on Wireless Systems Within the Conferences on Intelligent Data Acquisition and Advanced Computing Systems (IDAACS-SWS), pp.~62--68, 2016.
\end{thebibliography}"""

def convert_figure_to_alt(tex_content):
    """figure環境を代替テキストに変換"""
    # minipageを含む複雑なfigureを処理
    complex_pattern = r'\\begin\{figure\}(\[.*?\])?\s*\\centering\s*\\begin\{minipage\}.*?\\includegraphics.*?\\end\{minipage\}.*?\\caption\{(.*?)\}\\label\{(.*?)\}\\end\{figure\}'
    
    def replace_complex_fig(match):
        caption = match.group(2)
        label = match.group(3)
        result = "\\\\begin{center}\\\\fbox{\\\\parbox{0.8\\\\linewidth}{\\\\centering\\\\vspace{8mm}[図: " + caption + "]\\\\vspace{8mm}}}\\\\end{center}\\\\vspace{-2mm}\\\\captionof{figure}{" + caption + "}\\\\label{" + label + "}\\\\vspace{2mm}"
        return result
    
    # 複雑なパターンを先に処理
    tex_content = re.sub(complex_pattern, replace_complex_fig, tex_content, flags=re.DOTALL)
    
    return tex_content

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. main.tex を読み込み
    main_tex = read_file(os.path.join(base_dir, 'main.tex'))
    
    # 2. meta.tex を読み込んで統合
    meta_tex = read_file(os.path.join(base_dir, 'meta.tex'))
    main_tex = main_tex.replace('\\input{meta}', meta_tex)
    
    # 3. 図を代替テキストに変換
    # \usepackage{caption} を確認（\captionof用）
    if 'capt-of' not in main_tex:
        main_tex = main_tex.replace('\\usepackage{caption}', '\\usepackage{caption}\n\\usepackage{capt-of}')
    
    main_tex = convert_figure_to_alt(main_tex)
    
    # 4. 参考文献を thebibliography に置き換え
    bib_env = get_manual_bibliography()
    
    # \printbibliography[heading=none] を置き換え（正規表現の特殊文字を回避）
    main_tex = main_tex.replace(r'\\printbibliography[heading=none]', bib_env)
    
    # \addbibresource 行を削除
    main_tex = re.sub(r'\\\\addbibresource\{.*?\}\n', '', main_tex)
    
    # \usepackage{biblatex} を削除
    main_tex = re.sub(r'\\\\usepackage\[.*?\]\{biblatex\}\n', '', main_tex)
    
    # \DeclareCiteCommand 等のbiblatex固有コマンドを削除
    main_tex = re.sub(r'\\\\DeclareCiteCommand\{\\\\scite\}.*?\{\}\s*\\\\{\}\s*\\\\{\}\n', '', main_tex, flags=re.DOTALL)
    
    # \scite を \cite に変更
    main_tex = main_tex.replace('\\scite', '\\cite')
    
    # 5. 出力
    output_path = os.path.join(base_dir, 'main_standalone.tex')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(main_tex)
    
    print(f"単一ファイル版を生成しました: {output_path}")
    print("このファイルは図ファイル（figures/）と .bib ファイルなしでコンパイル可能です。")
    print("図は代替テキスト（[図: ...]）として表示されます。")

if __name__ == '__main__':
    main()
