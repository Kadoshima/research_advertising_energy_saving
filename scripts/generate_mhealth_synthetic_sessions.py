#!/usr/bin/env python3
"""
Generate high-transition synthetic sessions from mHealth raw logs, with HAR inference for U/CCS.

Spec baseline (docs/フェーズ1/mhealth_synthetic_sessions_spec_v1.md):
- 15s non-overlapping segments, similarity >0.95 filtered.
- Global z-score (train subjects) to reduce boundary jumps.
- Crossfade 0.5s at boundaries; evaluation mask excludes ±1.0s around each boundary.
- Session length 15min with 15s dwell (≈59 transitions).
- Truth grid at 100ms; HAR inference with TFLite (2s window / 1s stride by default).
- U = normalized entropy; CCS = 1 - dot(p_t, p_{t-1}) on 4-class probs; optional EMA.

Outputs (per session):
- sensor CSV: time_s, acc_x/y/z, truth_label, mask_eval
- script CSV: segment list with source metadata
- har CSV: time_center_s, probs(4), y_hat, U, U_ema, CCS, CCS_ema, mask_eval_window, window_len, stride, seed
- summary JSON for reproducibility
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import tensorflow as tf
from numpy.typing import ArrayLike

# ---------------------------------------------------------------------------
# Constants (aligned with spec v1.0)
# ---------------------------------------------------------------------------
FS_HZ = 50
SEG_LEN_S = 15.0
FADE_S = 0.5
EXCLUDE_S = 1.0
SESSION_LEN_S = 15 * 60
TRUTH_DT_MS = 100
WINDOW_S = 2.0
STRIDE_S = 1.0
EMA_ALPHA = 0.2
# 4-class names for logging (0=loco,1=trans,2=stat,3=unk)
CLASS_NAMES = {0: "locomotion", 1: "transition", 2: "stationary", 3: "unknown"}
# Model output index → dataset label ID (mHealth uses 1..12; no null class in TFLite)
MODEL_LABEL_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def load_subject_raw(path: Path) -> pd.DataFrame:
    # Columns: see mHealth README (label is last col, 1-indexed)
    return pd.read_csv(path, sep=r"\s+|\t+", engine="python", header=None)


def map_to_operational(label12_1idx: np.ndarray) -> np.ndarray:
    """Map 1-indexed mHealth labels to 4-class operational labels (0/1/2/3)."""
    label12_0idx = label12_1idx - 1
    out = np.full_like(label12_0idx, fill_value=3)  # unknown by default
    locomotion = {3, 8, 9, 10}
    transition = {4, 5, 6, 7, 11}
    stationary = {0, 1, 2}
    for cls in locomotion:
        out[label12_0idx == cls] = 0
    for cls in transition:
        out[label12_0idx == cls] = 1
    for cls in stationary:
        out[label12_0idx == cls] = 2
    return out


def compute_global_stats(subject_ids: List[int], raw_dir: Path) -> Tuple[np.ndarray, np.ndarray]:
    """Compute global mean/std for chest acc across given subjects."""
    total = np.zeros(3, dtype=np.float64)
    total_sq = np.zeros(3, dtype=np.float64)
    count = 0
    for sid in subject_ids:
        df = load_subject_raw(raw_dir / f"mHealth_subject{sid}.log")
        acc = df.iloc[:, :3].to_numpy(dtype=np.float64)
        total += acc.sum(axis=0)
        total_sq += np.square(acc).sum(axis=0)
        count += len(acc)
    mean = total / count
    var = total_sq / count - np.square(mean)
    std = np.sqrt(np.maximum(var, 1e-6))
    return mean.astype(np.float32), std.astype(np.float32)


def segment_features(seg: np.ndarray, fs: int) -> np.ndarray:
    """Feature vector for similarity: mean/std/RMS + dominant freq mag per channel."""
    mean = seg.mean(axis=0)
    std = seg.std(axis=0)
    rms = np.sqrt(np.mean(np.square(seg), axis=0))
    # dominant frequency magnitude (excluding DC)
    freqs = np.fft.rfft(seg, axis=0)
    mag = np.abs(freqs)
    dom = mag[1:].max(axis=0) if mag.shape[0] > 1 else np.zeros(seg.shape[1])
    feat = np.concatenate([mean, std, rms, dom])
    norm = np.linalg.norm(feat) + 1e-9
    return feat / norm


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


@dataclass
class Segment:
    label4: int
    subject: int
    start_idx: int
    end_idx: int
    data: np.ndarray
    feature: np.ndarray


def build_segment_library(
    subject_ids: List[int],
    raw_dir: Path,
    mean: np.ndarray,
    std: np.ndarray,
    seg_len_s: float,
    sim_threshold: float,
    seed: int,
) -> Dict[int, List[Segment]]:
    rng = random.Random(seed)
    seg_len = int(seg_len_s * FS_HZ)
    library: Dict[int, List[Segment]] = {0: [], 1: [], 2: []}

    for sid in subject_ids:
        df = load_subject_raw(raw_dir / f"mHealth_subject{sid}.log")
        acc = df.iloc[:, :3].to_numpy(dtype=np.float32)
        labels4 = map_to_operational(df.iloc[:, 23].to_numpy(dtype=np.int64))
        # global z-score
        acc = (acc - mean) / std

        # find runs
        n = len(labels4)
        i = 0
        while i < n:
            lbl = labels4[i]
            if lbl == 3:  # unknown
                i += 1
                continue
            j = i
            while j < n and labels4[j] == lbl:
                j += 1
            run_len = j - i
            if run_len >= seg_len:
                starts = list(range(i, j - seg_len + 1, seg_len))
                rng.shuffle(starts)
                for s in starts:
                    seg = acc[s : s + seg_len]
                    feat = segment_features(seg, FS_HZ)
                    # similarity check within label
                    dup = False
                    for existing in library[lbl]:
                        if cosine_sim(feat, existing.feature) > sim_threshold:
                            dup = True
                            break
                    if not dup:
                        library[lbl].append(
                            Segment(
                                label4=lbl,
                                subject=sid,
                                start_idx=s,
                                end_idx=s + seg_len,
                                data=seg,
                                feature=feat,
                            )
                        )
            i = j
    # Shuffle each list for random pop
    for lbl in library:
        rng.shuffle(library[lbl])
    return library


def prepare_interpreter(model_path: Path) -> Tuple[tf.lite.Interpreter, float, int]:
    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()[0]
    input_scale, input_zero = input_details["quantization"]
    input_index = input_details["index"]
    return interpreter, float(input_scale), int(input_zero), input_index


def infer_window(
    interpreter: tf.lite.Interpreter,
    input_scale: float,
    input_zero: int,
    input_index: int,
    window: np.ndarray,
) -> np.ndarray:
    # window shape: [win, 3] float32
    xq = np.round(window / input_scale + input_zero).astype(np.int8)
    interpreter.set_tensor(input_index, xq[None, ...])
    interpreter.invoke()
    output = interpreter.get_output_details()[0]
    yq = interpreter.get_tensor(output["index"])
    y = (yq.astype(np.float32) - output["quantization"][1]) * output["quantization"][0]
    probs = tf.nn.softmax(y, axis=1).numpy()[0]
    return probs


def probs_to_4class(probs12: np.ndarray) -> np.ndarray:
    """Aggregate model probs (len=12) into 4 operational classes."""

    def label_to_class4(label_id: int) -> int:
        # 0:Locomotion, 1:Transition, 2:Stationary, 3:Unknown
        if label_id in (1, 2, 3):  # Standing/Sitting/Lying
            return 2
        if label_id in (4, 9, 10, 11):  # Walking/Cycling/Jogging/Running
            return 0
        if label_id in (5, 6, 7, 8, 12):  # Stairs/Bends/Arms/Crouch/Jump
            return 1
        return 3

    out = np.zeros(4, dtype=np.float32)
    for i, p in enumerate(probs12):
        out[label_to_class4(MODEL_LABEL_IDS[i])] += float(p)
    return out


def session_quality_stats(assembled: Dict[str, object], har_rows: List[Dict[str, object]]) -> Dict[str, object]:
    script = assembled["script"]
    reuse_counts = [r["reuse_count"] for r in script]
    truth_labels = assembled["truth_labels"]
    truth_mask = assembled["truth_mask"]
    mask_window = np.array([r["mask_eval_window"] for r in har_rows], dtype=np.int8)
    u_vals = np.array([r["U"] for r in har_rows], dtype=np.float32)

    def safe_median(arr: ArrayLike) -> float | None:
        arr = np.asarray(arr)
        if arr.size == 0:
            return None
        return float(np.median(arr))

    return {
        "reuse_max": int(max(reuse_counts) if reuse_counts else 0),
        "reuse_mean": float(np.mean(reuse_counts)) if reuse_counts else 0.0,
        "label_counts": {int(k): int(v) for k, v in zip(*np.unique(truth_labels, return_counts=True))},
        "mask_truth_zero_ratio": float(np.mean(truth_mask == 0)),
        "mask_window_zero_ratio": float(np.mean(mask_window == 0)),
        "median_U_eval": safe_median(u_vals[mask_window == 1]),
        "median_U_boundary": safe_median(u_vals[mask_window == 0]),
    }


def normalized_entropy(probs: np.ndarray) -> float:
    """Normalized entropy for U. Unknownクラスは含めず3クラスで計算する."""
    # use first 3 classes (loco, trans, stat); unknown is index 3
    p = probs[:3].astype(np.float64)
    total = p.sum()
    if total <= 1e-9:
        p = np.ones(3, dtype=np.float64) / 3.0
    else:
        p = p / total
    ent = -np.sum(p * np.log(p + 1e-12))
    return float(ent / math.log(3))


# ---------------------------------------------------------------------------
# Session synthesis
# ---------------------------------------------------------------------------
def assemble_session(
    library: Dict[int, List[Segment]],
    sess_id: str,
    seed: int,
) -> Dict[str, object]:
    rng = random.Random(seed)
    seg_needed = int(SESSION_LEN_S / SEG_LEN_S)
    fade = int(FADE_S * FS_HZ)
    exclude = int(EXCLUDE_S * FS_HZ)
    seg_pool = {lbl: list(segs) for lbl, segs in library.items()}
    reuse_counts = {lbl: 0 for lbl in library}
    # shuffle pool per session for variety
    for lbl in seg_pool:
        rng.shuffle(seg_pool[lbl])

    data = np.empty((0, 3), dtype=np.float32)
    labels = np.empty((0,), dtype=np.int32)
    mask = np.empty((0,), dtype=np.int8)
    script_rows = []
    last_label = None

    def pop_segment(lbl: int) -> Segment:
        if not seg_pool[lbl]:
            # replenish
            seg_pool[lbl] = list(library[lbl])
            reuse_counts[lbl] += 1
        return seg_pool[lbl].pop()

    for idx in range(seg_needed):
        choices = [l for l in library.keys() if l != last_label]
        if not choices:
            choices = list(library.keys())
        lbl = rng.choice(choices)
        seg = pop_segment(lbl)

        seg_len = len(seg.data)
        seg_labels = np.full(seg_len, lbl, dtype=np.int32)
        seg_mask = np.ones(seg_len, dtype=np.int8)

        if len(data) == 0:
            data = seg.data.copy()
            labels = seg_labels
            mask = seg_mask
        else:
            L = len(data)
            # apply crossfade on tail
            w = np.linspace(0, 1, fade, endpoint=False, dtype=np.float32)
            data[L - fade :] = data[L - fade :] * (1 - w[:, None]) + seg.data[:fade] * w[:, None]
            labels[L - fade :] = lbl
            # boundary mask exclude
            boundary = L - fade
            start = max(0, boundary - exclude)
            # new length after append
            data = np.concatenate([data, seg.data[fade:]], axis=0)
            labels = np.concatenate([labels, seg_labels[fade:]], axis=0)
            mask = np.concatenate([mask, seg_mask[fade:]], axis=0)
            end = min(len(data), boundary + exclude)
            mask[start:end] = 0

        last_label = lbl
        script_rows.append(
            {
                "seg_idx": idx,
                "label4": lbl,
                "label_name": CLASS_NAMES.get(lbl, "unknown"),
                "subject": seg.subject,
                "start_idx": seg.start_idx,
                "end_idx": seg.end_idx,
                "source_len": seg_len,
                "reuse_count": reuse_counts[lbl],
            }
        )

    # Truth at 100ms grid
    step = int(TRUTH_DT_MS * FS_HZ / 1000)
    n_bins = len(data) // step
    truth_labels = []
    truth_mask = []
    for i in range(n_bins):
        sl = slice(i * step, (i + 1) * step)
        truth_labels.append(int(np.bincount(labels[sl]).argmax()))
        truth_mask.append(int(mask[sl].min()))

    return {
        "data": data,
        "labels": labels,
        "mask": mask,
        "truth_labels": np.array(truth_labels, dtype=np.int32),
        "truth_mask": np.array(truth_mask, dtype=np.int8),
        "script": script_rows,
    }


def run_inference(
    data: np.ndarray,
    mask: np.ndarray,
    interpreter: tf.lite.Interpreter,
    input_scale: float,
    input_zero: int,
    input_index: int,
) -> List[Dict[str, object]]:
    win = int(WINDOW_S * FS_HZ)
    hop = int(STRIDE_S * FS_HZ)
    rows = []
    prev_probs4 = None
    U_ema = None
    CCS_ema = None

    for start in range(0, len(data) - win + 1, hop):
        window = data[start : start + win]
        probs12 = infer_window(interpreter, input_scale, input_zero, input_index, window)
        probs4 = probs_to_4class(probs12)
        U = normalized_entropy(probs4)
        if prev_probs4 is None:
            CCS = 0.0
        else:
            CCS = float(1.0 - np.dot(probs4, prev_probs4))
        U_ema = U if U_ema is None else EMA_ALPHA * U + (1 - EMA_ALPHA) * U_ema
        CCS_ema = CCS if CCS_ema is None else EMA_ALPHA * CCS + (1 - EMA_ALPHA) * CCS_ema
        pred = int(np.argmax(probs4))
        center = (start + win / 2) / FS_HZ
        # window mask: if any sample in window masked, mark 0
        m_eval = int(mask[start : start + win].min())
        rows.append(
            {
                "time_center_s": round(center, 3),
                "p0_loco": float(probs4[0]),
                "p1_trans": float(probs4[1]),
                "p2_stat": float(probs4[2]),
                "p3_unk": float(probs4[3]),
                "y_hat": pred,
                "U": U,
                "U_ema": float(U_ema),
                "CCS": CCS,
                "CCS_ema": float(CCS_ema),
                "mask_eval_window": m_eval,
                "window_len_s": WINDOW_S,
                "stride_s": STRIDE_S,
            }
        )
        prev_probs4 = probs4
    return rows


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------
def save_sensor_csv(path: Path, data: np.ndarray, labels: np.ndarray, mask: np.ndarray):
    with open(path, "w") as f:
        f.write("time_s,acc_x,acc_y,acc_z,truth_label4,mask_eval\n")
        for i, row in enumerate(data):
            t = i / FS_HZ
            f.write(f"{t:.3f},{row[0]:.5f},{row[1]:.5f},{row[2]:.5f},{labels[i]},{mask[i]}\n")


def save_truth_csv(path: Path, truth_labels: np.ndarray, truth_mask: np.ndarray):
    with open(path, "w") as f:
        f.write("time_s,truth_label4,mask_eval\n")
        for i, lbl in enumerate(truth_labels):
            t = i * TRUTH_DT_MS / 1000.0
            f.write(f"{t:.3f},{lbl},{truth_mask[i]}\n")


def save_script_csv(path: Path, rows: List[Dict[str, object]], seed: int):
    with open(path, "w") as f:
        f.write("seg_idx,label4,label_name,subject,start_idx,end_idx,source_len,reuse_count,seed\n")
        for r in rows:
            f.write(
                f"{r['seg_idx']},{r['label4']},{r['label_name']},{r['subject']},"
                f"{r['start_idx']},{r['end_idx']},{r['source_len']},{r['reuse_count']},{seed}\n"
            )


def save_har_csv(path: Path, rows: List[Dict[str, object]]):
    with open(path, "w") as f:
        header = [
            "time_center_s",
            "p0_loco",
            "p1_trans",
            "p2_stat",
            "p3_unk",
            "y_hat",
            "U",
            "U_ema",
            "CCS",
            "CCS_ema",
            "mask_eval_window",
            "window_len_s",
            "stride_s",
        ]
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(
                f"{r['time_center_s']},{r['p0_loco']:.6f},{r['p1_trans']:.6f},"
                f"{r['p2_stat']:.6f},{r['p3_unk']:.6f},{r['y_hat']},{r['U']:.6f},"
                f"{r['U_ema']:.6f},{r['CCS']:.6f},{r['CCS_ema']:.6f},"
                f"{r['mask_eval_window']},{r['window_len_s']},{r['stride_s']}\n"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Generate high-transition synthetic mHealth sessions with U/CCS.")
    ap.add_argument("--raw-dir", type=Path, default=Path("data/MHEALTHDATASET"))
    ap.add_argument("--out-dir", type=Path, default=Path("data/mhealth_synthetic_sessions_v1"))
    ap.add_argument("--train-subjects", type=int, nargs="+", default=list(range(1, 9)))
    ap.add_argument("--test-subjects", type=int, nargs="+", default=[9, 10])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--sessions-per-seed", type=int, default=1)
    ap.add_argument("--sim-threshold", type=float, default=0.95)
    ap.add_argument("--model-path", type=Path, default=Path("har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite"))
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "sessions").mkdir(exist_ok=True)

    mean, std = compute_global_stats(args.train_subjects, args.raw_dir)
    library = build_segment_library(
        subject_ids=args.test_subjects,
        raw_dir=args.raw_dir,
        mean=mean,
        std=std,
        seg_len_s=SEG_LEN_S,
        sim_threshold=args.sim_threshold,
        seed=42,
    )

    interpreter, input_scale, input_zero, input_index = prepare_interpreter(args.model_path)

    summaries = []
    for seed in args.seeds:
        for k in range(args.sessions_per_seed):
            sess_seed = seed * 100 + k  # ensure uniqueness across runs
            sess_id = f"seed{seed}_run{k}"
            assembled = assemble_session(library, sess_id, seed=sess_seed)
            har_rows = run_inference(
                assembled["data"],
                assembled["mask"],
                interpreter,
                input_scale,
                input_zero,
                input_index,
            )
            sess_dir = args.out_dir / "sessions"
            sensor_path = sess_dir / f"{sess_id}_sensor.csv"
            truth_path = sess_dir / f"{sess_id}_truth100ms.csv"
            script_path = sess_dir / f"{sess_id}_script.csv"
            har_path = sess_dir / f"{sess_id}_har.csv"
            save_sensor_csv(sensor_path, assembled["data"], assembled["labels"], assembled["mask"])
            save_truth_csv(truth_path, assembled["truth_labels"], assembled["truth_mask"])
            save_script_csv(script_path, assembled["script"], seed=seed)
            save_har_csv(har_path, har_rows)
            qstats = session_quality_stats(assembled, har_rows)
            summaries.append(
                {
                    "sess_id": sess_id,
                    "seed": seed,
                    "sess_seed": sess_seed,
                    "segments": len(assembled["script"]),
                    "duration_s": len(assembled["data"]) / FS_HZ,
                    "n_transitions": len(assembled["script"]) - 1,
                    "paths": {
                        "sensor": str(sensor_path),
                        "truth100ms": str(truth_path),
                        "script": str(script_path),
                        "har": str(har_path),
                    },
                    "mean_U": float(np.mean([r["U"] for r in har_rows])),
                    "mean_CCS": float(np.mean([r["CCS"] for r in har_rows])),
                    "quality": qstats,
                }
            )
            print(f"[ok] session {sess_id} saved")

    with open(args.out_dir / "summary.json", "w") as f:
        json.dump(
            {
                "train_subjects": args.train_subjects,
                "test_subjects": args.test_subjects,
                "seeds": args.seeds,
                "sessions_per_seed": args.sessions_per_seed,
                "sim_threshold": args.sim_threshold,
                "fs_hz": FS_HZ,
                "seg_len_s": SEG_LEN_S,
                "fade_s": FADE_S,
                "exclude_s": EXCLUDE_S,
                "session_len_s": SESSION_LEN_S,
                "window_s": WINDOW_S,
                "stride_s": STRIDE_S,
                "truth_dt_ms": TRUTH_DT_MS,
                "model_path": str(args.model_path),
                "summaries": summaries,
            },
            f,
            indent=2,
        )
    print(f"Summary written to {args.out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
