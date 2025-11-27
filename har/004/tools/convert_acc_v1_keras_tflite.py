"""
Rebuild Phase0-1 acc.v1 DS-CNN in Keras, port PyTorch weights, and export TFLite int8 (PTQ).

Steps:
1) Load PyTorch model/weights (phase0-1.acc.v1).
2) Build equivalent Keras model (Conv1D + DepthwiseConv1D + pointwise Conv1D blocks).
3) Port weights (Conv/BN/Depthwise/Pointwise/Dense).
4) Save SavedModel and TFLite int8 with representative data (rep_data.npy).

Outputs (under --outdir, default har/001/export/acc_v1_keras):
  - saved_model/ (Keras SavedModel)
  - phase0-1-acc.v1.int8.tflite
  - port_meta.json (paths, sha256 of ckpt, shape, sample_count)

Requirements: torch, tensorflow (TF Lite), numpy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import tensorflow as tf
import torch
import yaml
from tensorflow.keras import layers, models

ROOT = Path(__file__).resolve().parents[3]  # repo root
SRC = ROOT / "har" / "001" / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from model import DSCNN  # type: ignore  # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_config(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_keras_model(T: int, C: int, n_classes: int = 12, dropout: float = 0.3) -> tf.keras.Model:
    inputs = layers.Input(shape=(T, C), name="input")

    x = layers.Conv1D(48, kernel_size=5, strides=1, padding="same", use_bias=True, name="conv1")(inputs)
    x = layers.BatchNormalization(name="bn1")(x)
    x = layers.ReLU(name="relu1")(x)

    # block1
    x = layers.DepthwiseConv1D(kernel_size=5, strides=1, padding="same", use_bias=True, name="dw1")(x)
    x = layers.Conv1D(96, kernel_size=1, strides=1, padding="same", use_bias=True, name="pw1")(x)
    x = layers.BatchNormalization(name="bn2")(x)
    x = layers.ReLU(name="relu2")(x)

    # block2
    x = layers.DepthwiseConv1D(kernel_size=5, strides=1, padding="same", use_bias=True, name="dw2")(x)
    x = layers.Conv1D(128, kernel_size=1, strides=1, padding="same", use_bias=True, name="pw2")(x)
    x = layers.BatchNormalization(name="bn3")(x)
    x = layers.ReLU(name="relu3")(x)

    # block3
    x = layers.DepthwiseConv1D(kernel_size=5, strides=1, padding="same", use_bias=True, name="dw3")(x)
    x = layers.Conv1D(160, kernel_size=1, strides=1, padding="same", use_bias=True, name="pw3")(x)
    x = layers.BatchNormalization(name="bn4")(x)
    x = layers.ReLU(name="relu4")(x)

    x = layers.Dropout(dropout, name="dropout")(x)
    x = layers.GlobalAveragePooling1D(name="gap")(x)
    x = layers.Dense(128, use_bias=True, name="fc1")(x)
    x = layers.ReLU(name="relu_fc1")(x)
    x = layers.Dropout(dropout, name="dropout_fc1")(x)
    outputs = layers.Dense(n_classes, use_bias=True, name="fc2")(x)
    model = models.Model(inputs=inputs, outputs=outputs, name="dscnn_acc_v1")
    return model


def load_torch_weights(ckpt: Path, in_ch: int = 3) -> Dict[str, np.ndarray]:
    model = DSCNN(n_classes=12, in_ch=in_ch, dropout=0.3)
    state = torch.load(ckpt, map_location="cpu")
    if isinstance(state, dict):
        state = state.get("model", state.get("state_dict", state))
    model.load_state_dict(state)
    sd = model.state_dict()
    return {k: v.numpy() for k, v in sd.items()}


def transpose_conv1d_weight(w: np.ndarray) -> np.ndarray:
    # torch: [out_ch, in_ch, k] -> keras Conv1D: [k, in_ch, out_ch]
    return np.transpose(w, (2, 1, 0))


def transpose_depthwise_weight(w: np.ndarray) -> np.ndarray:
    # torch depthwise: [in_ch, 1, k] -> keras DepthwiseConv1D: [k, in_ch, depth_multiplier=1]
    return np.transpose(w, (2, 0, 1))


def transpose_pointwise_weight(w: np.ndarray) -> np.ndarray:
    # torch pointwise: [out_ch, in_ch, 1] -> keras Conv1D (1x1): [1, in_ch, out_ch]
    return np.transpose(w, (2, 1, 0))


def port_weights_to_keras(kmodel: tf.keras.Model, sd: Dict[str, np.ndarray]) -> None:
    # conv1 + bn1
    kmodel.get_layer("conv1").set_weights([
        transpose_conv1d_weight(sd["features.0.weight"]),
        sd["features.0.bias"],
    ])
    kmodel.get_layer("bn1").set_weights([
        sd["features.1.weight"],
        sd["features.1.bias"],
        sd["features.1.running_mean"],
        sd["features.1.running_var"],
    ])

    def port_block(tprefix: str, block_idx: int, dw_name: str, pw_name: str, bn_name: str):
        kmodel.get_layer(dw_name).set_weights([
            transpose_depthwise_weight(sd[f"{tprefix}.depthwise.weight"]),
            sd[f"{tprefix}.depthwise.bias"],
        ])
        kmodel.get_layer(pw_name).set_weights([
            transpose_pointwise_weight(sd[f"{tprefix}.pointwise.weight"]),
            sd[f"{tprefix}.pointwise.bias"],
        ])
        kmodel.get_layer(bn_name).set_weights([
            sd[f"{tprefix}.bn.weight"],
            sd[f"{tprefix}.bn.bias"],
            sd[f"{tprefix}.bn.running_mean"],
            sd[f"{tprefix}.bn.running_var"],
        ])

    port_block("features.3", 1, "dw1", "pw1", "bn2")
    port_block("features.4", 2, "dw2", "pw2", "bn3")
    port_block("features.5", 3, "dw3", "pw3", "bn4")

    # classifier
    kmodel.get_layer("fc1").set_weights([
        sd["classifier.1.weight"].T,
        sd["classifier.1.bias"],
    ])
    kmodel.get_layer("fc2").set_weights([
        sd["classifier.4.weight"].T,
        sd["classifier.4.bias"],
    ])


def save_tflite_int8(saved_model_dir: Path, rep_data: np.ndarray, tflite_path: Path) -> None:
    def rep_gen():
        for i in range(len(rep_data)):
            yield [rep_data[i:i + 1]]

    converter = tf.lite.TFLiteConverter.from_saved_model(saved_model_dir.as_posix())
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = rep_gen
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    tflite_model = converter.convert()
    with open(tflite_path, "wb") as f:
        f.write(tflite_model)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("har/004/configs/phase0-1.acc.v1.yaml"))
    ap.add_argument("--ckpt", type=Path, default=Path("har/004/runs/phase0-1-acc/fold90/best_model.pth"))
    ap.add_argument("--rep-data", type=Path, default=Path("har/004/export/acc_v1/rep_data.npy"))
    ap.add_argument("--outdir", type=Path, default=Path("har/004/export/acc_v1_keras"))
    args = ap.parse_args()

    cfg = load_config(args.config)
    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    T = int(cfg["data"]["fs_hz"] * cfg["data"]["window_s"])
    C = cfg.get("model", {}).get("in_ch", 3)

    # Load torch weights
    sd = load_torch_weights(args.ckpt, in_ch=C)

    # Build Keras model and port weights
    kmodel = build_keras_model(T=T, C=C, n_classes=12, dropout=0.3)
    port_weights_to_keras(kmodel, sd)

    # Sanity: run one forward
    dummy = np.random.randn(1, T, C).astype(np.float32)
    _ = kmodel(dummy)

    # Save SavedModel
    saved_model_dir = outdir / "saved_model"
    if saved_model_dir.exists():
        import shutil
        shutil.rmtree(saved_model_dir)
    # export SavedModel for TFLite conversion
    kmodel.export(saved_model_dir.as_posix())

    # TFLite int8 PTQ
    rep_data = np.load(args.rep_data)
    tflite_path = outdir / "phase0-1-acc.v1.int8.tflite"
    save_tflite_int8(saved_model_dir, rep_data, tflite_path)

    # Meta
    meta = {
        "config": str(args.config),
        "ckpt": str(args.ckpt),
        "model_id_sha256": sha256_file(args.ckpt),
        "saved_model": str(saved_model_dir),
        "tflite_int8": str(tflite_path),
        "rep_data": str(args.rep_data),
        "rep_samples": int(rep_data.shape[0]),
        "input_shape": [1, T, C],
    }
    with open(outdir / "port_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("[ok] saved SavedModel ->", saved_model_dir)
    print("[ok] saved TFLite int8 ->", tflite_path)


if __name__ == "__main__":
    main()
