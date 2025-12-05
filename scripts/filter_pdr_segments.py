"""Filter segmented PDR CSV to keep only expected interval buckets.

Usage:
  python scripts/filter_pdr_segments.py \
      --input data/1202配線変更後/Mode_C_2_02/pdr_segmented.csv \
      --output data/1202配線変更後/Mode_C_2_02/pdr_segmented_filtered.csv

Buckets (interval_ms_est) are mapped as:
  - 70–150  -> 100
  - 350–650 -> 500
  - 750–1250 -> 1000
  - 1500–2300 -> 2000
Rows outside these ranges are excluded.
"""

import argparse
import csv
from pathlib import Path
from typing import Optional


def bucket_interval(iv: float) -> Optional[int]:
    if 70 <= iv <= 150:
        return 100
    if 350 <= iv <= 650:
        return 500
    if 750 <= iv <= 1250:
        return 1000
    if 1500 <= iv <= 2300:
        return 2000
    return None


def main():
    ap = argparse.ArgumentParser(description="Filter segmented PDR CSV by interval buckets.")
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    kept = []
    dropped = []
    with args.input.open() as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    for row in rows:
        iv = float(row["interval_ms_est"])
        bucket = bucket_interval(iv)
        if bucket is None:
            dropped.append(row)
            continue
        row["interval_bucket_ms"] = str(bucket)
        kept.append(row)

    fieldnames = list(rows[0].keys()) + ["interval_bucket_ms"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"kept={len(kept)} dropped={len(dropped)} -> {args.output}")
    if dropped:
        print("dropped intervals:", sorted({row['interval_ms_est'] for row in dropped}))


if __name__ == "__main__":
    main()
