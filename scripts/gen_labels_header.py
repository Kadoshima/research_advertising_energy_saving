#!/usr/bin/env python3
"""
CSVからラベル配列(C文字列)を生成し、ヘッダファイルに出力する簡易ツール。

例:
  python3 scripts/gen_labels_header.py \\
    --csv data/esp32_sessions/session_01.csv \\
    --label-col label \\
    --out esp32_firmware/1202/modeC2prime_tx/labels_generated.h

生成されるファイル内容:
  static const char* labels[] = {
    "0",
    "1",
    ...
  };
  static const uint16_t nLabels = N;

TX_ModeC2prime_1202_flash.ino から
  #include "labels_generated.h"
を追加すれば、そのままビルド時に最新のラベル配列を取り込めます。
"""
import argparse
import csv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="入力CSVパス")
    ap.add_argument("--label-col", required=True, help="ラベル列名 (例: label, true_label_4)")
    ap.add_argument("--out", required=True, help="出力ヘッダファイルパス")
    args = ap.parse_args()

    labels = []
    with open(args.csv) as f:
        r = csv.DictReader(f)
        if args.label_col not in r.fieldnames:
            raise SystemExit(f"label-col '{args.label_col}' not found in columns: {r.fieldnames}")
        for row in r:
            labels.append(row[args.label_col])

    with open(args.out, "w") as out:
        out.write(f"// generated from {args.csv}\n")
        out.write("static const char* labels[] = {\n")
        for i, l in enumerate(labels):
            comma = "," if i + 1 < len(labels) else ""
            out.write(f'  "{l}"{comma}\n')
        out.write("};\n")
        out.write(f"static const uint16_t nLabels = {len(labels)};\n")

    print(f"wrote {len(labels)} labels -> {args.out}")


if __name__ == "__main__":
    main()
