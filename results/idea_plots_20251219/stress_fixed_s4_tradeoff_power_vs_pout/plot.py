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
    svg_escape,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).with_name("plot.svg")))
    args = parser.parse_args()

    agg_path = ROOT / "results/stress_fixed/scan50/stress_causal_real_summary_1211_stress_agg_scan50_v5.csv"

    points = []
    colors = {
        100: "#1f77b4",
        500: "#2ca02c",
        1000: "#ff7f0e",
        2000: "#d62728",
    }
    with agg_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["session"].strip() != "S4":
                continue
            interval = int(float(row["interval_ms"]))
            if interval not in colors:
                continue
            avg_power = float(row["avg_power_mW_mean"])
            pout_1s = float(row["pout_1s_mean"])
            points.append((interval, avg_power, pout_1s))

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
        f'<text x="{width / 2}" y="22" font-size="16" text-anchor="middle">'
        "S4 fixed intervals: avg power vs Pout(1s)</text>\n"
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
    for interval, avg_power, pout_1s in points:
        x = scale_x(avg_power)
        y = scale_y(pout_1s)
        color = colors[interval]
        draw_scatter_point(canvas, x, y, color)
        canvas.add(
            f'<text x="{x + 8}" y="{y - 6}" font-size="12">'
            f'{svg_escape(str(interval))}ms</text>\n'
        )
        legend_items.append((f"{interval} ms", color, "dot"))

    draw_legend(canvas, legend_items, chart_left + 10, chart_top + 10)

    output_path = Path(args.out)
    output_path.write_text(canvas.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
