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


def load_s4_manifest(manifest_path: Path):
    interval_to_trial = {}
    with manifest_path.open(newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row:
                continue
            trial_id = row[0].strip() if len(row) > 0 else ""
            mode = row[2].strip() if len(row) > 2 else ""
            session = row[3].strip() if len(row) > 3 else ""
            session_key = session.split()[0] if session else ""
            if session_key != "S4":
                continue
            if not mode.startswith("FIXED_"):
                continue
            try:
                interval = int(mode.split("_")[1])
            except (IndexError, ValueError):
                continue
            interval_to_trial[interval] = trial_id
    return interval_to_trial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).with_name("plot.svg")))
    args = parser.parse_args()

    manifest_path = ROOT / "data/1211_modeC2prime_stress_fixed/full/manifest.csv"
    tx_dir = ROOT / "data/1211_modeC2prime_stress_fixed/full/TX"

    interval_map = load_s4_manifest(manifest_path)
    intervals = [100, 500, 1000, 2000]
    colors = {
        100: "#1f77b4",
        500: "#2ca02c",
        1000: "#ff7f0e",
        2000: "#d62728",
    }

    series = []
    for interval in intervals:
        trial_id = interval_map.get(interval)
        if not trial_id:
            raise RuntimeError(f"S4 interval {interval} not found in manifest")
        path = tx_dir / f"trial_{trial_id}_on.csv"
        times, energies = load_energy_series(path)
        series.append((interval, times, energies))

    max_time = min(max(times) for _, times, _ in series)
    max_index = int(max_time)
    trimmed = []
    y_max = 0.0
    for interval, times, energies in series:
        if len(times) <= max_index:
            max_index = len(times) - 1
        trimmed_times = times[: max_index + 1]
        trimmed_energies = energies[: max_index + 1]
        y_max = max(y_max, max(trimmed_energies))
        trimmed.append((interval, trimmed_times, trimmed_energies))

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
        "S4 fixed intervals: cumulative energy vs time</text>\n"
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
    for interval, times, energies in trimmed:
        points = list(zip(times, energies))
        line = polyline(points, scale_x, scale_y)
        canvas.add(line.replace("stroke-width=\"2\"", f"stroke=\"{colors[interval]}\" stroke-width=\"2\""))
        legend_items.append((f"{interval} ms", colors[interval], "line"))

    draw_legend(canvas, legend_items, chart_right - 160, chart_top + 10)

    output_path = Path(args.out)
    output_path.write_text(canvas.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
