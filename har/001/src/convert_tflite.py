"""Convert PyTorch HAR model to TensorFlow Lite with int8 quantization.

For ESP32-S3 deployment with TensorFlow Lite for Microcontrollers (TFLM).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
import tensorflow as tf

from model import DSCNN


def pytorch_to_tflite(model_path: Path, output_path: Path, representative_data_path: Path = None, quantize: bool = True):
    """Convert PyTorch model to TFLite with optional int8 quantization.

    Args:
        model_path: Path to PyTorch checkpoint (.pth)
        output_path: Path to save TFLite model (.tflite)
        representative_data_path: Path to representative dataset for quantization (npz file)
        quantize: If True, apply int8 quantization
    """
    print(f"\n{'='*80}")
    print("PyTorch → TFLite Conversion")
    print(f"{'='*80}\n")

    # Load PyTorch model
    print(f"Loading PyTorch model from {model_path}...")
    model = DSCNN(n_classes=12, in_ch=3)
    state_dict = torch.load(model_path, map_location='cpu')
    model.load_state_dict(state_dict)
    model.eval()

    # Create dummy input for tracing
    dummy_input = torch.randn(1, 100, 3)  # [batch, time, channels]

    print(f"Model architecture:")
    print(f"  Input shape: [batch, 100, 3]")
    print(f"  Output shape: [batch, 12]")
    print()

    # Convert to TorchScript
    print("Converting to TorchScript...")
    traced_model = torch.jit.trace(model, dummy_input)

    # Save TorchScript model temporarily
    temp_pt_path = output_path.parent / "temp_model.pt"
    traced_model.save(str(temp_pt_path))

    print("Converting TorchScript → ONNX → TFLite...")

    # PyTorch → ONNX
    temp_onnx_path = output_path.parent / "temp_model.onnx"
    torch.onnx.export(
        model,
        dummy_input,
        temp_onnx_path,
        export_params=True,
        opset_version=13,
        do_constant_folding=True,
        input_names=['input'],
        output_names=['output'],
        dynamic_axes={'input': {0: 'batch'}, 'output': {0: 'batch'}}
    )

    # ONNX → TensorFlow → TFLite
    import onnx
    from onnx_tf.backend import prepare

    onnx_model = onnx.load(str(temp_onnx_path))
    tf_rep = prepare(onnx_model)

    # Export TensorFlow SavedModel
    temp_tf_path = output_path.parent / "temp_tf_model"
    tf_rep.export_graph(str(temp_tf_path))

    # Convert to TFLite
    converter = tf.lite.TFLiteConverter.from_saved_model(str(temp_tf_path))

    if quantize and representative_data_path:
        print(f"Loading representative data from {representative_data_path}...")

        # Load representative dataset
        data = np.load(representative_data_path)
        X_repr = data['X'][:2000]  # Use first 2000 windows

        def representative_dataset():
            for i in range(len(X_repr)):
                # Yield [1, T, C] shaped data
                yield [X_repr[i:i+1].astype(np.float32)]

        # Enable int8 quantization
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.representative_dataset = representative_dataset
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8

        print("Applying int8 quantization...")
    else:
        print("Saving as float32 model (no quantization)...")

    tflite_model = converter.convert()

    # Save TFLite model
    with open(output_path, 'wb') as f:
        f.write(tflite_model)

    # Clean up temporary files
    temp_pt_path.unlink(missing_ok=True)
    temp_onnx_path.unlink(missing_ok=True)
    import shutil
    shutil.rmtree(temp_tf_path, ignore_errors=True)

    print(f"✅ Saved TFLite model to {output_path}")
    print(f"   Size: {len(tflite_model) / 1024:.2f} KB")

    # Analyze model
    interpreter = tf.lite.Interpreter(model_path=str(output_path))
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    print(f"\nModel details:")
    print(f"  Input: shape={input_details[0]['shape']}, dtype={input_details[0]['dtype']}")
    print(f"  Output: shape={output_details[0]['shape']}, dtype={output_details[0]['dtype']}")

    # Estimate tensor arena size
    arena_size = 0
    for tensor in interpreter.get_tensor_details():
        if tensor['shape'].size > 0:
            tensor_size = np.prod(tensor['shape']) * np.dtype(tensor['dtype']).itemsize
            arena_size += tensor_size

    print(f"  Estimated tensor arena: {arena_size / 1024:.2f} KB")

    target_arena = 80  # KB
    if arena_size / 1024 <= target_arena:
        print(f"  ✅ Arena size within target ({target_arena} KB)")
    else:
        print(f"  ⚠️  Arena size exceeds target ({target_arena} KB)")

    print(f"\n{'='*80}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, default=Path("har/001/runs/phase0-1/fold2/best_model.pth"))
    ap.add_argument("--output", type=Path, default=Path("har/001/runs/phase0-1/fold2/model_int8.tflite"))
    ap.add_argument("--repr-data", type=Path, default=Path("har/001/data_processed/subject03.npz"),
                    help="Representative dataset for quantization calibration")
    ap.add_argument("--no-quantize", action="store_true", help="Disable int8 quantization")
    args = ap.parse_args()

    if not args.model.exists():
        print(f"❌ Model checkpoint not found: {args.model}")
        return

    if not args.no_quantize and not args.repr_data.exists():
        print(f"⚠️  Representative data not found: {args.repr_data}")
        print("   Falling back to float32 model (no quantization)")
        args.no_quantize = True

    pytorch_to_tflite(
        args.model,
        args.output,
        representative_data_path=args.repr_data if not args.no_quantize else None,
        quantize=not args.no_quantize
    )


if __name__ == "__main__":
    main()
