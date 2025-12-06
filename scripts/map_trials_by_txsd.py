"""Map TXSD trial files to session/subject and interval using only TXSD logs.

Assumptions:
- TX rotates sessions 01-10 in order; subject = session index.
- Each trial logs a summary line:
    # summary, ms_total=..., adv_count=..., ...
- adv_count is expected to be 300; interval is inferred as ms_total/adv_count.
- Files are named trial_XXX_on.csv and chronological order matches trial order.

This is useful when TX serial logs are not available.

Usage:
  python scripts/map_trials_by_txsd.py \
      --txsd-dir data/1202配線変更後/Mode_C_2_02''''/TX \
      --output mapping_txsd.csv
"""

import argparse
import csv
from pathlib import Path
from typing import List, Tuple, Dict


def infer_interval(ms_total: float, adv_count: int) -> float:
    if adv_count <= 0:
        return 0.0
    return ms_total / adv_count


def bucket_interval(iv_ms: float) -> int:
    # simple bucketing around expected values
    if 70 <= iv_ms <= 150:
        return 100
    if 350 <= iv_ms <= 650:
        return 500
    if 750 <= iv_ms <= 1250:
        return 1000
    if 1500 <= iv_ms <= 2300:
        return 2000
    return 0


def parse_txsd_summary(path: Path) -> Tuple[float, int]:
    ms_total = 0.0
    adv_count = 0
    for line in path.read_text(errors="ignore").splitlines():
        if line.startswith("# summary"):
            parts = line.split(",")
            for p in parts:
                if "ms_total" in p:
                    try:
                        ms_total = float(p.split("=")[1])
                    except Exception:
                        pass
                if "adv_count" in p:
                    try:
                        adv_count = int(p.split("=")[1])
                    except Exception:
                        pass
            break
    return ms_total, adv_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--txsd-dir", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    files = sorted(args.txsd_dir.glob("trial_*_on.csv"))
    if not files:
        raise SystemExit("No TXSD trials found.")

    rows: List[Dict[str, str]] = []
    for idx, f in enumerate(files):
        ms_total, adv_count = parse_txsd_summary(f)
        iv_est = infer_interval(ms_total, adv_count)
        bucket = bucket_interval(iv_est)
        session_idx = (idx % 10) + 1  # 1..10 repeating
        rows.append({
            "order": idx + 1,
            "trial": f.name,
            "trial_path": str(f),
            "session": f"{session_idx:02d}",
            "subject": f"subject{session_idx:02d}",
            "interval_ms_est": f"{iv_est:.2f}",
            "interval_bucket_ms": bucket if bucket else "",
            "ms_total": f"{ms_total:.0f}",
            "adv_count": adv_count,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
