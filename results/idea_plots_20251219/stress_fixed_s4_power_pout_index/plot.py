from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHARED = Path(__file__).resolve().parents[1] / "_shared"
sys.path.insert(0, str(SHARED))

from plot_utils import SvgCanvas, draw_axes, draw_bar, linear_scale, nice_ticks, svg_escape


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).with_name("plot.svg")))
    args = parser.parse_args()

    agg_path = ROOT / "results/stress_fixed/scan50/stress_causal_real_summary_1211_stress_agg_scan50_v5.csv"

    rows = []
    with agg_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["session"].strip() != "S4":
                continue
            interval = int(float(row["interval_ms"]))
            if interval not in (100, 500, 1000, 2000):
                continue
            avg_power = float(row["avg_power_mW_mean"])
            pout_1s = float(row["pout_1s_mean"])
            rows.append((interval, avg_power * pout_1s))

    rows.sort(key=lambda x: x[0])

    values = [v for _, v in rows]
    y_min = 0.0
    y_max = max(values) * 1.15

    width = 900
    height = 520
    margin_left = 90
    margin_right = 30
    margin_top = 40
    margin_bottom = 90
    chart_left = margin_left
    chart_right = width - margin_right
    chart_top = margin_top
    chart_bottom = height - margin_bottom

    scale_y = linear_scale(y_min, y_max, chart_bottom, chart_top)

    canvas = SvgCanvas(width, height)
    canvas.add(
        f'<text class="title" x="{width / 2}" y="22" text-anchor="middle">'
        "S4 fixed intervals: avg power * Pout(1s)</text>\n"
    )

    x_ticks = []
    y_ticks = nice_ticks(y_min, y_max, 5)
    draw_axes(
        canvas,
        x_ticks,
        y_ticks,
        lambda v: v,
        scale_y,
        chart_left,
        chart_right,
        chart_top,
        chart_bottom,
        "Interval (ms)",
        "Avg power * Pout (mW)",
    )

    bar_space = (chart_right - chart_left) / len(rows)
    bar_width = bar_space * 0.6
    colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"]

    for idx, (interval, value) in enumerate(rows):
        x_center = chart_left + bar_space * (idx + 0.5)
        bar_left = x_center - bar_width / 2
        y = scale_y(value)
        height_bar = chart_bottom - y
        draw_bar(canvas, bar_left, y, bar_width, height_bar, colors[idx % len(colors)])
        canvas.add(
            f'<text x="{x_center}" y="{chart_bottom + 24}" font-size="12" '
            f'text-anchor="middle">{svg_escape(str(interval))}</text>\n'
        )
        canvas.add(
            f'<text x="{x_center}" y="{y - 6}" font-size="12" text-anchor="middle">'
            f'{value:.2f}</text>\n'
        )

    output_path = Path(args.out)
    output_path.write_text(canvas.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
