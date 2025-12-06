"""Map TXSD trial files to TX session/interval order parsed from TX serial log.

Assumptions:
- TX serial log contains lines like:
    [TX] start trial session=01 interval=100ms labels=...
- TXSD files are named trial_XXX_on.csv in chronological order.
- Session order is 01-10 repeated; subjectは session IDと同一とみなす。

Usage:
  python scripts/map_trials_to_sessions.py \
      --tx-log path/to/tx_serial.log \
      --txsd-dir data/1202配線変更後/Mode_C_2_02''''/TX \
      --output mapping.csv
"""

import argparse
import csv
import re
from pathlib import Path
from typing import List, Tuple


TX_START_RE = re.compile(r"session=([0-9]+)\s+interval=([0-9]+)ms", re.IGNORECASE)


def parse_tx_log(path: Path) -> List[Tuple[str, int]]:
    seq = []
    for line in path.read_text(errors="ignore").splitlines():
        m = TX_START_RE.search(line)
        if m:
            session = m.group(1).zfill(2)
            interval = int(m.group(2))
            seq.append((session, interval))
    return seq


def list_txsd_trials(txsd_dir: Path) -> List[Path]:
    files = sorted(txsd_dir.glob("trial_*_on.csv"))
    return files


def main():
    ap = argparse.ArgumentParser(description="Map TXSD trial files to TX sessions from serial log.")
    ap.add_argument("--tx-log", required=True, type=Path, help="TX serial log containing session/interval lines.")
    ap.add_argument("--txsd-dir", required=True, type=Path, help="Directory with TXSD trial_XXX_on.csv files.")
    ap.add_argument("--output", required=True, type=Path, help="Output CSV path.")
    args = ap.parse_args()

    tx_seq = parse_tx_log(args.tx_log)
    txsd_files = list_txsd_trials(args.txsd_dir)

    if not tx_seq:
        raise SystemExit("No session entries found in tx-log.")
    if not txsd_files:
        raise SystemExit("No TXSD trials found.")

    n = min(len(tx_seq), len(txsd_files))
    rows = []
    for idx in range(n):
        session, interval = tx_seq[idx]
        f = txsd_files[idx]
        trial_id = f.stem  # trial_XXX_on
        rows.append({
            "order": idx + 1,
            "trial": f.name,
            "trial_path": str(f),
            "session": session,
            "subject": f"subject{session}",
            "interval_ms": interval,
        })

    if len(tx_seq) != len(txsd_files):
        print(f"[warn] tx_seq={len(tx_seq)} txsd_files={len(txsd_files)}; mapped first {n} entries.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
