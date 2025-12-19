from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHARED = Path(__file__).resolve().parents[1] / "_shared"
sys.path.insert(0, str(SHARED))

from plot_utils import SvgCanvas, draw_axes, draw_legend, linear_scale, nice_ticks, polyline


def load_series(path: Path):
    xs = []
    policy = []
    u_only = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            xs.append(float(row["tau_s"]))
            policy.append(float(row["p100_policy"]))
            u_only.append(float(row["p100_u_only"]))
    return xs, policy, u_only


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).with_name("plot.svg")))
    args = parser.parse_args()

    data_path = ROOT / "uccs_d4b_scan90/plots/ccs_timing_01/event_triggered_p100.csv"
    xs, policy, u_only = load_series(data_path)

    x_min = min(xs)
    x_max = max(xs)
    y_min = 0.0
    y_max = max(max(policy), max(u_only)) * 1.1

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

    scale_x = linear_scale(x_min, x_max, chart_left, chart_right)
    scale_y = linear_scale(y_min, y_max, chart_bottom, chart_top)

    canvas = SvgCanvas(width, height)
    canvas.add(
        f'<text x="{width / 2}" y="22" font-size="16" text-anchor="middle">'
        "Transition-aligned P(100ms) around label changes</text>\n"
    )

    x_ticks = nice_ticks(x_min, x_max, 6)
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
        "Time from transition (s)",
        "P(100ms)",
    )

    policy_points = list(zip(xs, policy))
    u_only_points = list(zip(xs, u_only))
    policy_line = polyline(policy_points, scale_x, scale_y)
    u_only_line = polyline(u_only_points, scale_x, scale_y)

    canvas.add(policy_line.replace("stroke-width=\"2\"", "stroke=\"#ff7f0e\" stroke-width=\"2\""))
    canvas.add(u_only_line.replace("stroke-width=\"2\"", "stroke=\"#d62728\" stroke-width=\"2\""))

    legend_items = [
        ("Policy (U+CCS)", "#ff7f0e", "line"),
        ("U-only (CCS-off)", "#d62728", "line"),
    ]
    draw_legend(canvas, legend_items, chart_right - 220, chart_top + 10)

    output_path = Path(args.out)
    output_path.write_text(canvas.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
