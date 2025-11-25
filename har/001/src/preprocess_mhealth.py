"""Preprocess mHealth chest sensor logs into windowed datasets."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

# mHealth column mapping (1-indexed in README):
# 1-3: chest acc, 4-5: ECG, 6-8: ankle acc, 9-11: ankle gyro, 12-14: ankle mag,
# 15-17: wrist acc, 18-20: wrist gyro, 21-23: wrist mag, 24: label
CHEST_ACC_COLS = [0, 1, 2]
WRIST_GYRO_COLS = [17, 18, 19]  # optional
LABEL_COL = 23


def compute_preproc_hash(cfg: dict) -> str:
    blob = json.dumps(cfg, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_subject(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=r"\s+|\t+", engine="python", header=None)


def map_to_operational(label12: np.ndarray) -> np.ndarray:
    """Map mHealth 12-class labels (1-indexed) to 4-class operational labels.

    mHealth labels (1-indexed from dataset):
    - L1: Standing, L2: Sitting, L3: Lying
    - L4: Walking, L5: Stairs, L6: Bends, L7: Arms, L8: Crouch
    - L9: Cycling, L10: Jogging, L11: Running, L12: Jump
    - L0: Null (no label)

    After conversion to 0-indexed (subtract 1):
    - 0: Standing, 1: Sitting, 2: Lying
    - 3: Walking, 4: Stairs, 5: Bends, 6: Arms, 7: Crouch
    - 8: Cycling, 9: Jogging, 10: Running, 11: Jump

    Operational 4-class mapping:
    - 0 (Locomotion): Walking(3), Cycling(8), Jogging(9), Running(10)
    - 1 (Transition): Stairs(4), Bends(5), Arms(6), Crouch(7), Jump(11)
    - 2 (Stationary): Standing(0), Sitting(1), Lying(2)
    - -1 (Ignore): Null/unlabeled
    """
    locomotion = {3, 8, 9, 10}  # 0-indexed after conversion
    transition = {4, 5, 6, 7, 11}
    stationary = {0, 1, 2}

    out = np.full_like(label12, fill_value=-1)
    for cls in locomotion:
        out[label12 == cls] = 0
    for cls in transition:
        out[label12 == cls] = 1
    for cls in stationary:
        out[label12 == cls] = 2
    # Label 0 (null) and any unknown values remain -1 (Ignore)
    return out


def window_data(acc: np.ndarray, gyro: np.ndarray | None, labels: np.ndarray, fs: int, win_s: float, hop_s: float, purity_min: float, boundary_exclude_s: float):
    win = int(win_s * fs)
    hop = int(hop_s * fs)
    boundary = int(boundary_exclude_s * fs)
    xs, y12, spans = [], [], []
    n = len(labels)
    for start in range(0, n - win + 1, hop):
        end = start + win
        lbl_window = labels[start:end]
        inner = lbl_window[boundary:-boundary] if boundary > 0 else lbl_window
        if inner.size == 0:
            continue
        vals, counts = np.unique(inner, return_counts=True)
        top = vals[np.argmax(counts)]
        purity = counts.max() / len(inner)
        if purity < purity_min or top == 0:
            continue
        feat = acc[start:end] if gyro is None else np.hstack([acc[start:end], gyro[start:end]])
        xs.append(feat)
        y12.append(top)
        spans.append((start, end))
    if not xs:
        return np.empty((0, win, 3 if gyro is None else 6), dtype=np.float32), np.empty(0, dtype=np.int64), spans
    X = np.stack(xs).astype(np.float32)
    y12 = np.array(y12, dtype=np.int64)
    return X, y12, spans


def zscore_per_subject(X: np.ndarray) -> np.ndarray:
    mean = X.mean(axis=(0, 1), keepdims=True)
    std = X.std(axis=(0, 1), keepdims=True) + 1e-6
    return (X - mean) / std


@dataclass
class PreprocessConfig:
    fs_hz: int
    window_s: float
    hop_s: float
    purity_min: float
    boundary_exclude_s: float
    use_gyro: bool


def run_one(subject_id: int, cfg: PreprocessConfig, raw_dir: Path, out_dir: Path, preproc_hash: str):
    path = raw_dir / f"mHealth_subject{subject_id}.log"
    df = load_subject(path)
    acc = df.iloc[:, CHEST_ACC_COLS].to_numpy(dtype=np.float32)
    gyro = df.iloc[:, WRIST_GYRO_COLS].to_numpy(dtype=np.float32) if cfg.use_gyro else None
    labels = df.iloc[:, LABEL_COL].to_numpy(dtype=np.int64)
    X, y12_1indexed, spans = window_data(acc, gyro, labels, cfg.fs_hz, cfg.window_s, cfg.hop_s, cfg.purity_min, cfg.boundary_exclude_s)
    if X.shape[0] == 0:
        print(f"[warn] subject {subject_id}: no valid windows")
        return

    # Convert to 0-indexed for model training
    # mHealth labels are 1-12 (1-indexed), convert to 0-11
    # Note: window_data should have filtered out label=0 (null), but verify
    y12 = y12_1indexed - 1

    # Filter out any remaining null labels (originally 0, now -1 after conversion)
    valid_mask = y12 >= 0
    X = X[valid_mask]
    y12 = y12[valid_mask]
    spans = [spans[i] for i in range(len(spans)) if valid_mask[i]]

    if X.shape[0] == 0:
        print(f"[warn] subject {subject_id}: no valid windows after filtering")
        return

    X = zscore_per_subject(X)
    y4 = map_to_operational(y12)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez(
        out_dir / f"subject{subject_id:02d}.npz",
        X=X,
        y12=y12,
        y4=y4,
        spans=np.array(spans, dtype=np.int32),
        preproc_hash=preproc_hash,
    )
    print(f"[ok] subject {subject_id}: {X.shape[0]} windows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", type=Path, default=Path("data/MHEALTHDATASET"))
    ap.add_argument("--out-dir", type=Path, default=Path("har/001/data_processed"))
    ap.add_argument("--fs", type=int, default=50)
    ap.add_argument("--window-s", type=float, default=2.0)
    ap.add_argument("--hop-s", type=float, default=1.0)
    ap.add_argument("--purity-min", type=float, default=0.75)
    ap.add_argument("--boundary-exclude-s", type=float, default=0.25)
    ap.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 11)))
    ap.add_argument("--use-gyro", action="store_true")
    args = ap.parse_args()

    cfg = PreprocessConfig(
        fs_hz=args.fs,
        window_s=args.window_s,
        hop_s=args.hop_s,
        purity_min=args.purity_min,
        boundary_exclude_s=args.boundary_exclude_s,
        use_gyro=bool(args.use_gyro),
    )
    preproc_hash = compute_preproc_hash({
        "fs_hz": args.fs,
        "window_s": args.window_s,
        "hop_s": args.hop_s,
        "purity_min": args.purity_min,
        "boundary_exclude_s": args.boundary_exclude_s,
        "use_gyro": bool(args.use_gyro),
    })

    for sid in args.subjects:
        run_one(sid, cfg, args.raw_dir, args.out_dir, preproc_hash)


if __name__ == "__main__":
    main()
