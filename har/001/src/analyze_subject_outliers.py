"""Analyze Sub02 and Sub08 outliers to understand failure causes.

This script performs comprehensive analysis to identify why Sub02 and Sub08
perform significantly worse than other subjects in 10-fold LOSO validation.

Analysis includes:
1. Data-level statistics (signal properties, class distribution)
2. Prediction-level analysis (confusion matrices, confidence distribution)
3. Frequency domain analysis (FFT, power spectral density)
4. Per-class performance breakdown
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal as scipy_signal
from scipy.stats import entropy
from sklearn.metrics import confusion_matrix

# Class names for mHealth dataset (0-indexed)
CLASS_NAMES_12 = [
    "Standing", "Sitting", "Lying",  # 0-2: Stationary
    "Walking", "Stairs", "Bends", "Arms", "Crouch",  # 3-7: Dynamic
    "Cycling", "Jogging", "Running", "Jump"  # 8-11: Locomotion
]

CLASS_NAMES_4 = ["Locomotion", "Transition", "Stationary", "Unknown"]


def load_subject_data(subject_id: int, processed_dir: Path) -> Dict:
    """Load preprocessed data for a subject."""
    npz_path = processed_dir / f"subject{subject_id:02d}.npz"
    data = np.load(npz_path, allow_pickle=True)
    return {
        "X": data["X"],  # (N, 100, 3)
        "y12": data["y12"],  # (N,)
        "y4": data["y4"],  # (N,)
        "spans": data["spans"],  # (N, 2)
    }


def load_fold_metrics(fold_id: str, runs_dir: Path) -> Dict:
    """Load metrics for a fold."""
    metrics_path = runs_dir / fold_id / "metrics.json"
    with open(metrics_path, "r") as f:
        return json.load(f)


def compute_signal_statistics(X: np.ndarray) -> Dict:
    """Compute signal-level statistics.

    Args:
        X: (N, T, C) array of time-series data

    Returns:
        Dictionary of statistics per axis
    """
    stats = {}
    for axis in range(X.shape[2]):
        data = X[:, :, axis]
        stats[f"axis{axis}"] = {
            "mean": float(np.mean(data)),
            "std": float(np.std(data)),
            "min": float(np.min(data)),
            "max": float(np.max(data)),
            "range": float(np.ptp(data)),
            "skewness": float(np.mean((data - np.mean(data)) ** 3) / (np.std(data) ** 3 + 1e-10)),
            "kurtosis": float(np.mean((data - np.mean(data)) ** 4) / (np.std(data) ** 4 + 1e-10)),
        }
    return stats


def compute_frequency_features(X: np.ndarray, fs: int = 50) -> Dict:
    """Compute frequency domain features.

    Args:
        X: (N, T, C) array
        fs: Sampling frequency

    Returns:
        Dictionary of frequency features per axis
    """
    features = {}
    for axis in range(X.shape[2]):
        # Average PSD across all windows
        psds = []
        for i in range(X.shape[0]):
            f, psd = scipy_signal.welch(X[i, :, axis], fs=fs, nperseg=min(64, X.shape[1]))
            psds.append(psd)
        avg_psd = np.mean(psds, axis=0)

        # Dominant frequency
        dominant_idx = np.argmax(avg_psd)
        dominant_freq = f[dominant_idx]

        # Spectral entropy
        psd_norm = avg_psd / (np.sum(avg_psd) + 1e-10)
        spec_entropy = entropy(psd_norm)

        features[f"axis{axis}"] = {
            "dominant_freq_hz": float(dominant_freq),
            "spectral_entropy": float(spec_entropy),
            "power_0_5hz": float(np.sum(avg_psd[(f >= 0) & (f < 5)])),
            "power_5_10hz": float(np.sum(avg_psd[(f >= 5) & (f < 10)])),
            "power_10_25hz": float(np.sum(avg_psd[(f >= 10) & (f <= 25)])),
        }
        features[f"axis{axis}_psd"] = {"freq": f.tolist(), "psd": avg_psd.tolist()}

    return features


def analyze_class_distribution(y12: np.ndarray, y4: np.ndarray) -> Dict:
    """Analyze class distribution."""
    unique_12, counts_12 = np.unique(y12, return_counts=True)
    unique_4, counts_4 = np.unique(y4, return_counts=True)

    return {
        "12class": {int(cls): int(cnt) for cls, cnt in zip(unique_12, counts_12)},
        "4class": {int(cls): int(cnt) for cls, cnt in zip(unique_4, counts_4)},
        "class_imbalance_12": float(counts_12.max() / (counts_12.min() + 1e-10)),
        "class_imbalance_4": float(counts_4.max() / (counts_4.min() + 1e-10)),
    }


def analyze_predictions(metrics: Dict) -> Dict:
    """Analyze prediction quality."""
    y_true = np.array(metrics["preds"]["y_true"])
    y_pred = np.array(metrics["preds"]["y_pred"])
    logits = np.array(metrics["preds"]["logits"])

    # Compute probabilities
    probs = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
    max_probs = probs.max(axis=1)
    pred_entropy = entropy(probs.T)

    # Unknown predictions
    unknown_mask = y_pred == 12
    unknown_rate = unknown_mask.mean()

    # Confidence statistics
    conf_stats = {
        "mean_confidence": float(max_probs.mean()),
        "std_confidence": float(max_probs.std()),
        "mean_entropy": float(pred_entropy.mean()),
        "unknown_rate": float(unknown_rate),
        "correct_confidence": float(max_probs[y_true == y_pred].mean()) if (y_true == y_pred).any() else 0.0,
        "incorrect_confidence": float(max_probs[y_true != y_pred].mean()) if (y_true != y_pred).any() else 0.0,
    }

    # Per-class accuracy
    per_class_acc = {}
    for cls in range(12):
        mask = y_true == cls
        if mask.sum() > 0:
            acc = (y_pred[mask] == cls).mean()
            per_class_acc[int(cls)] = float(acc)

    # Confusion matrix (filter unknown from both)
    mask_no_unknown = y_pred != 12
    cm = confusion_matrix(y_true[mask_no_unknown], y_pred[mask_no_unknown], labels=list(range(12)))

    return {
        "confidence_stats": conf_stats,
        "per_class_accuracy": per_class_acc,
        "confusion_matrix": cm.tolist(),
    }


def main():
    # Paths
    processed_dir = Path("har/001/data_processed")
    runs_dir = Path("har/001/runs/phase0-1")
    output_dir = Path("har/001/analysis")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Target subjects
    outlier_subjects = [2, 8]
    success_subjects = [3, 5, 10]
    all_subjects = list(range(1, 11))

    # Collect statistics for all subjects
    all_stats = {}
    for sid in all_subjects:
        print(f"Analyzing Subject {sid:02d}...")
        data = load_subject_data(sid, processed_dir)

        # Signal statistics
        signal_stats = compute_signal_statistics(data["X"])

        # Frequency features
        freq_features = compute_frequency_features(data["X"], fs=50)

        # Class distribution
        class_dist = analyze_class_distribution(data["y12"], data["y4"])

        # Load fold metrics (subject sid is test in fold{sid})
        fold_id = f"fold{sid}"
        metrics = load_fold_metrics(fold_id, runs_dir)

        # Prediction analysis
        pred_analysis = analyze_predictions(metrics)

        all_stats[sid] = {
            "n_samples": int(data["X"].shape[0]),
            "signal_stats": signal_stats,
            "freq_features": freq_features,
            "class_distribution": class_dist,
            "prediction_analysis": pred_analysis,
            "test_bacc": metrics["test"]["bacc"],
            "test_bacc4": metrics["test_4class"]["bacc"],
            "ece": metrics["calibration"]["ece_test"],
            "unknown_rate": metrics["calibration"]["unknown_rate_test"],
            "calib_T": metrics["calibration"]["calib_T"],
            "tau": metrics["calibration"]["tau_unknown"],
        }

    # Save detailed statistics
    with open(output_dir / "subject_statistics.json", "w") as f:
        json.dump(all_stats, f, indent=2)

    # Create comparison tables
    comparison_data = []
    for sid in all_subjects:
        stats = all_stats[sid]
        row = {
            "Subject": sid,
            "Group": "Outlier" if sid in outlier_subjects else ("Success" if sid in success_subjects else "Normal"),
            "N_samples": stats["n_samples"],
            "BAcc_12c": stats["test_bacc"],
            "BAcc_4c": stats["test_bacc4"],
            "ECE": stats["ece"],
            "Unknown_rate": stats["unknown_rate"],
            "Temp_T": stats["calib_T"],
            "Tau": stats["tau"],
            "Mean_conf": stats["prediction_analysis"]["confidence_stats"]["mean_confidence"],
            "Mean_entropy": stats["prediction_analysis"]["confidence_stats"]["mean_entropy"],
        }
        # Add signal statistics
        for axis in range(3):
            row[f"Axis{axis}_mean"] = stats["signal_stats"][f"axis{axis}"]["mean"]
            row[f"Axis{axis}_std"] = stats["signal_stats"][f"axis{axis}"]["std"]
            row[f"Axis{axis}_range"] = stats["signal_stats"][f"axis{axis}"]["range"]

        comparison_data.append(row)

    df = pd.DataFrame(comparison_data)
    df.to_csv(output_dir / "subject_comparison.csv", index=False)
    print(f"\nComparison table saved to {output_dir / 'subject_comparison.csv'}")

    # Print summary
    print("\n" + "=" * 80)
    print("OUTLIER ANALYSIS SUMMARY")
    print("=" * 80)

    for sid in outlier_subjects:
        stats = all_stats[sid]
        print(f"\n### Subject {sid:02d} (BAcc={stats['test_bacc']:.3f}) ###")
        print(f"  Samples: {stats['n_samples']}")
        print(f"  ECE: {stats['ece']:.3f}, Unknown rate: {stats['unknown_rate']:.2%}")
        print(f"  Temperature T: {stats['calib_T']:.3f}, Tau: {stats['tau']:.3f}")

        # Signal characteristics
        print(f"\n  Signal Statistics:")
        for axis in range(3):
            ax_stats = stats["signal_stats"][f"axis{axis}"]
            print(f"    Axis {axis}: mean={ax_stats['mean']:.3f}, std={ax_stats['std']:.3f}, range={ax_stats['range']:.3f}")

        # Class distribution anomalies
        print(f"\n  Class Distribution (12-class):")
        class_dist_12 = stats["class_distribution"]["12class"]
        for cls, count in sorted(class_dist_12.items()):
            print(f"    {CLASS_NAMES_12[cls]:12s}: {count:3d} samples")

        # Per-class accuracy
        print(f"\n  Per-Class Accuracy:")
        per_class_acc = stats["prediction_analysis"]["per_class_accuracy"]
        for cls in sorted(per_class_acc.keys()):
            acc = per_class_acc[cls]
            print(f"    {CLASS_NAMES_12[cls]:12s}: {acc:.3f}")

    # Compare with success cases
    print("\n" + "=" * 80)
    print("COMPARISON WITH SUCCESS CASES")
    print("=" * 80)

    for sid in success_subjects:
        stats = all_stats[sid]
        print(f"\n### Subject {sid:02d} (BAcc={stats['test_bacc']:.3f}) ###")
        print(f"  ECE: {stats['ece']:.3f}, Unknown rate: {stats['unknown_rate']:.2%}")

        # Signal characteristics
        print(f"  Signal Statistics:")
        for axis in range(3):
            ax_stats = stats["signal_stats"][f"axis{axis}"]
            print(f"    Axis {axis}: mean={ax_stats['mean']:.3f}, std={ax_stats['std']:.3f}, range={ax_stats['range']:.3f}")

    print("\n" + "=" * 80)
    print("Analysis complete. Results saved to har/001/analysis/")
    print("=" * 80)


if __name__ == "__main__":
    main()
