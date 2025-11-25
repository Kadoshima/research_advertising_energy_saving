"""Compute U (Uncertainty), S (Stability), and CCS (Composite Confidence Score) for HAR predictions.

Phase 0-1 specification:
- U: Uncertainty = 1 - max(softmax)
- S: Stability based on state transitions in last W windows
- CCS: 0.6 * U + 0.4 * (1 - S)
- Thresholds: theta_low=0.40, theta_high=0.70
"""
from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch


def compute_uncertainty(probs: np.ndarray) -> np.ndarray:
    """Compute normalized entropy as uncertainty.

    U = -Σ(p * log(p)) / log(n_classes)

    Args:
        probs: [N, n_classes] probability matrix (after softmax)

    Returns:
        U: [N] normalized entropy values in [0, 1]
        where 0 = certain (one class has p=1), 1 = maximum uncertainty (uniform distribution)
    """
    n_classes = probs.shape[1]
    eps = 1e-10
    entropy = -np.sum(probs * np.log(probs + eps), axis=1)
    max_entropy = np.log(n_classes)
    return entropy / max_entropy


def compute_stability(predictions: np.ndarray, window_size: int = 10) -> np.ndarray:
    """Compute stability S based on state transitions in last W windows.

    Stability = 1 - (transitions / (W - 1))

    Args:
        predictions: [N] predicted class IDs
        window_size: W, number of recent predictions to consider

    Returns:
        S: [N] stability values in [0, 1]
    """
    N = len(predictions)
    stability = np.zeros(N)

    for i in range(N):
        # Get last W predictions (or all if < W)
        start = max(0, i - window_size + 1)
        window = predictions[start:i+1]

        if len(window) <= 1:
            stability[i] = 1.0  # No transitions possible
            continue

        # Count transitions
        transitions = np.sum(window[:-1] != window[1:])
        max_transitions = len(window) - 1

        # S = 1 - (transitions / max_transitions)
        stability[i] = 1.0 - (transitions / max_transitions)

    return stability


def compute_ccs(U: np.ndarray, S: np.ndarray, alpha: float = 0.6, beta: float = 0.4) -> np.ndarray:
    """Compute Composite Confidence Score.

    CCS = alpha * U + beta * (1 - S)

    Args:
        U: [N] uncertainty values
        S: [N] stability values
        alpha: weight for uncertainty (default 0.6)
        beta: weight for instability (default 0.4)

    Returns:
        CCS: [N] composite scores in [0, 1]
    """
    assert abs(alpha + beta - 1.0) < 1e-6, "alpha + beta must equal 1.0"
    return alpha * U + beta * (1.0 - S)


def map_ccs_to_state(ccs: np.ndarray, theta_low: float = 0.40, theta_high: float = 0.70) -> np.ndarray:
    """Map CCS values to BLE states.

    States:
    - 0: QUIET (CCS < theta_low) → 2000ms interval
    - 1: UNCERTAIN (theta_low ≤ CCS < theta_high) → 500ms interval
    - 2: ACTIVE (CCS ≥ theta_high) → 100ms interval

    Args:
        ccs: [N] composite confidence scores
        theta_low: lower threshold (default 0.40)
        theta_high: upper threshold (default 0.70)

    Returns:
        states: [N] state IDs (0=QUIET, 1=UNCERTAIN, 2=ACTIVE)
    """
    states = np.zeros(len(ccs), dtype=np.int32)
    states[ccs >= theta_low] = 1  # UNCERTAIN
    states[ccs >= theta_high] = 2  # ACTIVE
    return states


def apply_hysteresis(states: np.ndarray, hysteresis: float = 0.05,
                     theta_low: float = 0.40, theta_high: float = 0.70) -> Tuple[float, float]:
    """Compute effective thresholds with hysteresis.

    Hysteresis prevents rapid switching by adding/subtracting margin to thresholds.

    Args:
        states: [N] current state sequence
        hysteresis: margin to add/subtract (default 0.05)
        theta_low: base lower threshold
        theta_high: base upper threshold

    Returns:
        (effective_low, effective_high): adjusted thresholds
    """
    # For upward transitions: use theta - hysteresis
    # For downward transitions: use theta + hysteresis
    return (theta_low - hysteresis, theta_high + hysteresis)


