from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHARED = Path(__file__).resolve().parents[1] / "_shared"
sys.path.insert(0, str(SHARED))

from plot_utils import SvgCanvas, draw_axes, draw_legend, linear_scale, nice_ticks, polyline


def load_energy_series(path: Path, sample_ms: int = 1000):
    times = []
    energies = []
    energy_mj = 0.0
    prev_ms = None
    prev_power_mw = None
    next_sample = 0

    with path.open(newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            first = row[0].strip()
            if first.startswith("#") or first == "ms":
                continue
            try:
                ms = float(row[0])
                power_mw = float(row[3])
            except (ValueError, IndexError):
                continue
            if prev_ms is not None:
                dt = ms - prev_ms
                if dt >= 0:
                    energy_mj += prev_power_mw * dt / 1000.0
            prev_ms = ms
            prev_power_mw = power_mw
            while ms >= next_sample:
                times.append(next_sample / 1000.0)
                energies.append(energy_mj)
                next_sample += sample_ms
    return times, energies


def mean_series(paths, sample_ms: int = 1000):
    series = [load_energy_series(Path(p), sample_ms) for p in paths]
    if not series:
        return [], []
    max_len = min(len(energies) for _, energies in series)
    times = list(range(max_len))
    mean_values = []
    for idx in range(max_len):
        vals = [energies[idx] for _, energies in series]
        mean_values.append(sum(vals) / len(vals))
    return times, mean_values


def load_condition_paths(per_trial_path: Path, conditions):
    cond_map = {cond: [] for cond in conditions}
    with per_trial_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            condition = row["condition"].strip()
            if condition not in cond_map:
                continue
            cond_map[condition].append(row["txsd_path"].strip())
    return cond_map


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).with_name("plot.svg")))
    args = parser.parse_args()

    d4b_per_trial = ROOT / "uccs_d4b_scan90/metrics/01/per_trial.csv"
    d4_per_trial = ROOT / "uccs_d4_scan90/metrics/01/per_trial.csv"

    d4b_conditions = [
        "S4_fixed100",
        "S4_fixed500",
        "S4_policy",
        "S4_ablation_ccs_off",
    ]
    d4_conditions = ["S4_ablation_u_shuf"]

    d4b_map = load_condition_paths(d4b_per_trial, d4b_conditions)
    d4_map = load_condition_paths(d4_per_trial, d4_conditions)

    series = []
    for condition in d4b_conditions:
        times, energies = mean_series(d4b_map[condition])
        series.append((condition, times, energies))
    for condition in d4_conditions:
        times, energies = mean_series(d4_map[condition])
        series.append((condition, times, energies))

    if not series:
        raise RuntimeError("No series data found.")

    max_time = min(max(times) for _, times, _ in series if times)
    max_index = int(max_time)
    trimmed = []
    y_max = 0.0
    for condition, times, energies in series:
        trimmed_times = times[: max_index + 1]
        trimmed_energies = energies[: max_index + 1]
        if trimmed_energies:
            y_max = max(y_max, max(trimmed_energies))
        trimmed.append((condition, trimmed_times, trimmed_energies))

    colors = {
        "S4_fixed100": "#1f77b4",
        "S4_fixed500": "#2ca02c",
        "S4_policy": "#ff7f0e",
        "S4_ablation_ccs_off": "#d62728",
        "S4_ablation_u_shuf": "#9467bd",
    }
    labels = {
        "S4_fixed100": "Fixed100",
        "S4_fixed500": "Fixed500",
        "S4_policy": "Policy (U+CCS)",
        "S4_ablation_ccs_off": "U-only (CCS-off)",
        "S4_ablation_u_shuf": "U-shuffle (U broken)",
    }

    width = 960
    height = 540
    margin_left = 90
    margin_right = 30
    margin_top = 40
    margin_bottom = 70
    chart_left = margin_left
    chart_right = width - margin_right
    chart_top = margin_top
    chart_bottom = height - margin_bottom

    x_min = 0.0
    x_max = max_time
    y_min = 0.0
    y_max = y_max * 1.05

    scale_x = linear_scale(x_min, x_max, chart_left, chart_right)
    scale_y = linear_scale(y_min, y_max, chart_bottom, chart_top)

    canvas = SvgCanvas(width, height)
    canvas.add(
        f'<text x="{width / 2}" y="22" font-size="16" text-anchor="middle">'
        "UCCS S4: cumulative energy vs time (mixed runs)</text>\n"
    )

    x_ticks = nice_ticks(x_min, x_max, 6)
    y_ticks = nice_ticks(y_min, y_max, 6)
    draw_axes(
        canvas,
        x_ticks,
        y_ticks,
        scale_x,
        scale_y,
        chart_left,
        chart_right,
        chart_top,
        chart_bottom,
        "Time (s)",
        "Cumulative energy (mJ)",
    )

    legend_items = []
    for condition, times, energies in trimmed:
        if not times:
            continue
        points = list(zip(times, energies))
        line = polyline(points, scale_x, scale_y)
        color = colors.get(condition, "#333")
        canvas.add(line.replace("stroke-width=\"2\"", f"stroke=\"{color}\" stroke-width=\"2\""))
        legend_items.append((labels.get(condition, condition), color, "line"))

    draw_legend(canvas, legend_items, chart_right - 220, chart_top + 10)

    output_path = Path(args.out)
    output_path.write_text(canvas.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
