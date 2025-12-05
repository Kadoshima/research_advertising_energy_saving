"""Summarize PDR and energy per interval bucket.

Usage:
  python scripts/summarize_pdr_energy.py \
      --pdr-csv data/1202配線変更後/Mode_C_2_02/pdr_segmented_filtered.csv \
      --tx-dir data/1202配線変更後/Mode_C_2_02/TX \
      --output data/1202配線変更後/Mode_C_2_02/pdr_energy_summary.csv
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def load_tx_energy(tx_dir: Path) -> Dict[str, float]:
    energies: Dict[str, float] = {}
    for f in tx_dir.glob("trial_*_on.csv"):
        text = f.read_text(errors="ignore").splitlines()
        summary = next((l for l in text if l.startswith("# summary")), None)
        if not summary:
            continue
        kv = {}
        for part in summary.split(",")[1:]:
            if "=" in part:
                k, v = part.split("=", 1)
                kv[k.strip()] = v.strip()
        try:
            energies[f.name] = float(kv["E_per_adv_uJ"])
        except KeyError:
            continue
    return energies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdr-csv", required=True, type=Path)
    ap.add_argument("--tx-dir", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    tx_energy = load_tx_energy(args.tx_dir)

    with args.pdr_csv.open() as fh:
        rows = list(csv.DictReader(fh))

    agg: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    counts: Dict[str, int] = defaultdict(int)
    for r in rows:
        bucket = r["interval_bucket_ms"]
        counts[bucket] += 1
        agg[bucket]["pdr_raw"].append(float(r["pdr_raw"]))
        agg[bucket]["pdr_unique"].append(float(r["pdr_unique"]))
        ea = tx_energy.get(r["trial"])
        if ea is not None:
            agg[bucket]["E_per_adv_uJ"].append(ea)

    out_rows: List[Dict[str, str]] = []
    for bucket in sorted(agg.keys(), key=lambda x: int(x)):
        d = agg[bucket]
        def mean(lst: List[float]) -> float:
            return sum(lst) / len(lst) if lst else float("nan")
        out_rows.append({
            "interval_bucket_ms": bucket,
            "trials": str(counts[bucket]),
            "pdr_raw_mean": f"{mean(d['pdr_raw']):.4f}",
            "pdr_unique_mean": f"{mean(d['pdr_unique']):.4f}",
            "E_per_adv_uJ_mean": f"{mean(d['E_per_adv_uJ']):.1f}" if d["E_per_adv_uJ"] else "",
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    # Also print to stdout
    print("interval_bucket_ms,trials,pdr_raw_mean,pdr_unique_mean,E_per_adv_uJ_mean")
    for row in out_rows:
        print(",".join(row.values()))


if __name__ == "__main__":
    main()
