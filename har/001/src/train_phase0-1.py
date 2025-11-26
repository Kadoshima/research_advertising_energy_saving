from __future__ import annotations

import argparse
import json
import math
import os
import traceback
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import random
from math import cos, sin
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import balanced_accuracy_score, f1_score
from torch.utils.data import DataLoader, Dataset

from model import DSCNN
from calibration import search_temperature, search_tau, temperature_scale


def compute_ece(y_true: np.ndarray, probs: np.ndarray, n_bins: int = 15) -> float:
    """Compute Expected Calibration Error with equal-frequency binning."""
    confidences = probs.max(axis=1)
    predictions = probs.argmax(axis=1)
    accuracies = (predictions == y_true).astype(float)

    # Equal-frequency binning
    bin_boundaries = np.percentile(confidences, np.linspace(0, 100, n_bins + 1))
    bin_boundaries[-1] += 1e-8  # ensure last bin includes max

    ece = 0.0
    for i in range(n_bins):
        mask = (confidences >= bin_boundaries[i]) & (confidences < bin_boundaries[i + 1])
        if mask.sum() > 0:
            bin_conf = confidences[mask].mean()
            bin_acc = accuracies[mask].mean()
            bin_size = mask.sum()
            ece += (bin_size / len(y_true)) * abs(bin_conf - bin_acc)

    return ece


def compute_4class_metrics(y_true_12: list, y_pred_12: list) -> dict:
    """Map 12-class predictions to 4-class and compute metrics."""
    # Mapping: 12class (0-11 + 12=unknown) -> 4class
    # 0: Locomotion (Walking=3, Cycling=8, Jogging=9, Running=10)
    # 1: Transition (Stairs=4, Bends=5, Arms=6, Crouch=7, Jump=11)
    # 2: Stationary (Standing=0, Sitting=1, Lying=2)
    # 3: Ignore (or Unknown if pred=12)

    def map_to_4class(label):
        if label == 12:  # Unknown
            return 3
        if label in [3, 8, 9, 10]:  # Walking, Cycling, Jogging, Running
            return 0  # Locomotion
        if label in [4, 5, 6, 7, 11]:  # Stairs, Bends, Arms, Crouch, Jump
            return 1  # Transition
        if label in [0, 1, 2]:  # Standing, Sitting, Lying
            return 2  # Stationary
        return 3  # Fallback to Ignore

    y_true_4 = np.array([map_to_4class(y) for y in y_true_12])
    y_pred_4 = np.array([map_to_4class(y) for y in y_pred_12])

    return {
        "bacc": float(balanced_accuracy_score(y_true_4, y_pred_4)),
        "f1_macro": float(f1_score(y_true_4, y_pred_4, average="macro", zero_division=0)),
    }


def load_config(path: Path) -> dict:
    import yaml

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
    """Augment 6ch (or 3ch) sample; x shape [T, C]."""
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
    def __init__(self, npz_paths: List[Path], use_labels4: bool = False, return_logits: bool = False, apply_aug: bool = False):
        self.samples: List[Tuple[np.ndarray, int]] = []
        for p in npz_paths:
            data = np.load(p, allow_pickle=True)
            X = data["X"]
            y = data["y4" if use_labels4 else "y12"]
            for i in range(len(X)):
                self.samples.append((X[i], int(y[i])))
        self.return_logits = return_logits
        self.apply_aug = apply_aug

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        x, y = self.samples[idx]
        if self.apply_aug:
            x = augment_sample(x.copy())
        return torch.from_numpy(x), torch.tensor(y, dtype=torch.long)


def split_paths(processed_dir: Path, subjects: List[int], use_labels4: bool = False) -> List[Path]:
    paths = []
    for sid in subjects:
        p = processed_dir / f"subject{sid:02d}.npz"
        if p.exists():
            paths.append(p)
    return paths


