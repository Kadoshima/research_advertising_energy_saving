# -*- coding: utf-8 -*-
"""
ストレス用の高遷移ラベル列に「因果的（未来を見ない）」CCSを付与して
シミュレーション用CSVを生成するスクリプト。

出力先:
  Mode_C_2_シミュレート_causal/
    ├── ccs/stress_S*.csv  (idx,label,S,U,CCS,T_adv)
    └── manifest_stress_causal.json (p_stay,seed,遷移数,T_adv比率など)

設計ポイント:
  - ラベル列は既存のストレス仕様と同じ (p_stay=0.99×3本, 0.98×3本)
  - CCSは「直近遷移からの経過時間」のみで安定度Sを定義（未来は見ない）
  - U = 1 - S + N(0, σ^2), σ=0.05 をクリップ [0,1]
  - CCS = 0.7*(1-U) + 0.3*S
  - T_advマッピング: CCS<=0.3→100ms, 0.3<CCS<=0.7→500ms, >0.7→2000ms
"""

import json
import random
from pathlib import Path

import math

N_STEPS = 6352  # 100msグリッドで約10.6分
CLASSES = list(range(12))
SESSIONS = [
    {"id": "S1", "p_stay": 0.99, "seed": 101},
    {"id": "S2", "p_stay": 0.99, "seed": 102},
    {"id": "S3", "p_stay": 0.99, "seed": 103},
    {"id": "S4", "p_stay": 0.98, "seed": 201},
    {"id": "S5", "p_stay": 0.98, "seed": 202},
    {"id": "S6", "p_stay": 0.98, "seed": 203},
]

T0_STEPS = 50  # 5s
SIGMA_U = 0.05
TH_LOW = 0.3
TH_HIGH = 0.7

out_dir = Path("Mode_C_2_シミュレート_causal")
ccs_dir = out_dir / "ccs"
ccs_dir.mkdir(parents=True, exist_ok=True)

manifest_entries = []


def gen_sequence(p_stay: float, seed: int):
    random.seed(seed)
    seq = [random.choice(CLASSES)]
    while len(seq) < N_STEPS:
        if random.random() < p_stay:
            seq.append(seq[-1])
        else:
            nxt = random.choice([c for c in CLASSES if c != seq[-1]])
            seq.append(nxt)
    return seq


def compute_ccs_causal(seq):
    # 因果版: 直近遷移からの経過のみでSを決める
    trans_idx = [i for i in range(1, len(seq)) if seq[i] != seq[i - 1]]
    last_change = 0
    S_list = []
    U_list = []
    CCS_list = []
    Tadv_list = []

    for t in range(len(seq)):
        if t in trans_idx:
            last_change = t
        d_prev = t - last_change
        S = min(d_prev / T0_STEPS, 1.0)
        U_base = 1.0 - S
        U = max(0.0, min(1.0, U_base + random.gauss(0.0, SIGMA_U)))
        CCS = 0.7 * (1 - U) + 0.3 * S
        if CCS <= TH_LOW:
            t_adv = 100
        elif CCS <= TH_HIGH:
            t_adv = 500
        else:
            t_adv = 2000
        S_list.append(S)
        U_list.append(U)
        CCS_list.append(CCS)
        Tadv_list.append(t_adv)
    return S_list, U_list, CCS_list, Tadv_list


def summarize_interval_frac(t_adv_list):
    total = len(t_adv_list)
    frac_100 = sum(1 for t in t_adv_list if t == 100) / total
    frac_500 = sum(1 for t in t_adv_list if t == 500) / total
    frac_2000 = sum(1 for t in t_adv_list if t == 2000) / total
    return frac_100, frac_500, frac_2000


def write_csv(path, seq, S_list, U_list, CCS_list, Tadv_list):
    with path.open("w", encoding="utf-8") as f:
        f.write("idx,label,S,U,CCS,T_adv\n")
        for i, (lb, s, u, c, tadv) in enumerate(
            zip(seq, S_list, U_list, CCS_list, Tadv_list)
        ):
            f.write(f"{i},{lb},{s:.6f},{u:.6f},{c:.6f},{tadv}\n")


def main():
    for sess in SESSIONS:
        seq = gen_sequence(sess["p_stay"], sess["seed"])
        S_list, U_list, CCS_list, Tadv_list = compute_ccs_causal(seq)
        csv_path = ccs_dir / f"stress_causal_{sess['id']}.csv"
        write_csv(csv_path, seq, S_list, U_list, CCS_list, Tadv_list)

        frac100, frac500, frac2000 = summarize_interval_frac(Tadv_list)
        manifest_entries.append(
            {
                "id": sess["id"],
                "p_stay": sess["p_stay"],
                "seed": sess["seed"],
                "transitions": sum(1 for i in range(1, len(seq)) if seq[i] != seq[i - 1]),
                "interval_frac": {
                    "100ms": round(frac100, 4),
                    "500ms": round(frac500, 4),
                    "2000ms": round(frac2000, 4),
                },
            }
        )

    manifest = {
        "note": "Causal CCS: S uses only time since last transition (no future lookahead). U=1-S+N(0,0.05^2). T_adv thresholds 0.3/0.7.",
        "sessions": manifest_entries,
    }
    with (out_dir / "manifest_stress_causal.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
