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
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).with_name("plot.svg")))
    args = parser.parse_args()

    summary_path = ROOT / "results/final/tab/tab_summary_by_condition.csv"

    wanted = {
        ("uccs_d4b_scan90", "S4_fixed100"),
        ("uccs_d4b_scan90", "S4_fixed500"),
        ("uccs_d4b_scan90", "S4_policy"),
        ("uccs_d4b_scan90", "S4_ablation_ccs_off"),
        ("uccs_d4_scan90", "S4_ablation_u_shuf"),
    }
    label_map = {
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

    points = []
    with summary_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["dataset"].strip(), row["condition"].strip())
            if key not in wanted:
                continue
            avg_power = float(row["avg_power_mW_mean"])
            pout_1s = float(row["pout_1s_mean"])
            points.append((row["condition"].strip(), avg_power, pout_1s, row["dataset"].strip()))

    x_values = [p[1] for p in points]
    y_values = [p[2] for p in points]
    x_min = min(x_values)
    x_max = max(x_values)
    y_min = 0.0
    y_max = max(y_values) * 1.1

    width = 900
    height = 520
    margin_left = 90
    margin_right = 30
    margin_top = 40
    margin_bottom = 70
    chart_left = margin_left
    chart_right = width - margin_right
    chart_top = margin_top
    chart_bottom = height - margin_bottom

    scale_x = linear_scale(x_min, x_max, chart_left, chart_right)
    scale_y = linear_scale(y_min, y_max, chart_bottom, chart_top)

    canvas = SvgCanvas(width, height)
    canvas.add(
        f'<text class="title" x="{width / 2}" y="22" text-anchor="middle">'
        "UCCS S4: avg power vs Pout(1s) (mixed runs)</text>\n"
    )

    x_ticks = nice_ticks(x_min, x_max, 5)
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
        "Avg power (mW)",
        "Pout (1s)",
    )

    legend_items = []
    for condition, avg_power, pout_1s, dataset in points:
        x = scale_x(avg_power)
        y = scale_y(pout_1s)
        color = colors.get(condition, "#333")
        draw_scatter_point(canvas, x, y, color)
        label = label_map.get(condition, condition)
        legend_items.append((label, color, "dot"))

    draw_legend(canvas, legend_items, chart_left + 10, chart_top + 10)

    output_path = Path(args.out)
    output_path.write_text(canvas.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
