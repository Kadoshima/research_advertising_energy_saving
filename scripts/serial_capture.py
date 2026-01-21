#!/usr/bin/env python3
"""Capture serial logs continuously from one or more ports.

Example:
  python scripts/serial_capture.py --ports COM8,COM9 --baud 115200 \
      --out-dir logs/serial_capture --duration 900 --tag v02
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from datetime import datetime
from typing import Iterable, List

try:
    import serial  # type: ignore
except ImportError as exc:
    raise SystemExit("pyserial is required: pip install pyserial") from exc


def _toggle_reset(ser: serial.Serial) -> None:
    ser.dtr = False
    ser.rts = False
    time.sleep(0.1)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.15)
    ser.dtr = False
    ser.rts = False
    time.sleep(0.1)


def _capture_port(
    port: str,
    baud: int,
    out_path: str,
    duration: float,
    toggle_reset: bool,
    stop_event: threading.Event,
) -> None:
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=0.2)
    except Exception as exc:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(f"(open failed) {exc}\n")
        return

    try:
        if toggle_reset:
            _toggle_reset(ser)
        deadline = time.time() + duration if duration > 0 else None
        with open(out_path, "ab") as fh:
            while not stop_event.is_set():
                if deadline is not None and time.time() >= deadline:
                    break
                try:
                    data = ser.read(ser.in_waiting or 1)
                except Exception:
                    break
                if data:
                    fh.write(data)
                    fh.flush()
    finally:
        try:
            ser.close()
        except Exception:
            pass


def _parse_ports(raw: str) -> List[str]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("ports must not be empty")
    return parts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", required=True, help="Comma-separated list, e.g., COM8,COM9")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--out-dir", default=os.path.join("logs", "serial_capture"))
    ap.add_argument("--duration", type=float, default=0.0, help="Seconds; 0 = run until Ctrl+C")
    ap.add_argument("--tag", default="", help="Optional tag appended to filenames")
    ap.add_argument("--toggle-reset", action="store_true", help="Toggle DTR/RTS once on start")
    args = ap.parse_args()

    ports = _parse_ports(args.ports)
    os.makedirs(args.out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"_{args.tag}" if args.tag else ""
    stop_event = threading.Event()
    threads: List[threading.Thread] = []
    out_paths: List[str] = []

    for port in ports:
        out_path = os.path.join(args.out_dir, f"serial_{port}_{ts}{tag}.log")
        out_paths.append(out_path)
        t = threading.Thread(
            target=_capture_port,
            args=(port, args.baud, out_path, args.duration, args.toggle_reset, stop_event),
            daemon=True,
        )
        threads.append(t)
        t.start()
        print(f"[capture] {port} -> {out_path}")

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        stop_event.set()
        for t in threads:
            t.join()

    print("[capture] done")


if __name__ == "__main__":
    main()
