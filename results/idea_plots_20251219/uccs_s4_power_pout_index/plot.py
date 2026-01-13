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

    summary_path = ROOT / "results/final/tab/tab_summary_by_condition.csv"

    wanted_order = [
        ("uccs_d4b_scan90", "S4_fixed100"),
        ("uccs_d4b_scan90", "S4_fixed500"),
        ("uccs_d4b_scan90", "S4_policy"),
        ("uccs_d4b_scan90", "S4_ablation_ccs_off"),
        ("uccs_d4_scan90", "S4_ablation_u_shuf"),
    ]
    label_map = {
        "S4_fixed100": "Fixed100",
        "S4_fixed500": "Fixed500",
        "S4_policy": "Policy",
        "S4_ablation_ccs_off": "U-only",
        "S4_ablation_u_shuf": "U-shuffle",
    }

    rows = {}
    with summary_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["dataset"].strip(), row["condition"].strip())
            if key not in wanted_order:
                continue
            avg_power = float(row["avg_power_mW_mean"])
            pout_1s = float(row["pout_1s_mean"])
            rows[key] = avg_power * pout_1s

    ordered_rows = [(key, rows[key]) for key in wanted_order if key in rows]

    values = [v for _, v in ordered_rows]
    y_min = 0.0
    y_max = max(values) * 1.15

    width = 980
    height = 520
    margin_left = 90
    margin_right = 30
    margin_top = 40
    margin_bottom = 100
    chart_left = margin_left
    chart_right = width - margin_right
    chart_top = margin_top
    chart_bottom = height - margin_bottom

    scale_y = linear_scale(y_min, y_max, chart_bottom, chart_top)

    canvas = SvgCanvas(width, height)
    canvas.add(
        f'<text class="title" x="{width / 2}" y="22" text-anchor="middle">'
        "UCCS S4: avg power * Pout(1s) (mixed runs)</text>\n"
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
        "Condition",
        "Avg power * Pout (mW)",
    )

    bar_space = (chart_right - chart_left) / len(ordered_rows)
    bar_width = bar_space * 0.6
    colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd"]

    for idx, (key, value) in enumerate(ordered_rows):
        dataset, condition = key
        x_center = chart_left + bar_space * (idx + 0.5)
        bar_left = x_center - bar_width / 2
        y = scale_y(value)
        height_bar = chart_bottom - y
        draw_bar(canvas, bar_left, y, bar_width, height_bar, colors[idx % len(colors)])
        label = label_map.get(condition, condition)
        suffix = "D4B" if dataset == "uccs_d4b_scan90" else "D4"
        canvas.add(
            f'<text x="{x_center}" y="{chart_bottom + 24}" font-size="12" '
            f'text-anchor="middle">{svg_escape(label)}</text>\n'
        )
        canvas.add(
            f'<text x="{x_center}" y="{chart_bottom + 40}" font-size="10" '
            f'text-anchor="middle">{svg_escape(suffix)}</text>\n'
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
