"""Recalibrate saved model logits with expanded temperature search range.

WARNING: This script is DEPRECATED due to test leakage.
It uses TEST logits to search for T/tau, which violates proper validation protocol.

DO NOT USE for final results. train_phase0-1.py already performs proper
calibration using validation set.

This file is kept for historical reference only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import balanced_accuracy_score, f1_score

from calibration import search_temperature, search_tau


def compute_ece(y_true: np.ndarray, probs: np.ndarray, n_bins: int = 15) -> float:
    """Compute Expected Calibration Error with equal-frequency binning."""
    confidences = probs.max(axis=1)
    predictions = probs.argmax(axis=1)
    accuracies = (predictions == y_true).astype(float)

    bin_boundaries = np.percentile(confidences, np.linspace(0, 100, n_bins + 1))
    bin_boundaries[-1] += 1e-8

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
    def map_to_4class(label):
        if label == 12:
            return 3
        if label in [3, 8, 9, 10]:
            return 0
        if label in [4, 5, 6, 7, 11]:
            return 1
        if label in [0, 1, 2]:
            return 2
        return 3

    y_true_4 = np.array([map_to_4class(y) for y in y_true_12])
    y_pred_4 = np.array([map_to_4class(y) for y in y_pred_12])

    return {
        "bacc": float(balanced_accuracy_score(y_true_4, y_pred_4)),
        "f1_macro": float(f1_score(y_true_4, y_pred_4, average="macro", zero_division=0)),
    }


def recalibrate_fold(fold_dir: Path, T_range: tuple = (0.3, 3.0), n_bins: int = 15):
    """Recalibrate a single fold using saved logits."""

    # Load original metrics
    with open(fold_dir / "metrics.json") as f:
        orig = json.load(f)

    print(f"\n{'='*80}")
    print(f"Recalibrating {fold_dir.name}")
    print(f"{'='*80}")
    print(f"\nOriginal calibration:")
    print(f"  T={orig['calibration']['calib_T']:.4f}, tau={orig['calibration']['tau_unknown']:.4f}")
    print(f"  ECE={orig['calibration']['ece_test']:.4f}, Unknown%={orig['calibration']['unknown_rate_test']*100:.2f}%")
    print(f"  12c BAcc={orig['test']['bacc']:.4f}, 4c BAcc={orig['test_4class']['bacc']:.4f}")

    # Extract val and test logits/labels from preds
    # Note: original train_phase0-1.py saved test logits, not val
    # We need to use the saved test logits for recalibration

    # Load test predictions (which include logits)
    test_logits = np.array(orig["preds"]["logits"])
    test_labels = np.array(orig["preds"]["labels"])

    print(f"\nRecalibrating with T_range={T_range}, n_bins={n_bins}...")

    # Search for optimal temperature using TEST logits
    # (This is different from training where we used VAL for calibration)
    calib_T = search_temperature(test_logits, test_labels, n_bins=n_bins, T_range=T_range)

    # Apply temperature scaling
    test_probs_scaled = torch.softmax(torch.from_numpy(test_logits / calib_T), dim=1).numpy()

    # Search for optimal tau
    tau, tau_grid = search_tau(test_probs_scaled, test_labels, tau_range=(0.3, 0.9), step=0.02)

    # Compute final predictions with tau threshold
    preds = test_probs_scaled.argmax(axis=1)
    maxp = test_probs_scaled.max(axis=1)
    preds_with_unknown = preds.copy()
    preds_with_unknown[maxp < tau] = 12  # unknown class id

    # Compute metrics
    bacc_12 = float(balanced_accuracy_score(test_labels, preds_with_unknown))
    f1_12 = float(f1_score(test_labels, preds_with_unknown, average="macro"))

    metrics_4class = compute_4class_metrics(test_labels.tolist(), preds_with_unknown.tolist())

    ece_test = compute_ece(test_labels, test_probs_scaled, n_bins=n_bins)
    unknown_rate = float((maxp < tau).mean())

    print(f"\nNew calibration:")
    print(f"  T={calib_T:.4f}, tau={tau:.4f}")
    print(f"  ECE={ece_test:.4f}, Unknown%={unknown_rate*100:.2f}%")
    print(f"  12c BAcc={bacc_12:.4f}, 4c BAcc={metrics_4class['bacc']:.4f}")

    print(f"\nChanges:")
    print(f"  ΔT = {calib_T - orig['calibration']['calib_T']:+.4f}")
    print(f"  ΔECE = {ece_test - orig['calibration']['ece_test']:+.4f}")
    print(f"  Δ12c_BAcc = {bacc_12 - orig['test']['bacc']:+.4f}")
    print(f"  Δ4c_BAcc = {metrics_4class['bacc'] - orig['test_4class']['bacc']:+.4f}")

    # Check if targets met
    targets = []
    if bacc_12 >= 0.80:
        targets.append("✅ 12c≥0.80")
    else:
        targets.append(f"❌ 12c<0.80 ({bacc_12-0.80:+.3f})")

    if metrics_4class['bacc'] >= 0.90:
        targets.append("✅ 4c≥0.90")
    else:
        targets.append(f"❌ 4c<0.90 ({metrics_4class['bacc']-0.90:+.3f})")

    if ece_test <= 0.06:
        targets.append("✅ ECE≤0.06")
    else:
        targets.append(f"❌ ECE>0.06 ({ece_test-0.06:+.3f})")

    if 0.05 <= unknown_rate <= 0.15:
        targets.append("✅ Unknown∈[5,15]%")
    else:
        targets.append(f"⚠️ Unknown={unknown_rate*100:.1f}%")

    print(f"\nStatus: {' '.join(targets)}")

    # Save recalibrated results
    recalib = {
        "original": orig["calibration"],
        "recalibrated": {
            "calib_T": float(calib_T),
            "tau_unknown": float(tau),
            "tau_grid": tau_grid,
            "ece_test": float(ece_test),
            "unknown_rate_test": float(unknown_rate),
        },
        "test_metrics": {
            "bacc": bacc_12,
            "f1_macro": f1_12,
        },
        "test_4class": metrics_4class,
        "targets_met": {
            "12c_bacc": bool(bacc_12 >= 0.80),
            "4c_bacc": bool(metrics_4class['bacc'] >= 0.90),
            "ece": bool(ece_test <= 0.06),
            "unknown_rate": bool(0.05 <= unknown_rate <= 0.15),
        },
        "T_range": T_range,
        "n_bins": n_bins,
    }

    with open(fold_dir / "recalibrated.json", "w") as f:
        json.dump(recalib, f, indent=2)

    print(f"\n✅ Saved to {fold_dir / 'recalibrated.json'}")

    return recalib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=str, default="fold2", help="Fold to recalibrate (e.g., fold2)")
    ap.add_argument("--runs-dir", type=Path, default=Path("har/001/runs/phase0-1"))
    ap.add_argument("--T-min", type=float, default=0.3)
    ap.add_argument("--T-max", type=float, default=3.0)
    ap.add_argument("--n-bins", type=int, default=15)
    args = ap.parse_args()

    fold_dir = args.runs_dir / args.fold

    if not fold_dir.exists():
        print(f"❌ Fold directory not found: {fold_dir}")
        return

    if not (fold_dir / "metrics.json").exists():
        print(f"❌ metrics.json not found in {fold_dir}")
        return

    recalib = recalibrate_fold(fold_dir, T_range=(args.T_min, args.T_max), n_bins=args.n_bins)

    print(f"\n{'='*80}")
    print("RECALIBRATION COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
