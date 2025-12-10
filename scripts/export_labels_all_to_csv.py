#!/usr/bin/env python3
"""
Export labels_all.h (subjectXX arrays) to per-subject CSV files (idx,label).

Usage:
  python scripts/export_labels_all_to_csv.py \
    --header esp32_firmware/1202/modeC2prime_tx/labels_all.h \
    --out-dir data/1210_modeC2prime_fixed/truth
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


def parse_header(path: Path) -> dict[str, list[int]]:
    text = path.read_text()
    # pattern: static const uint8_t subject01[] = { ... };
    pattern = re.compile(r"static\s+const\s+uint8_t\s+subject(\d+)\[\]\s*=\s*\{([^}]*)\};", re.S)
    subjects: dict[str, list[int]] = {}
    for m in pattern.finditer(text):
        sid = m.group(1).zfill(2)
        body = m.group(2)
        # remove comments/spaces/newlines
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
        nums = []
        for tok in body.replace("\n", " ").split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                nums.append(int(tok))
            except ValueError:
                pass
        subjects[sid] = nums
    return subjects


def main() -> None:
    ap = argparse.ArgumentParser(description="Export labels_all.h subjects to CSV (idx,label)")
    ap.add_argument("--header", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()

    subjects = parse_header(args.header)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for sid, seq in subjects.items():
        out = args.out_dir / f"subject{sid}.csv"
        with out.open("w") as f:
            f.write("idx,label\n")
            for i, v in enumerate(seq[:6352]):  # clip to EFFECTIVE_LEN used by TX flash
                f.write(f"{i},{v}\n")
        print(f"[INFO] wrote {out} len={len(seq)}")


if __name__ == "__main__":
    main()
