import argparse
import csv
import re
import time
from datetime import datetime
from pathlib import Path

import serial


def parse_rx_log(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    out = {
        "name_hit": None,
        "mfd_hit": None,
        "rx_count": None,
        "cb_total": None,
        "mfd_bad": None,
        "no_mfd": None,
        "ms_total": None,
    }
    for line in text.splitlines():
        m = re.search(r"\[RX\] summary trial=\d+ ms_total=(\d+), rx=(\d+)", line)
        if m:
            out["ms_total"] = int(m.group(1))
            out["rx_count"] = int(m.group(2))
        m = re.search(r"\[AGENT\] RX diag trial=\d+ cbTotal=(\d+) noMfd=(\d+) mfdBad=(\d+)", line)
        if m:
            out["cb_total"] = int(m.group(1))
            out["no_mfd"] = int(m.group(2))
            out["mfd_bad"] = int(m.group(3))
        m = re.search(r"\[AGENT\] RX diag3 trial=\d+ mfdMfHit=(\d+)", line)
        if m:
            out["mfd_hit"] = int(m.group(1))
        m = re.search(r"\[AGENT\] RX diag4 trial=\d+ nameHit=(\d+)", line)
        if m:
            out["name_hit"] = int(m.group(1))
    return out


def capture_logs(out_dir: Path, tx_port: str, rx_port: str, txsd_port: str, duration_sec: float) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = {
        "tx": out_dir / f"serial_tx_ononly_check_{ts}.txt",
        "rx": out_dir / f"serial_rx_ononly_check_{ts}.txt",
        "txsd": out_dir / f"serial_txsd_ononly_check_{ts}.txt",
    }

    ports = {}
    files = {}
    for key, port in [("tx", tx_port), ("rx", rx_port), ("txsd", txsd_port)]:
        try:
            ser = serial.Serial(port, 115200, timeout=0.2)
            ports[key] = ser
            files[key] = open(paths[key], "ab")
        except Exception as e:
            raise RuntimeError(f"failed to open {port}: {e}")

    try:
        ser = ports["tx"]
        ser.dtr = False
        ser.rts = False
        time.sleep(0.2)
        ser.dtr = True
        ser.rts = True

        start = time.time()
        while time.time() - start < duration_sec:
            for key, ser in ports.items():
                data = ser.read(4096)
                if data:
                    files[key].write(data)
                    files[key].flush()
            time.sleep(0.01)
    finally:
        for ser in ports.values():
            ser.close()
        for f in files.values():
            f.close()

    return paths


def write_manifest(manifest_path: Path, row: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    exists = manifest_path.exists()
    with manifest_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def main() -> int:
    ap = argparse.ArgumentParser(description="ON-only session check with RX diagnostics")
    ap.add_argument("--tx-port", default="COM5")
    ap.add_argument("--rx-port", default="COM9")
    ap.add_argument("--txsd-port", default="COM8")
    ap.add_argument("--duration-sec", type=float, default=25.0)
    ap.add_argument("--condition", required=True, choices=["crowded", "low"], help="Environment condition")
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--manifest", default="logs/session_checks/manifest.csv")
    ap.add_argument("--name-hit-min", type=int, default=None)
    ap.add_argument("--mfd-hit-min", type=int, default=None)
    ap.add_argument("--no-capture", action="store_true")
    ap.add_argument("--tx-log")
    ap.add_argument("--rx-log")
    ap.add_argument("--txsd-log")
    args = ap.parse_args()

    if args.no_capture:
        if not (args.tx_log and args.rx_log and args.txsd_log):
            ap.error("--no-capture requires --tx-log --rx-log --txsd-log")
        paths = {
            "tx": Path(args.tx_log),
            "rx": Path(args.rx_log),
            "txsd": Path(args.txsd_log),
        }
    else:
        paths = capture_logs(Path("logs/session_checks"), args.tx_port, args.rx_port, args.txsd_port, args.duration_sec)

    stats = parse_rx_log(paths["rx"])

    status = "unknown"
    if args.name_hit_min is not None and args.mfd_hit_min is not None:
        if stats["name_hit"] is None or stats["mfd_hit"] is None:
            status = "unknown"
        elif stats["name_hit"] >= args.name_hit_min and stats["mfd_hit"] >= args.mfd_hit_min:
            status = "pass"
        else:
            status = "fail"

    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": args.session_id,
        "condition": args.condition,
        "duration_sec": f"{args.duration_sec:.1f}",
        "tx_log": str(paths["tx"]),
        "rx_log": str(paths["rx"]),
        "txsd_log": str(paths["txsd"]),
        "name_hit": stats["name_hit"],
        "mfd_hit": stats["mfd_hit"],
        "rx_count": stats["rx_count"],
        "cb_total": stats["cb_total"],
        "mfd_bad": stats["mfd_bad"],
        "no_mfd": stats["no_mfd"],
        "ms_total": stats["ms_total"],
        "name_hit_min": args.name_hit_min,
        "mfd_hit_min": args.mfd_hit_min,
        "status": status,
    }

    write_manifest(Path(args.manifest), row)

    print("session_check:", row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
