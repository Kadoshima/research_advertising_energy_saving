"""
Minimal training script for A_tiny (fold90) with minimal dependencies.
- Dependencies: torch, numpy, pyyaml only
- No sklearn; metrics are computed via lightweight confusion-matrix functions.
- Data/work dirs are taken from the YAML config (same as A0), split from docs/フェーズ0-1/splits_subject90.yaml.
Usage example (after activating a minimal venv):
  python har/004/tools/train_phase0-1_tiny.py \
    --config har/004/configs/phase0-1.acc.v2_tiny.yaml \
    --splits docs/フェーズ0-1/splits_subject90.yaml \
    --fold fold90
Outputs:
- best_model.pth under runs_dir/foldXX/
- metrics.json (val/test 12c & 4c BAcc/F1, best_val_bacc)
"""

from __future__ import annotations

# Set OMP/KMP before torch import to avoid libomp conflicts on macOS
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("KMP_INIT_AT_FORK", "FALSE")

import argparse
import json
import random
from math import cos, sin
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import yaml
from torch.utils.data import DataLoader, Dataset

# Ensure we can import the shared DSCNN definition from har/001/src
import sys

ROOT = Path(__file__).resolve().parents[3]  # repo root
SRC_DIR = ROOT / "har/001/src"
sys.path.insert(0, str(SRC_DIR))

from model import DSCNN


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(False)


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _time_stretch(x: np.ndarray, factor: float) -> np.ndarray:
    """Linear interp time stretch; x shape [T, C]."""
    T, C = x.shape
    new_T = max(1, int(T * factor))
    t_orig = np.arange(T)
    t_new = np.linspace(0, T - 1, new_T)
    stretched = np.stack([np.interp(t_new, t_orig, x[:, c]) for c in range(C)], axis=1)
    if new_T > T:
        stretched = stretched[:T]
    elif new_T < T:
        pad_len = T - new_T
        pad = np.repeat(stretched[-1:], pad_len, axis=0)
        stretched = np.concatenate([stretched, pad], axis=0)
    return stretched.astype(np.float32)


def _small_rotation_matrix(deg: float) -> np.ndarray:
    rad = np.deg2rad(deg)
    c, s = cos(rad), sin(rad)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float32)


def augment_sample(x: np.ndarray) -> np.ndarray:
    """Lightweight augmentation; x shape [T, C]."""
    T, C = x.shape
    # time stretch
    factor = random.uniform(0.9, 1.1)
    x = _time_stretch(x, factor)
    # small rotation on first 3 axes (and next 3 if present)
    deg = random.uniform(-10, 10)
    R = _small_rotation_matrix(deg)
    if C >= 3:
        x[:, 0:3] = x[:, 0:3] @ R.T
    if C >= 6:
        x[:, 3:6] = x[:, 3:6] @ R.T
    # axis scaling
    scale = 1.0 + random.uniform(-0.05, 0.05)
    x = x * scale
    # phase shift
    shift = random.randint(-2, 2)
    if shift != 0:
        if shift > 0:
            x = np.concatenate([np.zeros((shift, C), dtype=np.float32), x[:-shift]], axis=0)
        else:
            x = np.concatenate([x[-shift:], np.zeros((-shift, C), dtype=np.float32)], axis=0)
    # gaussian noise
    std = max(1e-6, x.std()) * 0.05
    noise = np.random.normal(0, std, size=x.shape).astype(np.float32)
    x = x + noise
    return x.astype(np.float32)


class WindowDataset(Dataset):
    def __init__(self, npz_paths: List[Path], apply_aug: bool = False):
        self.samples: List[Tuple[np.ndarray, int]] = []
        for p in npz_paths:
            data = np.load(p, allow_pickle=True)
            X = data["X"]
            y = data["y12"]
            for i in range(len(X)):
                self.samples.append((X[i], int(y[i])))
        self.apply_aug = apply_aug

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        x, y = self.samples[idx]
        if self.apply_aug:
            x = augment_sample(x.copy())
        return torch.from_numpy(x), torch.tensor(y, dtype=torch.long)


def split_paths(processed_dir: Path, subjects: List[int]) -> List[Path]:
    paths = []
    for sid in subjects:
        p = processed_dir / f"subject{sid:02d}.npz"
        if p.exists():
            paths.append(p)
    return paths


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int) -> np.ndarray:
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        cm[int(t), int(p)] += 1
    return cm


def balanced_accuracy_from_cm(cm: np.ndarray) -> float:
    recalls = []
    for c in range(cm.shape[0]):
        tp = cm[c, c]
        fn = cm[c, :].sum() - tp
        denom = tp + fn
        recalls.append(tp / denom if denom > 0 else 0.0)
    return float(np.mean(recalls))


def macro_f1_from_cm(cm: np.ndarray) -> float:
    f1s = []
    for c in range(cm.shape[0]):
        tp = cm[c, c]
        fn = cm[c, :].sum() - tp
        fp = cm[:, c].sum() - tp
        prec_denom = tp + fp
        rec_denom = tp + fn
        precision = tp / prec_denom if prec_denom > 0 else 0.0
        recall = tp / rec_denom if rec_denom > 0 else 0.0
        if precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * precision * recall / (precision + recall)
        f1s.append(f1)
    return float(np.mean(f1s))


def map_to_4class(label: int) -> int:
    if label == 12:  # Unknown
        return 3
    if label in [3, 8, 9, 10]:  # Locomotion
        return 0
    if label in [4, 5, 6, 7, 11]:  # Transition
        return 1
    if label in [0, 1, 2]:  # Stationary
        return 2
    return 3


