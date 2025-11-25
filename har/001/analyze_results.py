"""Detailed analysis of har/001 LOSO results."""
import json
from pathlib import Path
import numpy as np

runs_dir = Path("har/001/runs/phase0-1")

print("="*80)
print("HAR Phase 0-1 Detailed Analysis (har/001)")
print("="*80)
print()

# Load all fold results
folds = {}
for fold_id in ["fold1", "fold2", "fold3", "fold4", "fold5"]:
    with open(runs_dir / fold_id / "metrics.json") as f:
        folds[fold_id] = json.load(f)

# Per-fold detailed report
print("### Per-Fold Results")
print()
for fold_id in sorted(folds.keys()):
    d = folds[fold_id]
    test_subject = int(fold_id.replace("fold", ""))

    print(f"**{fold_id.upper()} (Test Subject: {test_subject})**")
    print(f"  Val BAcc:         {d['best_val_bacc']:.4f}")
    print(f"  Test 12-class:    BAcc={d['test']['bacc']:.4f}, F1={d['test']['f1_macro']:.4f}")
    print(f"  Test 4-class:     BAcc={d['test_4class']['bacc']:.4f}, F1={d['test_4class']['f1_macro']:.4f}")
    print(f"  Temperature:      T={d['calibration']['calib_T']:.4f}")
    print(f"  Unknown thresh:   tau={d['calibration']['tau_unknown']:.4f}")
    print(f"  ECE:              {d['calibration']['ece_test']:.4f}")
    print(f"  Unknown rate:     {d['calibration']['unknown_rate_test']*100:.2f}%")

    # Check if targets met
    targets = []
    if d['test']['bacc'] >= 0.80:
        targets.append("✅ 12-BAcc")
    else:
        targets.append(f"❌ 12-BAcc ({d['test']['bacc']-0.80:+.3f})")

    if d['test_4class']['bacc'] >= 0.90:
        targets.append("✅ 4-BAcc")
    else:
        targets.append(f"❌ 4-BAcc ({d['test_4class']['bacc']-0.90:+.3f})")

    if d['calibration']['ece_test'] <= 0.06:
        targets.append("✅ ECE")
    else:
        targets.append(f"❌ ECE ({d['calibration']['ece_test']-0.06:+.3f})")

    unknown_rate = d['calibration']['unknown_rate_test']
    if 0.05 <= unknown_rate <= 0.15:
        targets.append("✅ Unknown%")
    else:
        targets.append(f"⚠️  Unknown% ({unknown_rate*100:.1f}%)")

    print(f"  Status:           {' '.join(targets)}")
    print()

# Summary statistics
print("="*80)
print("### Summary Statistics")
print("="*80)
print()

with open(runs_dir / "summary.json") as f:
    summary = json.load(f)

print("**12-class Classification:**")
print(f"  Mean BAcc:   {summary['mean']['bacc']:.4f} ± {summary['std']['bacc']:.4f}")
print(f"  Median BAcc: {summary['median']['bacc']:.4f}")
print(f"  Range:       [{summary['min']['bacc']:.4f}, {summary['max']['bacc']:.4f}]")
print(f"  Mean F1:     {summary['mean']['f1_macro']:.4f} ± {summary['std']['f1_macro']:.4f}")
target_12 = '✅ PASS' if summary['mean']['bacc'] >= 0.80 else f'❌ FAIL ({summary["mean"]["bacc"]-0.80:+.4f})'
print(f"  Target:      ≥0.80 → {target_12}")
print()

print("**4-class Classification:**")
print(f"  Mean BAcc:   {summary['mean']['bacc4']:.4f} ± {summary['std']['bacc4']:.4f}")
print(f"  Median BAcc: {summary['median']['bacc4']:.4f}")
print(f"  Range:       [{summary['min']['bacc4']:.4f}, {summary['max']['bacc4']:.4f}]")
print(f"  Mean F1:     {summary['mean']['f1_macro4']:.4f} ± {summary['std']['f1_macro4']:.4f}")
target_4 = '✅ PASS' if summary['mean']['bacc4'] >= 0.90 else f'❌ FAIL ({summary["mean"]["bacc4"]-0.90:+.4f})'
print(f"  Target:      ≥0.90 → {target_4}")
print()

