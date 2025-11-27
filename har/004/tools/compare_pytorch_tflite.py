"""
Compare PyTorch vs TFLite outputs for Phase0-1 acc.v1 model.

Usage:
  python har/001/tools/compare_pytorch_tflite.py \\
    --config har/001/configs/phase0-1.acc.v1.yaml \\
    --ckpt har/001/runs/phase0-1-acc/fold90/best_model.pth \\
    --tflite har/001/export/acc_v1/phase0-1-acc.v1.int8.tflite \\
    --npz har/001/data_processed/subject01.npz --num 200

Reports:
  - argmax match rate
  - max_prob MAE
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
import yaml

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "har" / "001" / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from model import DSCNN  # type: ignore  # noqa: E402


def load_config(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_model(cfg: Dict, ckpt: Path) -> torch.nn.Module:
    model = DSCNN(
        n_classes=cfg.get("model", {}).get("n_classes", 12),
        in_ch=cfg.get("model", {}).get("in_ch", 3),
        dropout=cfg.get("model", {}).get("dropout", 0.3),
    )
    state = torch.load(ckpt, map_location="cpu")
    if isinstance(state, dict):
        state = state.get("model", state.get("state_dict", state))
    model.load_state_dict(state)
    model.eval()
    return model


def load_samples(npz_paths: List[Path], num: int) -> np.ndarray:
    xs = []
    for p in npz_paths:
        data = np.load(p)
        X = data["X"]
        for i in range(len(X)):
            xs.append(X[i])
            if len(xs) >= num:
                return np.stack(xs).astype(np.float32)
    return np.stack(xs).astype(np.float32)


def run_torch(model: torch.nn.Module, x_np: np.ndarray) -> np.ndarray:
    with torch.no_grad():
        logits = model(torch.from_numpy(x_np).float())
        probs = torch.softmax(logits, dim=-1).numpy()
    return probs


def run_tflite(tflite_path: Path, x_np: np.ndarray) -> np.ndarray:
    import tensorflow as tf

    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]

    # TFLite expects [1, T, C], so run sample by sample
    outputs = []
    scale_in, zero_in = input_detail["quantization"]
    scale_out, zero_out = output_detail["quantization"]
    for i in range(len(x_np)):
        x = x_np[i:i+1]
        if input_detail["dtype"] == np.int8:
            x_int8 = np.round(x / scale_in + zero_in).astype(np.int8)
            interpreter.set_tensor(input_detail["index"], x_int8)
        else:
            interpreter.set_tensor(input_detail["index"], x.astype(np.float32))
        interpreter.invoke()
        out = interpreter.get_tensor(output_detail["index"])
        if output_detail["dtype"] == np.int8:
            out = (out.astype(np.float32) - zero_out) * scale_out
        # convert logits -> probs
        exp = np.exp(out - out.max(axis=-1, keepdims=True))
        probs = exp / exp.sum(axis=-1, keepdims=True)
        outputs.append(probs[0])
    out = np.stack(outputs)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("har/004/configs/phase0-1.acc.v1.yaml"))
    ap.add_argument("--ckpt", type=Path, default=Path("har/004/runs/phase0-1-acc/fold90/best_model.pth"))
    ap.add_argument("--tflite", type=Path, required=True)
    ap.add_argument("--npz", type=Path, required=True, help="A subjectXX.npz file to draw samples from")
    ap.add_argument("--num", type=int, default=200)
    args = ap.parse_args()

    cfg = load_config(args.config)
    model = load_model(cfg, args.ckpt)
    X = load_samples([args.npz], args.num)

    probs_pt = run_torch(model, X)
    probs_tf = run_tflite(args.tflite, X)

    y_pt = probs_pt.argmax(axis=1)
    y_tf = probs_tf.argmax(axis=1)
    match = (y_pt == y_tf).mean()
    mae_pmax = np.abs(probs_pt.max(axis=1) - probs_tf.max(axis=1)).mean()

    print(f"argmax match: {match:.4f}")
    print(f"max_prob MAE: {mae_pmax:.4f}")


if __name__ == "__main__":
    main()