def eval_metrics(y_true: List[int], y_pred: List[int]) -> Dict[str, float]:
    y_true_np = np.array(y_true)
    y_pred_np = np.array(y_pred)
    cm = confusion_matrix(y_true_np, y_pred_np, num_classes=12)
    return {
        "bacc": balanced_accuracy_from_cm(cm),
        "f1_macro": macro_f1_from_cm(cm),
    }


def eval_4class_metrics(y_true_12: List[int], y_pred_12: List[int]) -> Dict[str, float]:
    y_true_4 = np.array([map_to_4class(y) for y in y_true_12])
    y_pred_4 = np.array([map_to_4class(y) for y in y_pred_12])
    cm4 = confusion_matrix(y_true_4, y_pred_4, num_classes=4)
    return {
        "bacc": balanced_accuracy_from_cm(cm4),
        "f1_macro": macro_f1_from_cm(cm4),
    }


def train_one_fold(cfg: dict, fold: dict, fold_dir: Path) -> Dict:
    device = torch.device(cfg.get("training", {}).get("device", "cpu"))
    torch.set_num_threads(1)
    processed_dir = Path(cfg["paths"]["processed_dir"])
    val_ratio = cfg["train"].get("val_ratio", 0.1)

    train_paths = split_paths(processed_dir, fold["train"])
    val_paths = split_paths(processed_dir, fold.get("val", []))
    test_paths = split_paths(processed_dir, fold["test"])

    train_ds_full = WindowDataset(train_paths, apply_aug=True)
    if len(val_paths) == 0:
        val_size = max(1, int(len(train_ds_full) * val_ratio))
        train_size = len(train_ds_full) - val_size
        g = torch.Generator().manual_seed(42)
        train_ds, val_ds = torch.utils.data.random_split(train_ds_full, [train_size, val_size], generator=g)
    else:
        train_ds = train_ds_full
        val_ds = WindowDataset(val_paths)
    test_ds = WindowDataset(test_paths)

    train_loader = DataLoader(train_ds, batch_size=cfg["train"]["batch"], shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=cfg["train"]["batch"], shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=cfg["train"]["batch"], shuffle=False, num_workers=0)

    m_cfg = cfg.get("model", {})
    model = DSCNN(
        n_classes=12,
        in_ch=m_cfg.get("in_ch", 3),
        stem_channels=m_cfg.get("stem_channels", 48),
        dw_channels=m_cfg.get("dw_channels", (96, 128, 160)),
        fc_hidden=m_cfg.get("fc_hidden", 128),
        dropout=m_cfg.get("dropout", 0.3),
    ).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=cfg["train"]["lr"], weight_decay=cfg["train"]["weight_decay"])
    best_val = -1e9
    best_state = None
    patience = cfg["train"]["early_stop_patience"]
    counter = 0

    def run_eval(loader):
        model.eval()
        y_true, y_pred = [], []
        with torch.no_grad():
            for x, y in loader:
                x = x.float().to(device)
                y = y.to(device)
                logits = model(x)
                preds = logits.argmax(dim=1)
                y_true.extend(y.cpu().numpy().tolist())
                y_pred.extend(preds.cpu().numpy().tolist())
        return y_true, y_pred

    for epoch in range(cfg["train"]["max_epoch"]):
        model.train()
        for x, y in train_loader:
            x = x.float().to(device)
            y = y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()

        # val
        y_val_true, y_val_pred = run_eval(val_loader)
        val_cm = confusion_matrix(np.array(y_val_true), np.array(y_val_pred), num_classes=12)
        val_bacc = balanced_accuracy_from_cm(val_cm)
        if val_bacc > best_val:
            best_val = val_bacc
            counter = 0
            best_state = {
                "model": model.state_dict(),
                "epoch": epoch,
                "val_bacc": val_bacc,
            }
        else:
            counter += 1
        if counter >= patience:
            break

    if best_state is None:
        best_state = {"model": model.state_dict(), "epoch": epoch, "val_bacc": best_val}
    model.load_state_dict(best_state["model"])
    torch.save(model.state_dict(), fold_dir / "best_model.pth")

    # final eval on val/test
    y_val_true, y_val_pred = run_eval(val_loader)
    y_test_true, y_test_pred = run_eval(test_loader)

    val_metrics = eval_metrics(y_val_true, y_val_pred)
    test_metrics = eval_metrics(y_test_true, y_test_pred)
    test_4class = eval_4class_metrics(y_test_true, y_test_pred)

    return {
        "val": val_metrics,
        "test": test_metrics,
        "test_4class": test_4class,
        "best_val_bacc": best_state["val_bacc"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--splits", type=Path, required=True)
    ap.add_argument("--fold", type=str, default=None, help="If set, run only this fold id")
    args = ap.parse_args()

    set_seed(42)
    cfg = load_config(args.config)
    with open(args.splits, "r", encoding="utf-8") as f:
        folds = yaml.safe_load(f)["folds"]

    os.makedirs(cfg["paths"]["runs_dir"], exist_ok=True)
    target_fold = args.fold
    for fold in folds:
        if target_fold and fold["id"] != target_fold:
            continue
        out_dir = Path(cfg["paths"]["runs_dir"]) / fold["id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        res = train_one_fold(cfg, fold, out_dir)
        with open(out_dir / "metrics.json", "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)


if __name__ == "__main__":
    main()