def train_one_fold(args, cfg: dict, fold: dict, fold_dir: Path) -> Dict:
    device = torch.device(cfg.get("training", {}).get("device", "cpu"))
    torch.set_num_threads(1)
    processed_dir = Path(cfg["paths"]["processed_dir"])
    val_ratio = cfg["train"].get("val_ratio", 0.1)

    train_paths = split_paths(processed_dir, fold["train"])
    val_paths = split_paths(processed_dir, fold.get("val", []))
    test_paths = split_paths(processed_dir, fold["test"])

    train_ds_full = WindowDataset(train_paths, apply_aug=True)
    if len(val_paths) == 0:
        # split train into train/val
        val_size = max(1, int(len(train_ds_full) * val_ratio))
        train_size = len(train_ds_full) - val_size
        g = torch.Generator().manual_seed(42)
        train_ds, val_ds = torch.utils.data.random_split(train_ds_full, [train_size, val_size], generator=g)
    else:
        train_ds = train_ds_full
        val_ds = WindowDataset(val_paths)
    test_ds = WindowDataset(test_paths)
    print(f"[fold {fold['id']}] train/val/test sizes: {len(train_ds)}/{len(val_ds)}/{len(test_ds)}")

    train_loader = DataLoader(train_ds, batch_size=cfg["train"]["batch"], shuffle=True, num_workers=cfg["training"].get("num_workers", 0))
    val_loader = DataLoader(val_ds, batch_size=cfg["train"]["batch"], shuffle=False, num_workers=cfg["training"].get("num_workers", 0))
    test_loader = DataLoader(test_ds, batch_size=cfg["train"]["batch"], shuffle=False, num_workers=cfg["training"].get("num_workers", 0))

    model = DSCNN(n_classes=12, in_ch=cfg.get("model", {}).get("in_ch", 3)).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=cfg["train"]["lr"], weight_decay=cfg["train"]["weight_decay"])
    best_val = -math.inf
    best_state = None
    patience = cfg["train"]["early_stop_patience"]
    counter = 0

    for epoch in range(cfg["train"]["max_epoch"]):
        print(f"[fold {fold['id']}] epoch {epoch+1}/{cfg['train']['max_epoch']}")
        model.train()
        for x, y in train_loader:
            x = x.to(device)
            y = y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()

        val_acc = eval_loader(model, val_loader, device)["bacc"]
        if val_acc > best_val:
            best_val = val_acc
            best_state = model.state_dict()
            counter = 0
        else:
            counter += 1
            if counter >= patience:
                break

    if best_state:
        model.load_state_dict(best_state)
        # Save checkpoint
        checkpoint_path = fold_dir / "best_model.pth"
        torch.save(best_state, checkpoint_path)
        print(f"[fold {fold['id']}] saved checkpoint to {checkpoint_path}")

    val_metrics, val_logits = eval_loader(model, val_loader, device, return_preds=True, return_logits=True)
    logits_np = np.asarray(val_logits["logits"])
    labels_np = np.asarray(val_logits["labels"])
    calib_T = search_temperature(logits_np, labels_np, n_bins=cfg["calibration"]["ece_bins"], T_range=(0.3, 3.0))
    # apply temperature to val logits for tau search
    val_probs_scaled = torch.softmax(torch.from_numpy(logits_np / calib_T), dim=1).numpy()
    tau, tau_grid = search_tau(val_probs_scaled, labels_np, tau_range=(0.3, 0.9), step=0.02)

    # Test evaluation with calibration
    test_metrics, test_preds = eval_loader(model, test_loader, device, return_preds=True, return_logits=True, tau=tau, calib_T=calib_T)

    # Compute ECE on test set
    test_logits_np = np.asarray(test_preds["logits"])
    test_labels_np = np.asarray(test_preds["labels"])
    test_probs_calibrated = torch.softmax(torch.from_numpy(test_logits_np / calib_T), dim=1).numpy()
    ece_test = compute_ece(test_labels_np, test_probs_calibrated, n_bins=cfg["calibration"]["ece_bins"])

    # Compute 4-class metrics
    test_metrics_4class = compute_4class_metrics(test_preds["y_true"], test_preds["y_pred"])

    # Compute unknown rate on test
    test_max_probs = test_probs_calibrated.max(axis=1)
    unknown_rate_test = float((test_max_probs < tau).mean())

    return {
        "val": val_metrics,
        "test": test_metrics,
        "test_4class": test_metrics_4class,
        "preds": test_preds,
        "best_val_bacc": best_val,
        "calibration": {
            "calib_T": float(calib_T),
            "tau_unknown": float(tau),
            "tau_grid": tau_grid,
            "ece_test": float(ece_test),
            "unknown_rate_test": float(unknown_rate_test),
        },
    }


