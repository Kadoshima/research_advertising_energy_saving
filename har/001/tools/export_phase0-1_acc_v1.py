"""
Export Phase0-1 acc.v1 model to ONNX and prepare representative data for TFLite PTQ.

Outputs (under --outdir, default har/001/export/acc_v1):
  - phase0-1-acc.v1.onnx       : ONNX graph
  - rep_data.npy               : representative samples (float32, [N,T,C])
  - meta.json                  : export metadata (model_id sha256, config, ckpt, input_shape, sample_count)

Notes:
  * TFLite conversion is intentionally left to a follow-up step (requires TensorFlow stack).
    The representative data is saved here for PTQ (per-channel conv) in the next step.
  * Model_id is derived from the ckpt sha256 for reproducibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
import yaml

# Allow imports from repo root and har/001/src
ROOT = Path(__file__).resolve().parents[3]  # repo root
SRC = ROOT / "har" / "001" / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from model import DSCNN  # type: ignore  # noqa: E402


def load_config(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_model(cfg: Dict) -> DSCNN:
    model_cfg = cfg.get("model", {})
    n_classes = model_cfg.get("n_classes", 12)
    in_ch = model_cfg.get("in_ch", 3)
    dropout = model_cfg.get("dropout", 0.3)
    model = DSCNN(n_classes=n_classes, in_ch=in_ch, dropout=dropout)
    return model


def load_state(model: torch.nn.Module, ckpt_path: Path) -> None:
    state = torch.load(ckpt_path, map_location="cpu")
    # Support plain state_dict or dict with "model"/"state_dict"
    if isinstance(state, dict):
        if "model" in state:
            state = state["model"]
        elif "state_dict" in state:
            state = state["state_dict"]
    model.load_state_dict(state)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_representative(npz_paths: List[Path], sample_count: int, rng: np.random.Generator) -> np.ndarray:
    samples: List[np.ndarray] = []
    for p in npz_paths:
        data = np.load(p)
        X = data["X"]  # [N, T, C]
        n = len(X)
        idx = rng.permutation(n)
        for i in idx:
            samples.append(X[i])
            if len(samples) >= sample_count:
                return np.stack(samples).astype(np.float32)
    return np.stack(samples).astype(np.float32) if samples else np.empty((0, 0, 0), dtype=np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("har/001/configs/phase0-1.acc.v1.yaml"))
    ap.add_argument("--ckpt", type=Path, default=Path("har/001/runs/phase0-1-acc/fold90/best_model.pth"))
    ap.add_argument("--outdir", type=Path, default=Path("har/001/export/acc_v1"))
    ap.add_argument("--sample-dir", type=Path, default=None, help="Directory with subjectXX.npz (uses config paths.processed_dir if omitted)")
    ap.add_argument("--sample-count", type=int, default=2000, help="Representative sample count for PTQ")
    args = ap.parse_args()

    cfg = load_config(args.config)
    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    # Build model
    model = build_model(cfg)
    load_state(model, args.ckpt)
    model.eval()

    # Dummy input for ONNX export
    T = int(cfg["data"]["fs_hz"] * cfg["data"]["window_s"])
    C = cfg.get("model", {}).get("in_ch", 3)
    dummy = torch.randn(1, T, C, dtype=torch.float32)

    # Export ONNX
    onnx_path = outdir / "phase0-1-acc.v1.onnx"
    torch.onnx.export(
        model,
        dummy,
        onnx_path.as_posix(),
        input_names=["input"],
        output_names=["logits"],
        opset_version=13,
        dynamic_axes={"input": {0: "batch", 1: "time"}, "logits": {0: "batch"}},
    )
    print(f"[ok] saved ONNX -> {onnx_path}")

    # Representative data for PTQ
    proc_dir = args.sample_dir if args.sample_dir else Path(cfg["paths"]["processed_dir"])
    npz_paths = sorted(proc_dir.glob("subject*.npz"))
    rng = np.random.default_rng(42)
    rep = collect_representative(npz_paths, args.sample_count, rng)
    rep_path = outdir / "rep_data.npy"
    np.save(rep_path, rep)
    print(f"[ok] saved representative data ({rep.shape}) -> {rep_path}")

    # Metadata
    meta = {
        "config": str(args.config),
        "ckpt": str(args.ckpt),
        "model_id_sha256": sha256_file(args.ckpt),
        "onnx": str(onnx_path),
        "rep_data": str(rep_path),
        "input_shape": [1, T, C],
        "sample_count": int(rep.shape[0]),
    }
    with open(outdir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[ok] wrote meta -> {outdir / 'meta.json'}")


if __name__ == "__main__":
    main()