def apply_dwell_time_filter(states: np.ndarray, min_dwell_samples: int = 100) -> np.ndarray:
    """Apply minimum dwell time constraint.

    State changes are only allowed after min_dwell_samples in the same state.

    Args:
        states: [N] raw state sequence
        min_dwell_samples: minimum samples to stay in a state (default 100 = 2.0s at 50Hz)

    Returns:
        filtered_states: [N] filtered state sequence
    """
    filtered = states.copy()
    current_state = states[0]
    dwell_count = 0

    for i in range(len(states)):
        if states[i] == current_state:
            dwell_count += 1
        else:
            # State wants to change
            if dwell_count >= min_dwell_samples:
                # Allowed to change
                current_state = states[i]
                dwell_count = 1
            else:
                # Not allowed yet, maintain current state
                filtered[i] = current_state
                dwell_count += 1

    return filtered


def compute_usc_for_fold(fold_dir: Path, config: Dict, use_recalibrated: bool = True) -> Dict:
    """Compute U/S/CCS metrics for a fold's test predictions.

    Args:
        fold_dir: path to fold directory (e.g., har/001/runs/phase0-1/fold2)
        config: configuration dict with ccs parameters
        use_recalibrated: if True, use recalibrated.json; else use metrics.json

    Returns:
        Dict with U/S/CCS statistics and state distribution
    """
    # Load predictions
    if use_recalibrated and (fold_dir / "recalibrated.json").exists():
        print(f"Using recalibrated predictions from {fold_dir.name}")
        metrics_file = fold_dir / "recalibrated.json"
        with open(metrics_file) as f:
            data = json.load(f)
        # Recalibrated file doesn't have full preds, need to load from original
        with open(fold_dir / "metrics.json") as f:
            orig_data = json.load(f)

        # Get logits and apply recalibrated temperature
        logits = np.array(orig_data["preds"]["logits"])
        T = data["recalibrated"]["calib_T"]
        probs = torch.softmax(torch.from_numpy(logits / T), dim=1).numpy()

        # Get predictions with recalibrated tau
        tau = data["recalibrated"]["tau_unknown"]
        preds = probs.argmax(axis=1)
        maxp = probs.max(axis=1)
        preds[maxp < tau] = 12  # unknown class

        labels = np.array(orig_data["preds"]["labels"])
    else:
        print(f"Using original predictions from {fold_dir.name}")
        with open(fold_dir / "metrics.json") as f:
            data = json.load(f)

        logits = np.array(data["preds"]["logits"])
        labels = np.array(data["preds"]["labels"])

        # Apply original calibration
        T = data["calibration"]["calib_T"]
        probs = torch.softmax(torch.from_numpy(logits / T), dim=1).numpy()

        tau = data["calibration"]["tau_unknown"]
        preds = probs.argmax(axis=1)
        maxp = probs.max(axis=1)
        preds[maxp < tau] = 12

    # Compute U/S/CCS
    U = compute_uncertainty(probs)
    S = compute_stability(preds, window_size=config["ccs"]["window_size"])
    CCS = compute_ccs(U, S, alpha=config["ccs"]["alpha"], beta=config["ccs"]["beta"])

    # Map to states
    states_raw = map_ccs_to_state(CCS,
                                   theta_low=config["ccs"]["theta_low"],
                                   theta_high=config["ccs"]["theta_high"])

    # Apply dwell time filter (convert seconds to window count)
    # min_dwell_windows = min_stay_s / hop_s
    hop_s = config.get("data", {}).get("hop_s", 1.0)
    min_dwell_windows = int(config["ccs"]["min_stay_s"] / hop_s)
    states_filtered = apply_dwell_time_filter(states_raw, min_dwell_windows)

    # Compute statistics
    stats = {
        "U": {
            "mean": float(U.mean()),
            "std": float(U.std()),
            "min": float(U.min()),
            "max": float(U.max()),
            "median": float(np.median(U)),
        },
        "S": {
            "mean": float(S.mean()),
            "std": float(S.std()),
            "min": float(S.min()),
            "max": float(S.max()),
            "median": float(np.median(S)),
        },
        "CCS": {
            "mean": float(CCS.mean()),
            "std": float(CCS.std()),
            "min": float(CCS.min()),
            "max": float(CCS.max()),
            "median": float(np.median(CCS)),
        },
        "states_raw": {
            "QUIET": int((states_raw == 0).sum()),
            "UNCERTAIN": int((states_raw == 1).sum()),
            "ACTIVE": int((states_raw == 2).sum()),
            "distribution": {
                "QUIET": float((states_raw == 0).mean()),
                "UNCERTAIN": float((states_raw == 1).mean()),
                "ACTIVE": float((states_raw == 2).mean()),
            }
        },
        "states_filtered": {
            "QUIET": int((states_filtered == 0).sum()),
            "UNCERTAIN": int((states_filtered == 1).sum()),
            "ACTIVE": int((states_filtered == 2).sum()),
            "distribution": {
                "QUIET": float((states_filtered == 0).mean()),
                "UNCERTAIN": float((states_filtered == 1).mean()),
                "ACTIVE": float((states_filtered == 2).mean()),
            }
        },
        "n_samples": len(U),
    }

    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=str, default="fold2", help="Fold to analyze")
    ap.add_argument("--runs-dir", type=Path, default=Path("har/001/runs/phase0-1"))
    ap.add_argument("--config", type=Path, default=Path("har/001/configs/phase0-1.local.yaml"))
    ap.add_argument("--use-recalibrated", action="store_true", default=True)
    args = ap.parse_args()

    # Load config
    import yaml
    with open(args.config) as f:
        config = yaml.safe_load(f)

    # Set default values for missing keys
    if "ccs" not in config:
        config["ccs"] = {}
    config["ccs"].setdefault("alpha", 0.6)
    config["ccs"].setdefault("beta", 0.4)
    config["ccs"].setdefault("theta_low", 0.40)
    config["ccs"].setdefault("theta_high", 0.70)
    config["ccs"].setdefault("min_stay_s", 2.0)
    config["ccs"].setdefault("window_size", 10)

    if "data" not in config:
        config["data"] = {}
    config["data"].setdefault("fs_hz", 50)

    fold_dir = args.runs_dir / args.fold

    if not fold_dir.exists():
        print(f"❌ Fold directory not found: {fold_dir}")
        return

    print(f"\n{'='*80}")
    print(f"Computing U/S/CCS for {args.fold}")
    print(f"{'='*80}\n")

    print(f"Configuration:")
    print(f"  alpha (U weight): {config['ccs']['alpha']}")
    print(f"  beta ((1-S) weight): {config['ccs']['beta']}")
    print(f"  theta_low: {config['ccs']['theta_low']}")
    print(f"  theta_high: {config['ccs']['theta_high']}")
    print(f"  min_stay_s: {config['ccs']['min_stay_s']}")
    print(f"  window_size: {config['ccs']['window_size']}")
    print()

    stats = compute_usc_for_fold(fold_dir, config, use_recalibrated=args.use_recalibrated)

    print(f"{'='*80}")
    print("Results")
    print(f"{'='*80}\n")

    print(f"**Uncertainty (U):**")
    print(f"  Mean: {stats['U']['mean']:.4f} ± {stats['U']['std']:.4f}")
    print(f"  Range: [{stats['U']['min']:.4f}, {stats['U']['max']:.4f}]")
    print(f"  Median: {stats['U']['median']:.4f}")
    print()

    print(f"**Stability (S):**")
    print(f"  Mean: {stats['S']['mean']:.4f} ± {stats['S']['std']:.4f}")
    print(f"  Range: [{stats['S']['min']:.4f}, {stats['S']['max']:.4f}]")
    print(f"  Median: {stats['S']['median']:.4f}")
    print()

    print(f"**Composite Confidence Score (CCS):**")
    print(f"  Mean: {stats['CCS']['mean']:.4f} ± {stats['CCS']['std']:.4f}")
    print(f"  Range: [{stats['CCS']['min']:.4f}, {stats['CCS']['max']:.4f}]")
    print(f"  Median: {stats['CCS']['median']:.4f}")
    print()

    print(f"**BLE State Distribution (Raw):**")
    print(f"  QUIET (<{config['ccs']['theta_low']}): {stats['states_raw']['distribution']['QUIET']*100:.2f}%")
    print(f"  UNCERTAIN ([{config['ccs']['theta_low']}, {config['ccs']['theta_high']}): {stats['states_raw']['distribution']['UNCERTAIN']*100:.2f}%")
    print(f"  ACTIVE (≥{config['ccs']['theta_high']}): {stats['states_raw']['distribution']['ACTIVE']*100:.2f}%")
    print()

    print(f"**BLE State Distribution (Filtered, min_stay={config['ccs']['min_stay_s']}s):**")
    print(f"  QUIET: {stats['states_filtered']['distribution']['QUIET']*100:.2f}%")
    print(f"  UNCERTAIN: {stats['states_filtered']['distribution']['UNCERTAIN']*100:.2f}%")
    print(f"  ACTIVE: {stats['states_filtered']['distribution']['ACTIVE']*100:.2f}%")
    print()

    # Save results
    out_file = fold_dir / "usc_metrics.json"
    with open(out_file, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"✅ Saved to {out_file}")
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