def eval_loader(model, loader, device, return_preds: bool = False, return_logits: bool = False, tau: float = None, calib_T: float = None) -> Dict:
    model.eval()
    ys, yh = [], []
    logits_all = []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            logits = model(x)
            logits_all.append(logits.cpu().numpy())
            if calib_T:
                logits = logits / calib_T
            probs = torch.softmax(logits, dim=1)
            preds = probs.argmax(dim=1).cpu().numpy()
            if tau is not None:
                maxp = probs.max(dim=1).values.cpu().numpy()
                preds = preds.copy()
                preds[maxp < tau] = probs.shape[1]  # unknown class id = n_classes
            ys.append(y.numpy())
            yh.append(preds)
    y_true = np.concatenate(ys)
    y_pred = np.concatenate(yh)
    metrics = {
        "bacc": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro")),
    }
    if return_preds:
        preds_out = {"y_true": y_true.tolist(), "y_pred": y_pred.tolist()}
        if return_logits:
            logits_np = np.concatenate(logits_all)
            preds_out["logits"] = logits_np.tolist()
            preds_out["labels"] = y_true.tolist()
            return metrics, preds_out
        return metrics, preds_out
    if return_logits:
        logits_np = np.concatenate(logits_all)
        return metrics, {"logits": logits_np, "labels": y_true}
    return metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("configs/phase0-1.local.yaml"))
    ap.add_argument("--splits", type=Path, default=Path("../../docs/フェーズ0-1/splits.yaml"))
    ap.add_argument("--fold", type=str, default=None, help="If set, run only this fold id")
    args = ap.parse_args()

    cfg = load_config(args.config)
    with open(args.splits, "r", encoding="utf-8") as f:
        import yaml

        folds = yaml.safe_load(f)["folds"]

    os.makedirs(cfg["paths"]["runs_dir"], exist_ok=True)
    all_results = {}
    all_results_4class = {}
    all_calib = {}
    target_fold = args.fold
    for fold in folds:
        if target_fold and fold["id"] != target_fold:
            continue
        out_dir = Path(cfg["paths"]["runs_dir"]) / fold["id"]
        out_dir.mkdir(parents=True, exist_ok=True)

        res = train_one_fold(args, cfg, fold, out_dir)
        all_results[fold["id"]] = res["test"]
        all_results_4class[fold["id"]] = res["test_4class"]
        all_calib[fold["id"]] = res["calibration"]

        with open(out_dir / "metrics.json", "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)

    # Compute summary statistics
    if all_results:
        bacc_values = [v["bacc"] for v in all_results.values()]
        f1_values = [v["f1_macro"] for v in all_results.values()]
        bacc4_values = [v["bacc"] for v in all_results_4class.values()]
        f1_4_values = [v["f1_macro"] for v in all_results_4class.values()]
        ece_values = [v["ece_test"] for v in all_calib.values()]
        unknown_values = [v["unknown_rate_test"] for v in all_calib.values()]

        summary = {
            "folds": {
                fold_id: {
                    "bacc": all_results[fold_id]["bacc"],
                    "f1_macro": all_results[fold_id]["f1_macro"],
                    "bacc4": all_results_4class[fold_id]["bacc"],
                    "f1_macro4": all_results_4class[fold_id]["f1_macro"],
                    "ece": all_calib[fold_id]["ece_test"],
                    "unknown_rate": all_calib[fold_id]["unknown_rate_test"],
                }
                for fold_id in all_results.keys()
            },
            "mean": {
                "bacc": float(np.mean(bacc_values)),
                "f1_macro": float(np.mean(f1_values)),
                "bacc4": float(np.mean(bacc4_values)),
                "f1_macro4": float(np.mean(f1_4_values)),
                "ece": float(np.mean(ece_values)),
                "unknown_rate": float(np.mean(unknown_values)),
            },
            "std": {
                "bacc": float(np.std(bacc_values)),
                "f1_macro": float(np.std(f1_values)),
                "bacc4": float(np.std(bacc4_values)),
                "f1_macro4": float(np.std(f1_4_values)),
                "ece": float(np.std(ece_values)),
                "unknown_rate": float(np.std(unknown_values)),
            },
            "min": {
                "bacc": float(np.min(bacc_values)),
                "bacc4": float(np.min(bacc4_values)),
            },
            "max": {
                "bacc": float(np.max(bacc_values)),
                "bacc4": float(np.max(bacc4_values)),
            },
            "median": {
                "bacc": float(np.median(bacc_values)),
                "bacc4": float(np.median(bacc4_values)),
            },
        }

        with open(Path(cfg["paths"]["runs_dir"]) / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    print("[ok] training complete, see runs dir")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("[error] train_phase0-1.py crashed:")
        traceback.print_exc()
