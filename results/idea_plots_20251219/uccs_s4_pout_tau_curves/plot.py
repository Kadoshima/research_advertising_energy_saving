from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHARED = Path(__file__).resolve().parents[1] / "_shared"
sys.path.insert(0, str(SHARED))

from plot_utils import (
    SvgCanvas,
    draw_axes,
    draw_legend,
    draw_scatter_point,
    linear_scale,
    nice_ticks,
    polyline,
    svg_escape,
)


def load_pout_means(per_trial_path: Path, conditions):
    values = {cond: {1: [], 2: [], 3: []} for cond in conditions}
    with per_trial_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cond = row["condition"].strip()
            if cond not in values:
                continue
            values[cond][1].append(float(row["pout_1s"]))
            values[cond][2].append(float(row["pout_2s"]))
            values[cond][3].append(float(row["pout_3s"]))
    means = {}
    for cond, tau_map in values.items():
        means[cond] = {
            tau: sum(vals) / len(vals) if vals else 0.0
            for tau, vals in tau_map.items()
        }
    return means


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).with_name("plot.svg")))
    args = parser.parse_args()

    d4b_path = ROOT / "uccs_d4b_scan90/metrics/01/per_trial.csv"
    d4_path = ROOT / "uccs_d4_scan90/metrics/01/per_trial.csv"

    d4b_conditions = [
        "S4_fixed100",
        "S4_fixed500",
        "S4_policy",
        "S4_ablation_ccs_off",
    ]
    d4_conditions = ["S4_ablation_u_shuf"]

    d4b_means = load_pout_means(d4b_path, d4b_conditions)
    d4_means = load_pout_means(d4_path, d4_conditions)

    series = {**d4b_means, **d4_means}

    labels = {
        "S4_fixed100": "Fixed100",
        "S4_fixed500": "Fixed500",
        "S4_policy": "Policy (U+CCS)",
        "S4_ablation_ccs_off": "U-only (CCS-off)",
        "S4_ablation_u_shuf": "U-shuffle (U broken)",
    }
    colors = {
        "S4_fixed100": "#1f77b4",
        "S4_fixed500": "#2ca02c",
        "S4_policy": "#ff7f0e",
        "S4_ablation_ccs_off": "#d62728",
        "S4_ablation_u_shuf": "#9467bd",
    }

    taus = [1.0, 2.0, 3.0]
    y_values = [val for cond in series.values() for val in cond.values()]
    y_max = max(y_values) * 1.1 if y_values else 1.0

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

    x_min = 1.0
    x_max = 3.0
    y_min = 0.0

    scale_x = linear_scale(x_min, x_max, chart_left, chart_right)
    scale_y = linear_scale(y_min, y_max, chart_bottom, chart_top)

    canvas = SvgCanvas(width, height)
    canvas.add(
        f'<text x="{width / 2}" y="22" font-size="16" text-anchor="middle">'
        "UCCS S4: Pout(tau) curves (tau = 1..3 s)</text>\n"
    )

    x_ticks = [1, 2, 3]
    y_ticks = nice_ticks(y_min, y_max, 5)
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
        "Tau (s)",
        "Pout(tau)",
    )

    legend_items = []
    for cond, tau_map in series.items():
        points = [(tau, tau_map[int(tau)]) for tau in taus]
        line = polyline(points, scale_x, scale_y)
        color = colors.get(cond, "#333")
        canvas.add(line.replace("stroke-width=\"2\"", f"stroke=\"{color}\" stroke-width=\"2\""))
        for x, y in points:
            draw_scatter_point(canvas, scale_x(x), scale_y(y), color)
        legend_items.append((labels.get(cond, cond), color, "line"))

    draw_legend(canvas, legend_items, chart_right - 220, chart_top + 10)

    output_path = Path(args.out)
    output_path.write_text(canvas.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
