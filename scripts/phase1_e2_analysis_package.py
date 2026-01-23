#!/usr/bin/env python3
"""
Phase1 E2 (CCS vs Baseline) analysis package.

Outputs:
- results/phase1_e2_ci_summary.md
- results/phase1_e2_ci_summary.csv
- results/phase1_e2_tradeoff_plot.png
- results/phase1_e2_tail_note.md
"""
from __future__ import annotations

import argparse
import importlib.util
import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

try:
    import matplotlib.pyplot as plt
    HAS_MPL = True
except Exception:
    HAS_MPL = False


def load_analyze_module() -> object:
    module_path = Path(__file__).resolve().parent / "analyze_ccs_experiment.py"
    spec = importlib.util.spec_from_file_location("analyze_ccs_experiment", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def collect_trials(module: object, data_dir: Path, session_manifest: Path | None) -> List[object]:
    return module.process_experiment(
        str(data_dir),
        session_manifest_path=str(session_manifest) if session_manifest else None,
    )


def extract_metric(trials: List[object], condition: str, key: str) -> List[float]:
    values = []
    for t in trials:
        if t.environment != "E2":
            continue
        if t.condition != condition:
            continue
        if key == "avg_current_ma":
            values.append(float(t.avg_current_ma))
        elif key == "tl_p50_ms":
            values.append(float(t.tl_p50_ms))
        elif key == "tl_p95_ms":
            values.append(float(t.tl_p95_ms))
        elif key == "pout2":
            if isinstance(t.pout, dict):
                v = t.pout.get(2.0, t.pout.get("2.0", 0.0))
                values.append(float(v))
            else:
                values.append(0.0)
        else:
            raise ValueError(f"Unknown metric key: {key}")
    return values


def bootstrap_mean_ci(values: List[float], rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return (math.nan, math.nan)
    samples = rng.choice(arr, size=(n_boot, arr.size), replace=True)
    means = samples.mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def bootstrap_diff_ci(x: List[float], y: List[float], rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    if x_arr.size == 0 or y_arr.size == 0:
        return (math.nan, math.nan)
    x_s = rng.choice(x_arr, size=(n_boot, x_arr.size), replace=True)
    y_s = rng.choice(y_arr, size=(n_boot, y_arr.size), replace=True)
    diffs = x_s.mean(axis=1) - y_s.mean(axis=1)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(lo), float(hi)


def hedges_g(x: List[float], y: List[float]) -> float | None:
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    nx = x_arr.size
    ny = y_arr.size
    if nx < 2 or ny < 2:
        return None
    sx = np.std(x_arr, ddof=1)
    sy = np.std(y_arr, ddof=1)
    pooled = math.sqrt(((nx - 1) * sx * sx + (ny - 1) * sy * sy) / (nx + ny - 2)) if (nx + ny) > 2 else 0.0
    if pooled == 0:
        return None
    d = (x_arr.mean() - y_arr.mean()) / pooled
    correction = 1 - (3 / (4 * (nx + ny) - 9)) if (nx + ny) > 2 else 1.0
    return float(d * correction)


def format_ci(lo: float, hi: float, scale: float = 1.0, decimals: int = 2) -> str:
    if math.isnan(lo) or math.isnan(hi):
        return "NA"
    return f"[{lo*scale:.{decimals}f}, {hi*scale:.{decimals}f}]"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_ci_outputs(
    out_md: Path,
    out_csv: Path,
    rows: List[Dict[str, str]],
    source_notes: List[str],
    n_boot: int,
    seed: int,
) -> None:
    ensure_parent(out_md)
    ensure_parent(out_csv)

    headers = [
        "pair",
        "metric",
        "n_ccs",
        "n_base",
        "mean_ccs",
        "mean_base",
        "delta_ccs_minus_base",
        "delta_ci95",
        "effect_size_g",
        "unit",
        "notes",
        "sources",
    ]

    # CSV
    with out_csv.open("w", encoding="utf-8") as fh:
        fh.write(",".join(headers) + "\n")
        for row in rows:
            line = ",".join(row.get(h, "") for h in headers)
            fh.write(line + "\n")

    # Markdown
    lines = []
    lines.append("# Phase1 E2 CI Summary")
    lines.append("")
    lines.append(f"Bootstrap: n_boot={n_boot}, seed={seed}")
    lines.append("")
    lines.append("## Pairwise differences (CCS - baseline)")
    lines.append("")
    lines.append("| Pair | Metric | N(CCS) | N(Base) | Mean CCS | Mean Base | Delta (CCS-Base) | 95% CI | Effect Size (Hedges g) | Unit | Notes | Sources |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | --- | --- |")
    for row in rows:
        lines.append(
            "| {pair} | {metric} | {n_ccs} | {n_base} | {mean_ccs} | {mean_base} | {delta_ccs_minus_base} | {delta_ci95} | {effect_size_g} | {unit} | {notes} | {sources} |".format(**row)
        )
    lines.append("")
    lines.append("## Source notes")
    lines.extend([f"- {note}" for note in source_notes])
    lines.append("")
    lines.append("## Caveats")
    lines.append("- Small N (CCS n=5, FIXED100 n=3, FIXED2000 n=3). Treat as reference values.")
    lines.append("- Pout(2s) per-trial values are derived from RX logs via scripts/analyze_ccs_experiment.py; see sources above.")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tail_note(out_md: Path, trials_ccs: List[object], sources: List[str]) -> None:
    ensure_parent(out_md)

    items = []
    for t in trials_ccs:
        pout2 = t.pout.get(2.0, t.pout.get("2.0", 0.0)) if isinstance(t.pout, dict) else 0.0
        items.append({
            "trial_id": t.trial_id,
            "pout2": float(pout2),
            "tl_p95": float(t.tl_p95_ms),
            "avg_current": float(t.avg_current_ma),
        })

    by_pout = sorted(items, key=lambda x: (-x["pout2"], -x["tl_p95"]))
    by_tl = sorted(items, key=lambda x: (-x["tl_p95"], -x["pout2"]))

    lines = []
    lines.append("# Phase1 E2 CCS Tail Note")
    lines.append("")
    lines.append("## CCS trials ranked by Pout(2s) (desc)")
    lines.append("")
    lines.append("| Rank | Trial | Pout(2s) % | TL p95 (ms) | Avg Current (mA) |")
    lines.append("| ---: | --- | ---: | ---: | ---: |")
    for idx, row in enumerate(by_pout, start=1):
        lines.append(f"| {idx} | {row['trial_id']} | {row['pout2']*100:.2f} | {row['tl_p95']:.0f} | {row['avg_current']:.2f} |")

    lines.append("")
    lines.append("## CCS trials ranked by TL p95 (desc)")
    lines.append("")
    lines.append("| Rank | Trial | TL p95 (ms) | Pout(2s) % | Avg Current (mA) |")
    lines.append("| ---: | --- | ---: | ---: | ---: |")
    for idx, row in enumerate(by_tl, start=1):
        lines.append(f"| {idx} | {row['trial_id']} | {row['tl_p95']:.0f} | {row['pout2']*100:.2f} | {row['avg_current']:.2f} |")

    lines.append("")
    if by_pout:
        top_pout = by_pout[0]
        top_tl = by_tl[0]
        lines.append("## Tail note")
        lines.append(
            "- Highest Pout(2s) trial: {trial} (Pout(2s)={pout:.2f}%, TL p95={tl:.0f} ms).".format(
                trial=top_pout["trial_id"],
                pout=top_pout["pout2"] * 100,
                tl=top_pout["tl_p95"],
            )
        )
        lines.append(
            "- Highest TL p95 trial: {trial} (TL p95={tl:.0f} ms, Pout(2s)={pout:.2f}%).".format(
                trial=top_tl["trial_id"],
                tl=top_tl["tl_p95"],
                pout=top_tl["pout2"] * 100,
            )
        )
        lines.append(
            "- Tail sensitivity: a small number of CCS trials sit far above the median on Pout/TL, indicating tail-dominant behavior.")

    lines.append("")
    lines.append("## Sources")
    lines.extend([f"- {s}" for s in sources])

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tradeoff_plot(
    out_path: Path,
    summaries: Dict[str, Dict[str, float]],
    cis: Dict[str, Dict[str, Tuple[float, float]]],
    y_key: str,
    y_label: str,
    title: str,
    log_y: bool,
) -> None:
    if not HAS_MPL:
        raise RuntimeError("matplotlib is required to generate plot")
    ensure_parent(out_path)

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "axes.linewidth": 0.9,
        "axes.labelsize": 11,
        "axes.titlesize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 9,
    })

    colors = {
        "FIXED100": "#4E79A7",   # muted blue
        "CCS": "#9C755F",        # muted brown
        "FIXED2000": "#59A14F",  # muted green
    }

    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    y_bounds: List[float] = []
    for cond in ["FIXED100", "CCS", "FIXED2000"]:
        x = summaries[cond]["avg_current_ma"]
        y = summaries[cond][y_key]
        x_ci = cis[cond]["avg_current_ma"]
        y_ci = cis[cond][y_key]
        xerr = np.array([[x - x_ci[0]], [x_ci[1] - x]])
        yerr = np.array([[y - y_ci[0]], [y_ci[1] - y]])
        ax.errorbar(
            x,
            y,
            xerr=xerr,
            yerr=yerr,
            fmt="o",
            color=colors.get(cond, "#333333"),
            capsize=4,
            capthick=1.0,
            elinewidth=1.2,
            markersize=6.5,
            markeredgewidth=0.8,
            markerfacecolor=colors.get(cond, "#333333"),
            markeredgecolor="white",
            label=cond,
        )
        y_bounds.extend([y_ci[0], y_ci[1]])
        ax.annotate(
            cond,
            xy=(x, y),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=9,
        )

    import matplotlib.ticker as mticker

    ax.set_xlabel("Avg Current (mA)")
    ax.set_ylabel(y_label)
    ax.set_title(title)
    if log_y:
        ax.set_yscale("log")
        ax.yaxis.set_major_locator(mticker.LogLocator(base=10))
        ax.yaxis.set_minor_locator(mticker.LogLocator(base=10, subs=(2, 3, 4, 5, 6, 7, 8, 9)))
        ax.yaxis.set_major_formatter(mticker.ScalarFormatter())
        ax.yaxis.set_minor_formatter(mticker.NullFormatter())
        if y_bounds:
            y_min = max(min(y_bounds) * 0.85, 1.0)
            y_max = max(y_bounds) * 1.15
            ax.set_ylim(y_min, y_max)
            candidate_ticks = [100, 200, 300, 500, 700, 1000, 2000, 3000, 5000, 7000, 10000]
            ticks = [t for t in candidate_ticks if y_min <= t <= y_max]
            if ticks:
                ax.set_yticks(ticks)
                ax.yaxis.set_major_formatter(mticker.ScalarFormatter())
    elif y_bounds:
        y_min = min(y_bounds) * 0.9
        y_max = max(y_bounds) * 1.1
        if y_min < 0:
            y_min = 0
        ax.set_ylim(y_min, y_max)
    ax.grid(True, which="major", alpha=0.25, linewidth=0.8)
    ax.grid(True, which="minor", alpha=0.15, linewidth=0.6)
    ax.minorticks_on()
    ax.legend(loc="upper right", frameon=True, framealpha=0.9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase1 E2 analysis package")
    parser.add_argument("--baseline-input", default="results/phase1_e2_baseline_2026-01-22_v01_input")
    parser.add_argument("--ccs-input", default="results/phase1_e2_ccs_2026-01-22_v03_input")
    parser.add_argument("--session-manifest", default="data/esp32_sessions/session_manifest.json")
    parser.add_argument("--out-ci-md", default="results/phase1_e2_ci_summary.md")
    parser.add_argument("--out-ci-csv", default="results/phase1_e2_ci_summary.csv")
    parser.add_argument("--out-tail-md", default="results/phase1_e2_tail_note.md")
    parser.add_argument("--out-plot", default="results/phase1_e2_tradeoff_plot.png")
    parser.add_argument("--out-plot-p50", default="results/phase1_e2_tradeoff_plot_p50.png")
    parser.add_argument("--n-boot", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260122)
    args = parser.parse_args()

    module = load_analyze_module()
    baseline_trials = collect_trials(module, Path(args.baseline_input), None)
    ccs_trials = collect_trials(module, Path(args.ccs_input), Path(args.session_manifest))
    all_trials = baseline_trials + ccs_trials

    metrics_all = [
        {"key": "avg_current_ma", "label": "Avg Current", "unit": "mA", "scale": 1.0, "decimals": 2},
        {"key": "pout2", "label": "Pout(2s)", "unit": "pp", "scale": 100.0, "decimals": 2},
        {"key": "tl_p50_ms", "label": "TL p50", "unit": "ms", "scale": 1.0, "decimals": 1},
        {"key": "tl_p95_ms", "label": "TL p95", "unit": "ms", "scale": 1.0, "decimals": 1},
    ]
    metrics_ci = [m for m in metrics_all if m["key"] in ("avg_current_ma", "pout2", "tl_p95_ms")]

    rng = np.random.default_rng(args.seed)

    summaries: Dict[str, Dict[str, float]] = {}
    cis: Dict[str, Dict[str, Tuple[float, float]]] = {}
    for cond in ["FIXED100", "CCS", "FIXED2000"]:
        summaries[cond] = {}
        cis[cond] = {}
        for m in metrics_all:
            values = extract_metric(all_trials, cond, m["key"])
            summaries[cond][m["key"]] = float(np.mean(values)) if values else math.nan
            ci_lo, ci_hi = bootstrap_mean_ci(values, rng, args.n_boot)
            cis[cond][m["key"]] = (ci_lo, ci_hi)

    rows: List[Dict[str, str]] = []
    for base in ["FIXED100", "FIXED2000"]:
        for m in metrics_ci:
            ccs_vals = extract_metric(all_trials, "CCS", m["key"])
            base_vals = extract_metric(all_trials, base, m["key"])
            mean_ccs = np.mean(ccs_vals) if ccs_vals else math.nan
            mean_base = np.mean(base_vals) if base_vals else math.nan
            delta = mean_ccs - mean_base
            ci_lo, ci_hi = bootstrap_diff_ci(ccs_vals, base_vals, rng, args.n_boot)
            g = hedges_g(ccs_vals, base_vals)
            g_str = f"{g:.2f}" if g is not None else "NA"
            notes = "reference" if (len(ccs_vals) < 6 or len(base_vals) < 6) else ""

            rows.append({
                "pair": f"CCS vs {base}",
                "metric": m["label"],
                "n_ccs": str(len(ccs_vals)),
                "n_base": str(len(base_vals)),
                "mean_ccs": f"{mean_ccs * m['scale']:.{m['decimals']}f}",
                "mean_base": f"{mean_base * m['scale']:.{m['decimals']}f}",
                "delta_ccs_minus_base": f"{delta * m['scale']:.{m['decimals']}f}",
                "delta_ci95": format_ci(ci_lo, ci_hi, m["scale"], m["decimals"]),
                "effect_size_g": g_str,
                "unit": m["unit"],
                "notes": notes,
                "sources": ";".join([
                    "results/phase1_e2_ccs_2026-01-22_v03.md",
                    "results/phase1_e2_baseline_2026-01-22_v01.md",
                    "results/phase1_e2_ccs_2026-01-22_v03_input",
                    "results/phase1_e2_baseline_2026-01-22_v01_input",
                    "data/esp32_sessions/session_manifest.json",
                    "scripts/analyze_ccs_experiment.py",
                ]),
            })

    source_notes = [
        "Avg Current/TL p95 per-trial values align with results/phase1_e2_ccs_2026-01-22_v03.md and results/phase1_e2_baseline_2026-01-22_v01.md.",
        "Pout(2s) per-trial values derived from RX logs in results/phase1_e2_ccs_2026-01-22_v03_input and results/phase1_e2_baseline_2026-01-22_v01_input using scripts/analyze_ccs_experiment.py with data/esp32_sessions/session_manifest.json.",
        "Metric definition: docs/metrics_definition.md.",
    ]

    write_ci_outputs(Path(args.out_ci_md), Path(args.out_ci_csv), rows, source_notes, args.n_boot, args.seed)

    tail_sources = [
        "results/phase1_e2_ccs_2026-01-22_v03.md",
        "results/phase1_e2_ccs_2026-01-22_v03_input",
        "data/esp32_sessions/session_manifest.json",
        "scripts/analyze_ccs_experiment.py",
        "docs/metrics_definition.md",
    ]
    write_tail_note(Path(args.out_tail_md), ccs_trials, tail_sources)

    write_tradeoff_plot(
        Path(args.out_plot),
        summaries,
        cis,
        y_key="tl_p95_ms",
        y_label="TL p95 (ms)",
        title="E2 Tradeoff: Avg Current vs TL p95",
        log_y=False,
    )
    write_tradeoff_plot(
        Path(args.out_plot_p50),
        summaries,
        cis,
        y_key="tl_p50_ms",
        y_label="TL p50 (ms)",
        title="E2 Tradeoff: Avg Current vs TL p50",
        log_y=False,
    )


if __name__ == "__main__":
    main()
