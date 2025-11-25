"""Export model information for TFLite conversion and ESP32 deployment.

Generates a summary of the model that can be used to manually implement
or convert to TFLite using external tools.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import numpy as np

from model import DSCNN


def count_parameters(model):
    """Count trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def estimate_flops(model, input_shape=(1, 100, 3)):
    """Rough FLOP estimation for 1D convolutions."""
    # This is a simplified estimation
    # For accurate profiling, use tools like thop or fvcore
    total_flops = 0

    x = torch.randn(*input_shape)
    model.eval()

    with torch.no_grad():
        _ = model(x)

    # Rough estimate based on layer types
    for name, module in model.named_modules():
        if isinstance(module, torch.nn.Conv1d):
            # FLOPs = 2 * in_ch * out_ch * kernel_size * output_length
            in_ch = module.in_channels
            out_ch = module.out_channels
            kernel_size = module.kernel_size[0]
            # Approximate output length
            out_len = input_shape[1] // module.stride[0]
            flops = 2 * in_ch * out_ch * kernel_size * out_len
            total_flops += flops
        elif isinstance(module, torch.nn.Linear):
            # FLOPs = 2 * in_features * out_features
            flops = 2 * module.in_features * module.out_features
            total_flops += flops

    return total_flops


def export_model_info(model_path: Path, output_dir: Path, calib_T: float = 1.0, tau: float = 0.5):
    """Export model information for deployment.

    Args:
        model_path: Path to PyTorch checkpoint
        output_dir: Directory to save outputs
        calib_T: Calibration temperature
        tau: Unknown threshold
    """
    print(f"\n{'='*80}")
    print("Model Information Export")
    print(f"{'='*80}\n")

    # Load model
    print(f"Loading model from {model_path}...")
    model = DSCNN(n_classes=12, in_ch=3)
    state_dict = torch.load(model_path, map_location='cpu')
    model.load_state_dict(state_dict)
    model.eval()

    # Count parameters
    n_params = count_parameters(model)
    print(f"  Parameters: {n_params:,}")

    # Estimate model size
    param_size_bytes = sum(p.numel() * p.element_size() for p in model.parameters())
    print(f"  Model size (float32): {param_size_bytes / 1024:.2f} KB")
    print(f"  Model size (int8 est): {param_size_bytes / (4 * 1024):.2f} KB")

    # Estimate FLOPs
    flops = estimate_flops(model)
    print(f"  FLOPs (approx): {flops / 1e6:.2f} M")

    # Test inference time (CPU)
    import time
    dummy_input = torch.randn(1, 100, 3)
    n_trials = 100

    with torch.no_grad():
        # Warmup
        for _ in range(10):
            _ = model(dummy_input)

        # Measure
        start = time.time()
        for _ in range(n_trials):
            _ = model(dummy_input)
        elapsed = (time.time() - start) / n_trials

    print(f"  Inference time (CPU): {elapsed * 1000:.2f} ms")
    print()

    # Extract layer information
    layer_info = []
    for name, module in model.named_modules():
        if isinstance(module, (torch.nn.Conv1d, torch.nn.Linear, torch.nn.BatchNorm1d)):
            info = {
                "name": name,
                "type": module.__class__.__name__,
            }
            if isinstance(module, torch.nn.Conv1d):
                info.update({
                    "in_channels": module.in_channels,
                    "out_channels": module.out_channels,
                    "kernel_size": module.kernel_size[0],
                    "stride": module.stride[0],
                    "padding": module.padding[0],
                    "groups": module.groups,
                })
            elif isinstance(module, torch.nn.Linear):
                info.update({
                    "in_features": module.in_features,
                    "out_features": module.out_features,
                })
            elif isinstance(module, torch.nn.BatchNorm1d):
                info.update({
                    "num_features": module.num_features,
                })
            layer_info.append(info)

    # Model summary
    summary = {
        "model": "DSCNN",
        "input_shape": [1, 100, 3],
        "output_shape": [1, 12],
        "parameters": n_params,
        "model_size_bytes_float32": param_size_bytes,
        "model_size_bytes_int8_est": param_size_bytes // 4,
        "flops_millions": flops / 1e6,
        "inference_time_ms_cpu": elapsed * 1000,
        "layers": layer_info,
        "calibration": {
            "temperature": calib_T,
            "tau_unknown": tau,
        },
        "deployment": {
            "target": "ESP32-S3",
            "framework": "TensorFlow Lite for Microcontrollers",
            "quantization": "int8",
            "tensor_arena_kb_target": 80,
            "flash_kb_target": 200,
        }
    }

    # Save summary
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "model_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"✅ Saved model summary to {summary_path}")

    # Generate C header file for ESP32
    header_path = output_dir / "har_config.h"
    with open(header_path, 'w') as f:
        f.write(f"// Auto-generated HAR model configuration for ESP32\n")
        f.write(f"// Generated from {model_path.name}\n\n")
        f.write(f"#ifndef HAR_CONFIG_H\n")
        f.write(f"#define HAR_CONFIG_H\n\n")
        f.write(f"// Model architecture\n")
        f.write(f"#define HAR_INPUT_LENGTH 100\n")
        f.write(f"#define HAR_INPUT_CHANNELS 3\n")
        f.write(f"#define HAR_N_CLASSES 12\n")
        f.write(f"#define HAR_UNKNOWN_CLASS_ID 12\n\n")
        f.write(f"// Calibration parameters\n")
        f.write(f"#define HAR_TEMPERATURE {calib_T:.4f}f\n")
        f.write(f"#define HAR_TAU_UNKNOWN {tau:.4f}f\n\n")
        f.write(f"// U/S/CCS parameters\n")
        f.write(f"#define CCS_ALPHA 0.6f  // U weight\n")
        f.write(f"#define CCS_BETA 0.4f   // (1-S) weight\n")
        f.write(f"#define CCS_THETA_LOW 0.40f\n")
        f.write(f"#define CCS_THETA_HIGH 0.70f\n")
        f.write(f"#define CCS_WINDOW_SIZE 10\n")
        f.write(f"#define CCS_MIN_DWELL_MS 2000\n\n")
        f.write(f"// BLE advertising intervals (ms)\n")
        f.write(f"#define BLE_INTERVAL_QUIET 2000   // CCS < theta_low\n")
        f.write(f"#define BLE_INTERVAL_UNCERTAIN 500  // theta_low <= CCS < theta_high\n")
        f.write(f"#define BLE_INTERVAL_ACTIVE 100   // CCS >= theta_high\n")
        f.write(f"#define BLE_INTERVAL_FALLBACK 1000  // Error state\n\n")
        f.write(f"// Class names (12-class internal)\n")
        f.write(f"static const char* HAR_CLASS_NAMES[13] = {{\n")
        f.write(f"    \"Standing\",   // 0\n")
        f.write(f"    \"Sitting\",    // 1\n")
        f.write(f"    \"Lying\",      // 2\n")
        f.write(f"    \"Walking\",    // 3\n")
        f.write(f"    \"Stairs\",     // 4\n")
        f.write(f"    \"Bends\",      // 5\n")
        f.write(f"    \"Arms\",       // 6\n")
        f.write(f"    \"Crouch\",     // 7\n")
        f.write(f"    \"Cycling\",    // 8\n")
        f.write(f"    \"Jogging\",    // 9\n")
        f.write(f"    \"Running\",    // 10\n")
        f.write(f"    \"Jump\",       // 11\n")
        f.write(f"    \"Unknown\"     // 12\n")
        f.write(f"}};\n\n")
        f.write(f"// 4-class operational mapping\n")
        f.write(f"// Returns: 0=Locomotion, 1=Transition, 2=Stationary, 3=Unknown\n")
        f.write(f"static inline int map_to_4class(int class_12) {{\n")
        f.write(f"    if (class_12 == 12) return 3;  // Unknown\n")
        f.write(f"    if (class_12 == 3 || class_12 == 8 || class_12 == 9 || class_12 == 10) return 0;  // Locomotion\n")
        f.write(f"    if (class_12 == 4 || class_12 == 5 || class_12 == 6 || class_12 == 7 || class_12 == 11) return 1;  // Transition\n")
        f.write(f"    if (class_12 == 0 || class_12 == 1 || class_12 == 2) return 2;  // Stationary\n")
        f.write(f"    return 3;  // Fallback to Unknown\n")
        f.write(f"}}\n\n")
        f.write(f"#endif // HAR_CONFIG_H\n")

    print(f"✅ Saved C header to {header_path}")
    print(f"\n{'='*80}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, default=Path("har/001/runs/phase0-1/fold2/best_model.pth"))
    ap.add_argument("--output-dir", type=Path, default=Path("har/001/runs/phase0-1/fold2/deployment"))
    ap.add_argument("--calib-T", type=float, default=None, help="Calibration temperature (auto-load from recalibrated.json)")
    ap.add_argument("--tau", type=float, default=None, help="Unknown threshold (auto-load from recalibrated.json)")
    args = ap.parse_args()

    if not args.model.exists():
        print(f"❌ Model checkpoint not found: {args.model}")
        return

    # Try to load calibration parameters from recalibrated.json
    recalib_path = args.model.parent / "recalibrated.json"
    if recalib_path.exists() and (args.calib_T is None or args.tau is None):
        print(f"Loading calibration parameters from {recalib_path}")
        with open(recalib_path) as f:
            recalib = json.load(f)
        calib_T = recalib["recalibrated"]["calib_T"] if args.calib_T is None else args.calib_T
        tau = recalib["recalibrated"]["tau_unknown"] if args.tau is None else args.tau
    else:
        calib_T = args.calib_T if args.calib_T is not None else 1.0
        tau = args.tau if args.tau is not None else 0.5

    export_model_info(args.model, args.output_dir, calib_T=calib_T, tau=tau)


if __name__ == "__main__":
    main()
