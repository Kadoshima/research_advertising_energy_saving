from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import torch
from sklearn.metrics import f1_score


def temperature_scale(logits: torch.Tensor, T: float) -> torch.Tensor:
    return logits / T


def eval_ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 15) -> float:
    labels = np.asarray(labels)
    confidences = probs.max(axis=1)
    preds = probs.argmax(axis=1)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (confidences > bins[i]) & (confidences <= bins[i + 1])
        if not np.any(mask):
            continue
        acc = (preds[mask] == labels[mask]).mean()
        conf = confidences[mask].mean()
        ece += np.abs(acc - conf) * mask.mean()
    return float(ece)


def search_temperature(logits: np.ndarray, labels: np.ndarray, n_bins: int = 15, T_range: Tuple[float, float] = (0.5, 3.0)) -> float:
    logits = np.asarray(logits)
    labels = np.asarray(labels)
    # grid search for simplicity
    best_T = 1.0
    best_ece = 1e9
    for T in np.linspace(T_range[0], T_range[1], 26):
        scaled = logits / T
        probs = torch.softmax(torch.from_numpy(scaled), dim=1).numpy()
        ece = eval_ece(probs, labels, n_bins=n_bins)
        if ece < best_ece:
            best_ece = ece
            best_T = float(T)
    return best_T


def search_tau(probs: np.ndarray, labels: np.ndarray, tau_range=(0.3, 0.9), step=0.02) -> Tuple[float, Dict[float, Dict]]:
    best_tau = 0.5
    best_f1 = -1.0
    records: Dict[float, Dict] = {}
    for tau in np.arange(tau_range[0], tau_range[1] + 1e-9, step):
        pred = probs.argmax(axis=1)
        maxp = probs.max(axis=1)
        pred_with_unknown = pred.copy()
        pred_with_unknown[maxp < tau] = probs.shape[1]  # unknown class id = n_classes
        unknown_ratio = (pred_with_unknown == probs.shape[1]).mean()
        f1 = f1_score(labels, pred_with_unknown, average="macro", labels=list(range(probs.shape[1] + 1)))
        records[float(tau)] = {"f1_macro": float(f1), "unknown_ratio": float(unknown_ratio)}
        if 0.05 <= unknown_ratio <= 0.15 and f1 > best_f1:
            best_f1 = f1
            best_tau = float(tau)
    return best_tau, records


def save_calib(out_path: Path, calib_T: float, tau: float, stats: Dict) -> None:
    out = {"calib_T": calib_T, "tau_unknown": tau, "grid": stats}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
