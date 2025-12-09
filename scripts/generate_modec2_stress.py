# -*- coding: utf-8 -*-
import json, random, math
from pathlib import Path

N_STEPS = 6352
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

out_dir = Path('Mode_C_2_シミュレート')
ccs_dir = out_dir / 'ccs'
ccs_dir.mkdir(exist_ok=True)

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


def compute_ccs(seq):
    trans_idx = [i for i in range(1, len(seq)) if seq[i] != seq[i - 1]]
    d_near = [0] * len(seq)
    next_t = trans_idx[0] if trans_idx else len(seq)
    prev_t = 0
    ti = 0
    for i in range(len(seq)):
        if ti < len(trans_idx) and i > trans_idx[ti]:
            prev_t = trans_idx[ti]
            ti += 1
            next_t = trans_idx[ti] if ti < len(trans_idx) else len(seq)
        d_prev = (i - prev_t) * 0.1
        d_next = (next_t - i) * 0.1
        d_near[i] = min(d_prev, d_next)
    S = [min(d / (T0_STEPS * 0.1), 1.0) for d in d_near]
    U_base = [1.0 - s for s in S]
    U = []
    for ub in U_base:
        noise = random.gauss(0, SIGMA_U)
        u = max(0.0, min(1.0, ub + noise))
        U.append(u)
    CCS = [0.7 * (1 - u) + 0.3 * s for u, s in zip(U, S)]
    return S, U, CCS


def decide_interval(ccs):
    if ccs <= TH_LOW:
        return 100
    if ccs <= TH_HIGH:
        return 500
    return 2000

lines = []
lines.append('// generated stress labels (synthetic high-transition)')
lines.append('#pragma once')
lines.append('struct SessionLabels { const char* id; const uint8_t* seq; uint16_t len; };')

for sess in SESSIONS:
    sid = sess['id']
    seq = gen_sequence(sess['p_stay'], sess['seed'])
    Svals, Uvals, CCSvals = compute_ccs(seq)
    intervals = [decide_interval(c) for c in CCSvals]
    transitions = sum(1 for i in range(1, len(seq)) if seq[i] != seq[i - 1])
    frac = {
        '100ms': intervals.count(100) / len(intervals),
        '500ms': intervals.count(500) / len(intervals),
        '2000ms': intervals.count(2000) / len(intervals),
    }
    arr_name = f"stress_{sid.lower()}"
    lines.append(f"static const uint8_t {arr_name}[] = {{" + ', '.join(str(x) for x in seq) + "};")
    lines.append(f"static const uint16_t n_{arr_name} = sizeof({arr_name})/sizeof({arr_name}[0]);")
    manifest_entries.append({
        'id': sid,
        'array': arr_name,
        'len': len(seq),
        'p_stay': sess['p_stay'],
        'seed': sess['seed'],
        'transitions': transitions,
        'interval_fraction': frac,
    })
    csv_path = ccs_dir / f"stress_{sid}.csv"
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        f.write('idx,label,S,U,CCS,T_adv\n')
        for i, (lbl, s, u, c, iv) in enumerate(zip(seq, Svals, Uvals, CCSvals, intervals)):
            f.write(f"{i},{lbl},{s:.4f},{u:.4f},{c:.4f},{iv}\n")

lines.append('static const SessionLabels SESSIONS_STRESS[] = {')
for e in manifest_entries:
    lines.append(f"  {{\"{e['id']}\", {e['array']}, n_{e['array']}}},")
lines.append('};')
lines.append('static const uint8_t NUM_SESSIONS_STRESS = sizeof(SESSIONS_STRESS)/sizeof(SESSIONS_STRESS[0]);')

(out_dir / 'labels_stress.h').write_text('\n'.join(lines), encoding='utf-8')
(out_dir / 'manifest_stress.json').write_text(json.dumps(manifest_entries, indent=2), encoding='utf-8')

print('done')