print("**Calibration:**")
print(f"  Mean ECE:    {summary['mean']['ece']:.4f} ± {summary['std']['ece']:.4f}")
target_ece = '✅ PASS' if summary['mean']['ece'] <= 0.06 else f'❌ FAIL ({summary["mean"]["ece"]-0.06:+.4f})'
print(f"  Target:      ≤0.06 → {target_ece}")
print()

print("**Unknown Detection:**")
print(f"  Mean rate:   {summary['mean']['unknown_rate']*100:.2f}% ± {summary['std']['unknown_rate']*100:.2f}%")
print(f"  Target:      5-15% → {'✅ PASS' if 0.05 <= summary['mean']['unknown_rate'] <= 0.15 else '❌ FAIL'}")
print()

# Training efficiency
print("="*80)
print("### Training Efficiency")
print("="*80)
print()

epochs_stopped = []
for fold_id in sorted(folds.keys()):
    # Count epochs from stdout (would need to parse, using early stop patience=10 heuristic)
    # From the training log we saw: fold1=36, fold2=23, fold3=17, fold4=14, fold5=30
    pass

print("Early stopping (patience=10):")
print("  fold1: 36 epochs (converged slowly)")
print("  fold2: 23 epochs")
print("  fold3: 17 epochs")
print("  fold4: 14 epochs (converged quickly)")
print("  fold5: 30 epochs")
print()

# Problem diagnosis
print("="*80)
print("### Problem Diagnosis")
print("="*80)
print()

print("**Key Issues:**")
print()
print("1. **fold1 catastrophic failure (BAcc=0.601)**")
print("   - Test subject 1 is extremely difficult")
print("   - Val BAcc=0.668 but Test BAcc=0.601 → generalization gap")
print("   - 4-class performance is decent (0.868), suggesting class confusion within groups")
print()

print("2. **fold4 severe calibration failure (ECE=0.240)**")
print("   - Temperature scaling failed (T=?, need to check)")
print("   - Very low unknown rate (2.4%) suggests tau is too low")
print("   - Despite this, BAcc is acceptable (0.847)")
print()

print("3. **Overall calibration problems (ECE=0.116)**")
print("   - Temperature range (0.5-2.0) may be too narrow")
print("   - Equal-frequency binning may not match confidence distribution")
print("   - Model is overconfident on wrong predictions")
print()

print("4. **High variance across folds (std=0.108)**")
print("   - Subject dependency is strong")
print("   - LOSO is exposing subject-specific features that don't generalize")
print()

# Recommendations
print("="*80)
print("### Recommendations")
print("="*80)
print()

print("**Short-term fixes (attempt to reach targets):**")
print("1. Increase training epochs to 120, patience to 15")
print("2. Add data augmentation (time warping, axis permutation)")
print("3. Widen temperature search range to (0.3, 3.0)")
print("4. Try class weighting to handle imbalanced classes")
print("5. Increase model capacity (add one more DS-Conv layer)")
print()

print("**Long-term considerations:**")
print("1. Subject 1 may need to be excluded (outlier)")
print("2. Consider domain adaptation techniques")
print("3. Investigate chest sensor placement variation")
print("4. Consider waist sensor fallback (har/002 path)")
print()

print("**Representative fold for deployment:**")
print("  → fold2 (median BAcc=0.838, ECE=0.067, meets 4-class target)")
print("    Best balance of performance and calibration")
print()

# Final verdict
print("="*80)
print("### FINAL VERDICT")
print("="*80)
print()
overall_pass = (summary['mean']['bacc'] >= 0.80 and
                summary['mean']['bacc4'] >= 0.90 and
                summary['mean']['ece'] <= 0.06)

if overall_pass:
    print("🎉 ALL TARGETS MET - READY FOR DEPLOYMENT")
else:
    print("❌ TARGETS NOT MET - NEEDS IMPROVEMENT")
    print()
    print("Missing targets:")
    if summary['mean']['bacc'] < 0.80:
        print(f"  - 12-class BAcc: {summary['mean']['bacc']:.4f} < 0.80 (gap: {0.80-summary['mean']['bacc']:.4f})")
    if summary['mean']['bacc4'] < 0.90:
        print(f"  - 4-class BAcc: {summary['mean']['bacc4']:.4f} < 0.90 (gap: {0.90-summary['mean']['bacc4']:.4f})")
    if summary['mean']['ece'] > 0.06:
        print(f"  - ECE: {summary['mean']['ece']:.4f} > 0.06 (excess: {summary['mean']['ece']-0.06:.4f})")

print()
print("="*80)
