"""Detailed confusion matrix analysis for Standing/Sitting misclassification.

This script analyzes:
1. Where Standing/Sitting are misclassified (12-class confusion matrices)
2. 4-class confusion matrix patterns
3. Real impact on BLE interval control (CCS-based interval selection errors)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

# Class names
CLASS_NAMES_12 = [
    "Standing", "Sitting", "Lying",  # 0-2: Stationary
    "Walking", "Stairs", "Bends", "Arms", "Crouch",  # 3-7: Dynamic
    "Cycling", "Jogging", "Running", "Jump"  # 8-11: Locomotion
]

CLASS_NAMES_4 = ["Locomotion", "Transition", "Stationary", "Unknown"]

# 4-class mapping (0-indexed)
LOCOMOTION = {3, 8, 9, 10}  # Walking, Cycling, Jogging, Running
TRANSITION = {4, 5, 6, 7, 11}  # Stairs, Bends, Arms, Crouch, Jump
STATIONARY = {0, 1, 2}  # Standing, Sitting, Lying


def load_fold_metrics(fold_id: str, runs_dir: Path) -> Dict:
    """Load metrics for a fold."""
    metrics_path = runs_dir / fold_id / "metrics.json"
    with open(metrics_path, "r") as f:
        return json.load(f)


def analyze_standing_sitting_confusion(subject_id: int, runs_dir: Path) -> Dict:
    """Analyze where Standing (0) and Sitting (1) are misclassified."""
    fold_id = f"fold{subject_id}"
    metrics = load_fold_metrics(fold_id, runs_dir)

    y_true = np.array(metrics["preds"]["y_true"])
    y_pred = np.array(metrics["preds"]["y_pred"])

    # Filter out unknown predictions
    mask = y_pred != 12
    y_true_filtered = y_true[mask]
    y_pred_filtered = y_pred[mask]

    # Compute full confusion matrix
    cm = confusion_matrix(y_true_filtered, y_pred_filtered, labels=list(range(12)))

    # Extract Standing (row 0) and Sitting (row 1) misclassification patterns
    standing_row = cm[0, :]  # True=Standing, Pred=?
    sitting_row = cm[1, :]   # True=Sitting, Pred=?

    # Analyze where they go
    standing_total = standing_row.sum()
    sitting_total = sitting_row.sum()

    standing_dist = {}
    sitting_dist = {}

    for i in range(12):
        if standing_total > 0:
            standing_dist[CLASS_NAMES_12[i]] = {
                "count": int(standing_row[i]),
                "ratio": float(standing_row[i] / standing_total)
            }
        if sitting_total > 0:
            sitting_dist[CLASS_NAMES_12[i]] = {
                "count": int(sitting_row[i]),
                "ratio": float(sitting_row[i] / sitting_total)
            }

    return {
        "subject": subject_id,
        "standing_total": int(standing_total),
        "sitting_total": int(sitting_total),
        "standing_misclassification": standing_dist,
        "sitting_misclassification": sitting_dist,
        "confusion_matrix": cm.tolist()
    }


def analyze_4class_confusion(subject_id: int, runs_dir: Path) -> Dict:
    """Analyze 4-class confusion matrix."""
    fold_id = f"fold{subject_id}"
    metrics = load_fold_metrics(fold_id, runs_dir)

    y_true = np.array(metrics["preds"]["y_true"])
    y_pred = np.array(metrics["preds"]["y_pred"])

    # Map 12-class to 4-class
    def map_to_4class(labels):
        out = np.full_like(labels, fill_value=3)  # Default: Unknown
        for i, lbl in enumerate(labels):
            if lbl == 12:  # Unknown
                out[i] = 3
            elif lbl in LOCOMOTION:
                out[i] = 0
            elif lbl in TRANSITION:
                out[i] = 1
            elif lbl in STATIONARY:
                out[i] = 2
        return out

    y_true_4 = map_to_4class(y_true)
    y_pred_4 = map_to_4class(y_pred)

    # Filter unknown
    mask = y_pred_4 != 3
    y_true_4_filtered = y_true_4[mask]
    y_pred_4_filtered = y_pred_4[mask]

    cm4 = confusion_matrix(y_true_4_filtered, y_pred_4_filtered, labels=[0, 1, 2])

    # Compute per-class accuracy
    per_class_acc = {}
    for i in range(3):
        if cm4[i, :].sum() > 0:
            per_class_acc[CLASS_NAMES_4[i]] = float(cm4[i, i] / cm4[i, :].sum())

    return {
        "subject": subject_id,
        "confusion_matrix_4class": cm4.tolist(),
        "per_class_accuracy_4class": per_class_acc
    }


def estimate_ble_interval_errors(subject_id: int, runs_dir: Path) -> Dict:
    """Estimate BLE interval selection errors due to misclassification.

    Assumption: Standing/Sitting/Lying should result in similar CCS (Stationary),
    but misclassification between them might cause different U/S values.

    We simulate the impact by checking if misclassification leads to wrong
    operational class (Stationary vs Locomotion vs Transition).
    """
    fold_id = f"fold{subject_id}"
    metrics = load_fold_metrics(fold_id, runs_dir)

    y_true = np.array(metrics["preds"]["y_true"])
    y_pred = np.array(metrics["preds"]["y_pred"])

    # Map to operational 4-class
    def map_to_4class(labels):
        out = np.full_like(labels, fill_value=3)
        for i, lbl in enumerate(labels):
            if lbl == 12:
                out[i] = 3
            elif lbl in LOCOMOTION:
                out[i] = 0
            elif lbl in TRANSITION:
                out[i] = 1
            elif lbl in STATIONARY:
                out[i] = 2
        return out

    y_true_op = map_to_4class(y_true)
    y_pred_op = map_to_4class(y_pred)

    # Count operational-level errors
    # If true=Stationary but pred=Locomotion/Transition, BLE interval likely wrong
    total_samples = len(y_true)
    operational_errors = (y_true_op != y_pred_op).sum()
    operational_accuracy = 1.0 - (operational_errors / total_samples)

    # Specifically: Stationary misclassified as Locomotion/Transition
    stationary_mask = y_true_op == 2
    stationary_total = stationary_mask.sum()
    stationary_to_locomotion = ((y_true_op == 2) & (y_pred_op == 0)).sum()
    stationary_to_transition = ((y_true_op == 2) & (y_pred_op == 1)).sum()

    return {
        "subject": subject_id,
        "total_samples": int(total_samples),
        "operational_errors": int(operational_errors),
        "operational_accuracy": float(operational_accuracy),
        "stationary_samples": int(stationary_total),
        "stationary_to_locomotion": int(stationary_to_locomotion),
        "stationary_to_transition": int(stationary_to_transition),
        "stationary_misclass_rate": float((stationary_to_locomotion + stationary_to_transition) / (stationary_total + 1e-10))
    }


def main():
    runs_dir = Path("har/001/runs/phase0-1")
    output_dir = Path("har/001/analysis")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_subjects = list(range(1, 11))

    # 1. Standing/Sitting misclassification patterns
    print("=" * 80)
    print("1. STANDING/SITTING MISCLASSIFICATION ANALYSIS")
    print("=" * 80)

    confusion_details = []
    for sid in all_subjects:
        print(f"\nAnalyzing Subject {sid:02d}...")
        detail = analyze_standing_sitting_confusion(sid, runs_dir)
        confusion_details.append(detail)

        # Print top-3 misclassification destinations
        print(f"  Standing (n={detail['standing_total']}):")
        standing_sorted = sorted(
            detail['standing_misclassification'].items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:3]
        for cls, info in standing_sorted:
            print(f"    → {cls}: {info['count']} ({info['ratio']:.1%})")

        print(f"  Sitting (n={detail['sitting_total']}):")
        sitting_sorted = sorted(
            detail['sitting_misclassification'].items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:3]
        for cls, info in sitting_sorted:
            print(f"    → {cls}: {info['count']} ({info['ratio']:.1%})")

    # Save detailed confusion
    with open(output_dir / "confusion_detail_12class.json", "w") as f:
        json.dump(confusion_details, f, indent=2)

    # 2. 4-class confusion matrix
    print("\n" + "=" * 80)
    print("2. 4-CLASS CONFUSION MATRIX ANALYSIS")
    print("=" * 80)

    confusion_4class = []
    for sid in all_subjects:
        detail4 = analyze_4class_confusion(sid, runs_dir)
        confusion_4class.append(detail4)

        print(f"\nSubject {sid:02d}:")
        for cls, acc in detail4["per_class_accuracy_4class"].items():
            print(f"  {cls:12s}: {acc:.3f}")

    with open(output_dir / "confusion_4class.json", "w") as f:
        json.dump(confusion_4class, f, indent=2)

    # 3. BLE interval selection error estimation
    print("\n" + "=" * 80)
    print("3. BLE INTERVAL CONTROL ERROR ESTIMATION")
    print("=" * 80)

    ble_errors = []
    for sid in all_subjects:
        ble_err = estimate_ble_interval_errors(sid, runs_dir)
        ble_errors.append(ble_err)

        print(f"\nSubject {sid:02d}:")
        print(f"  Operational Accuracy: {ble_err['operational_accuracy']:.3f}")
        print(f"  Stationary samples: {ble_err['stationary_samples']}")
        print(f"  Stationary→Locomotion: {ble_err['stationary_to_locomotion']} ({ble_err['stationary_to_locomotion']/(ble_err['stationary_samples']+1e-10):.1%})")
        print(f"  Stationary→Transition: {ble_err['stationary_to_transition']} ({ble_err['stationary_to_transition']/(ble_err['stationary_samples']+1e-10):.1%})")
        print(f"  Stationary misclass rate: {ble_err['stationary_misclass_rate']:.1%}")

    with open(output_dir / "ble_interval_errors.json", "w") as f:
        json.dump(ble_errors, f, indent=2)

    # Summary table
    summary_data = []
    for sid in all_subjects:
        ble = next(b for b in ble_errors if b["subject"] == sid)
        conf4 = next(c for c in confusion_4class if c["subject"] == sid)

        summary_data.append({
            "Subject": f"Sub{sid:02d}",
            "Operational_Acc": ble["operational_accuracy"],
            "Stationary_Acc": conf4["per_class_accuracy_4class"].get("Stationary", 0.0),
            "Locomotion_Acc": conf4["per_class_accuracy_4class"].get("Locomotion", 0.0),
            "Transition_Acc": conf4["per_class_accuracy_4class"].get("Transition", 0.0),
            "Stationary_Misclass_Rate": ble["stationary_misclass_rate"]
        })

    df = pd.DataFrame(summary_data)
    df.to_csv(output_dir / "ble_impact_summary.csv", index=False)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Output files:")
    print(f"  - {output_dir / 'confusion_detail_12class.json'}")
    print(f"  - {output_dir / 'confusion_4class.json'}")
    print(f"  - {output_dir / 'ble_interval_errors.json'}")
    print(f"  - {output_dir / 'ble_impact_summary.csv'}")


if __name__ == "__main__":
    main()
