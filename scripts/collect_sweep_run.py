#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
D:\\logs などの雑多なログ置き場から、シリアルログに現れたファイル名だけを抽出して
プロジェクト配下へ整理コピーする。

入力:
  - serial_log:  TXSD/RX などのシリアル出力テキスト（貼り付け保存したもの）
  - source_dir:  SDカードの /logs をまとめて吸い上げたディレクトリ（例: D:\\logs）

出力（例）:
  data/実験データ/研究室/deltae_v3rig_sweep_YYYY-MM-DD_v01/
    README.md
    manifest.csv
    RX/*.csv
    TXSD/*.csv

使い方:
  python scripts/collect_sweep_run.py --serial-log "D:\\logs\\serial.txt" --source-dir "D:\\logs" --date 2026-01-16 --slug deltae_v3rig_sweep --version v01
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path


DEBUG_LOG_PATH = Path(".cursor") / "debug.log"


def _ndjson(hypothesis_id: str, location: str, message: str, data: dict, run_id: str) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "debug-session",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


RX_NAME_RE = re.compile(r"/logs/(rx_[0-9A-Za-z_]+\.csv)")
TXSD_NAME_RE = re.compile(r"/logs/(pwr_[0-9A-Za-z_]+\.csv)")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_csv_rows(path: Path) -> int:
    # コメント/メタ行('#')は除外し、ヘッダ1行 + データ行を想定
    n = 0
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        for line in f:
            if line.startswith("#"):
                continue
            if not line.strip():
                continue
            n += 1
    # ヘッダがあれば1行引く（安全側：0未満にはしない）
    return max(0, n - 1)


def _ensure_version_dir(base_dir: Path, version: str) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    vdir = base_dir / version
    vdir.mkdir(parents=True, exist_ok=True)
    return vdir


def _safe_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    # 既に同名がある場合は上書きしない（事故防止）
    if dst.exists():
        return
    dst.write_bytes(src.read_bytes())


@dataclass
class Copied:
    kind: str  # "RX" or "TXSD"
    src: Path
    dst: Path
    sha256: str
    rows: int
    size: int


def _read_existing_manifest(manifest: Path) -> dict[str, dict[str, str]]:
    """
    Returns dict keyed by dst_path (relative, e.g. 'TXSD/pwr_....csv') -> row dict.
    """
    if not manifest.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    try:
        with manifest.open("r", encoding="utf-8", errors="replace", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                dst = (row.get("dst_path") or "").strip()
                if not dst:
                    continue
                rows[dst] = {k: (v or "") for k, v in row.items()}
    except Exception:
        return {}
    return rows


def _write_manifest_merge(manifest: Path, out_dir: Path, copied: list[Copied], missing_rx: list[str], missing_txsd: list[str]) -> None:
    """
    Merge strategy:
      - Keep existing rows
      - Upsert copied rows (dst_path key)
      - Keep missing rows, but do not clobber existing filled rows
    """
    existing = _read_existing_manifest(manifest)

    def upsert(dst_rel: str, row: dict[str, str]) -> None:
        prev = existing.get(dst_rel, {})
        merged = dict(prev)
        merged.update({k: str(v) for k, v in row.items()})
        merged["dst_path"] = dst_rel
        existing[dst_rel] = merged

    for c in copied:
        dst_rel = str(c.dst.relative_to(out_dir)).replace("\\", "/")
        upsert(
            dst_rel,
            {
                "kind": c.kind,
                "src_path": str(c.src),
                "sha256": c.sha256,
                "rows": str(c.rows),
                "bytes": str(c.size),
            },
        )

    for n in missing_rx:
        dst_rel = f"RX/{n}"
        if dst_rel not in existing:
            upsert(dst_rel, {"kind": "RX", "src_path": "", "sha256": "", "rows": "", "bytes": ""})
    for n in missing_txsd:
        dst_rel = f"TXSD/{n}"
        if dst_rel not in existing:
            upsert(dst_rel, {"kind": "TXSD", "src_path": "", "sha256": "", "rows": "", "bytes": ""})

    # Write deterministically by dst_path
    fieldnames = ["kind", "src_path", "dst_path", "sha256", "rows", "bytes"]
    with manifest.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for dst_rel in sorted(existing.keys()):
            row = existing[dst_rel]
            w.writerow({k: row.get(k, "") for k in fieldnames})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--serial-log",
        required=True,
        help='TXSD/RXシリアルログのテキストファイルパス（"-" で stdin から読み込み）',
    )
    ap.add_argument("--source-dir", required=True, help="D:\\logs など、csvが入っているディレクトリ")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--slug", default="deltae_v3rig_sweep", help="出力runのslug (default: deltae_v3rig_sweep)")
    ap.add_argument("--version", default="v01", help="v01, v02, ... (default: v01)")
    ap.add_argument("--run-id", default="", help="NDJSON runId (default: auto)")
    args = ap.parse_args()

    run_id = args.run_id or f"collect_{args.slug}_{args.date}_{args.version}"

    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        raise SystemExit(f"[ERR] source dir not found: {source_dir}")

    serial_origin = args.serial_log
    if args.serial_log == "-":
        serial_text = sys.stdin.read()
        if not serial_text.strip():
            raise SystemExit('[ERR] serial log is empty (stdin). Try: Get-Clipboard -Raw | python ... --serial-log -')
    else:
        serial_log = Path(args.serial_log)
        if not serial_log.exists():
            # Hint: list nearby candidates
            parent = serial_log.parent if serial_log.parent.exists() else None
            candidates: list[str] = []
            try:
                if parent:
                    candidates = [p.name for p in parent.glob("serial*.txt")]
            except Exception:
                candidates = []
            msg = f"[ERR] serial log not found: {serial_log}"
            if candidates:
                msg += "\n[HINT] candidates in same dir: " + ", ".join(candidates[:10])
            msg += "\n[HINT] create the file, or use clipboard: Get-Clipboard -Raw | python scripts/collect_sweep_run.py --serial-log - ..."
            raise SystemExit(msg)
        serial_text = serial_log.read_text(encoding="utf-8", errors="replace")

    base_dir = Path("data") / "実験データ" / "研究室" / f"{args.slug}_{args.date}_{args.version}"
    out_dir = _ensure_version_dir(base_dir.parent, base_dir.name)  # keep structure stable
    rx_out = out_dir / "RX"
    txsd_out = out_dir / "TXSD"
    rx_out.mkdir(parents=True, exist_ok=True)
    txsd_out.mkdir(parents=True, exist_ok=True)

    rx_names = sorted(set(RX_NAME_RE.findall(serial_text)))
    txsd_names = sorted(set(TXSD_NAME_RE.findall(serial_text)))

    _ndjson("H1", "scripts/collect_sweep_run.py:main", "parsed filenames", {
        "serial_log": serial_origin,
        "source_dir": str(source_dir),
        "rx_names": len(rx_names),
        "txsd_names": len(txsd_names),
        "out_dir": str(out_dir),
    }, run_id)

    # Build source index (recursive search once)
    src_map: dict[str, Path] = {}
    for p in source_dir.rglob("*.csv"):
        src_map[p.name] = p
    _ndjson("H2", "scripts/collect_sweep_run.py:main", "indexed source csv", {
        "source_csv_count": len(src_map),
    }, run_id)

    copied: list[Copied] = []
    missing_rx: list[str] = []
    missing_txsd: list[str] = []

    for name in rx_names:
        src = src_map.get(name)
        if not src:
            missing_rx.append(name)
            continue
        dst = rx_out / name
        _safe_copy(src, dst)
        copied.append(Copied("RX", src, dst, _sha256(dst), _count_csv_rows(dst), dst.stat().st_size))

    for name in txsd_names:
        src = src_map.get(name)
        if not src:
            missing_txsd.append(name)
            continue
        dst = txsd_out / name
        _safe_copy(src, dst)
        copied.append(Copied("TXSD", src, dst, _sha256(dst), _count_csv_rows(dst), dst.stat().st_size))

    _ndjson("H3", "scripts/collect_sweep_run.py:main", "copied/missing summary", {
        "copied": len(copied),
        "missing_rx": len(missing_rx),
        "missing_txsd": len(missing_txsd),
        "example_missing_rx": missing_rx[:3],
        "example_missing_txsd": missing_txsd[:3],
    }, run_id)

    # manifest.csv
    manifest = out_dir / "manifest.csv"
    _write_manifest_merge(manifest, out_dir, copied, missing_rx, missing_txsd)
    _ndjson("H5", "scripts/collect_sweep_run.py:main", "manifest merged", {
        "manifest": str(manifest),
        "existing_rows": len(_read_existing_manifest(manifest)),
    }, run_id)

    # README.md (minimal, Japanese-first)
    readme = out_dir / "README.md"
    gen_date = time.strftime("%Y-%m-%d", time.localtime())
    if not readme.exists():
        readme.write_text(
            "\n".join(
                [
                    f"# {args.slug} {args.date} {args.version}",
                    "",
                    "- **目的/範囲**: ΔE sweep（TX serial無しでRX/TXSDログを回収・整理）",
                    "- **入力データ**:",
                    f"  - **source_dir**: `{source_dir}`",
                    f"  - **serial_log**: `{serial_origin}`",
                    f"- **出力物**（生成日/生成スクリプト）: {gen_date} / `scripts/collect_sweep_run.py`",
                    "- **再現手順（コマンド）**:",
                    f"  - `python scripts/collect_sweep_run.py --serial-log \"{serial_origin}\" --source-dir \"{source_dir}\" --date {args.date} --slug {args.slug} --version {args.version}`",
                    "- **状態**: draft",
                    "- **関連リンク**:",
                    "  - `scripts/sweep_status.py`（完走判定）",
                    "- **更新履歴**:",
                    f"  - {gen_date}: 初版（ログ抽出→必要csvのみ回収、manifest生成）",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        # Append only a short note to avoid clobbering manual edits.
        with readme.open("a", encoding="utf-8") as f:
            f.write(f"- {gen_date}: 追記回収（serial_log={serial_origin}）\n")

    _ndjson("H4", "scripts/collect_sweep_run.py:main", "wrote outputs", {
        "manifest": str(manifest),
        "readme": str(readme),
    }, run_id)

    print("=== collect_sweep_run ===")
    print(f"out_dir: {out_dir}")
    print(f"RX copied:   {sum(1 for c in copied if c.kind == 'RX')} / missing {len(missing_rx)}")
    print(f"TXSD copied: {sum(1 for c in copied if c.kind == 'TXSD')} / missing {len(missing_txsd)}")
    print(f"manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

