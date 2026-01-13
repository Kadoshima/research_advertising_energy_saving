from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHARED = Path(__file__).resolve().parents[1] / "_shared"
sys.path.insert(0, str(SHARED))

from plot_utils import SvgCanvas, draw_axes, draw_scatter_point, linear_scale, nice_ticks


def load_pairs(per_trial_path: Path):
    policy = {}
    u_only = {}
    with per_trial_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cond = row["condition"].strip()
            repeat_idx = row["repeat_idx"].strip()
            if cond == "S4_policy":
                policy[repeat_idx] = float(row["pout_1s"])
            elif cond == "S4_ablation_ccs_off":
                u_only[repeat_idx] = float(row["pout_1s"])
    pairs = []
    for repeat_idx in sorted(set(policy) & set(u_only)):
        pairs.append((repeat_idx, u_only[repeat_idx], policy[repeat_idx]))
    return pairs


def bootstrap_ci(values, n_samples=10000, seed=1):
    if not values:
        return 0.0, 0.0, 0.0
    random.seed(seed)
    means = []
    n = len(values)
    for _ in range(n_samples):
        sample = [random.choice(values) for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    mean_val = sum(values) / n
    low = means[int(0.025 * n_samples)]
    high = means[int(0.975 * n_samples)]
    return mean_val, low, high


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).with_name("plot.svg")))
    args = parser.parse_args()

    per_trial_path = ROOT / "uccs_d4b_scan90/metrics/01/per_trial.csv"
    pairs = load_pairs(per_trial_path)
    if not pairs:
        raise RuntimeError("No paired trials found.")

    u_values = [u for _, u, _ in pairs]
    p_values = [p for _, _, p in pairs]
    deltas = [p - u for _, u, p in pairs]

    y_min = 0.0
    y_max = max(max(u_values), max(p_values)) * 1.1
    dy_min = min(deltas) * 1.2
    dy_max = max(deltas) * 1.2
    if dy_min == dy_max:
        dy_min -= 0.01
        dy_max += 0.01

    width = 960
    height = 540
    margin_left = 80
    margin_right = 30
    margin_top = 40
    margin_bottom = 80
    gap = 60
    panel_width = (width - margin_left - margin_right - gap) / 2

    left_left = margin_left
    left_right = left_left + panel_width
    right_left = left_right + gap
    right_right = right_left + panel_width
    chart_top = margin_top
    chart_bottom = height - margin_bottom

    scale_left_x = linear_scale(1.0, 2.0, left_left, left_right)
    scale_left_y = linear_scale(y_min, y_max, chart_bottom, chart_top)

    scale_right_x = linear_scale(0.0, 1.0, right_left, right_right)
    scale_right_y = linear_scale(dy_min, dy_max, chart_bottom, chart_top)

    canvas = SvgCanvas(width, height)
    canvas.add(
        f'<text class="title" x="{width / 2}" y="22" text-anchor="middle">'
        "Policy vs U-only (paired): Pout(1s)</text>\n"
    )

    draw_axes(
        canvas,
        [1, 2],
        nice_ticks(y_min, y_max, 5),
        scale_left_x,
        scale_left_y,
        left_left,
        left_right,
        chart_top,
        chart_bottom,
        "Condition",
        "Pout(1s)",
    )

    for idx, (_, u_val, p_val) in enumerate(pairs):
        x1 = scale_left_x(1.0)
        x2 = scale_left_x(2.0)
        y1 = scale_left_y(u_val)
        y2 = scale_left_y(p_val)
        canvas.add(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="#999" stroke-width="1" />\n'
        )
        draw_scatter_point(canvas, x1, y1, "#d62728")
        draw_scatter_point(canvas, x2, y2, "#ff7f0e")

    canvas.add(
        f'<text x="{scale_left_x(1.0)}" y="{chart_bottom + 24}" font-size="12" '
        f'text-anchor="middle">U-only</text>\n'
    )
    canvas.add(
        f'<text x="{scale_left_x(2.0)}" y="{chart_bottom + 24}" font-size="12" '
        f'text-anchor="middle">Policy</text>\n'
    )

    draw_axes(
        canvas,
        [],
        nice_ticks(dy_min, dy_max, 5),
        scale_right_x,
        scale_right_y,
        right_left,
        right_right,
        chart_top,
        chart_bottom,
        "Delta (Policy - U-only)",
        "Delta Pout(1s)",
    )

    zero_y = scale_right_y(0.0)
    canvas.add(
        f'<line x1="{right_left}" y1="{zero_y}" x2="{right_right}" y2="{zero_y}" '
        f'stroke="#444" stroke-width="1" stroke-dasharray="4,4" />\n'
    )

    mean_delta, ci_low, ci_high = bootstrap_ci(deltas)
    x_center = scale_right_x(0.5)

    canvas.add(
        f'<line x1="{x_center}" y1="{scale_right_y(ci_low)}" '
        f'x2="{x_center}" y2="{scale_right_y(ci_high)}" '
        f'stroke="#111" stroke-width="2" />\n'
    )
    canvas.add(
        f'<line x1="{x_center - 8}" y1="{scale_right_y(ci_low)}" '
        f'x2="{x_center + 8}" y2="{scale_right_y(ci_low)}" '
        f'stroke="#111" stroke-width="2" />\n'
    )
    canvas.add(
        f'<line x1="{x_center - 8}" y1="{scale_right_y(ci_high)}" '
        f'x2="{x_center + 8}" y2="{scale_right_y(ci_high)}" '
        f'stroke="#111" stroke-width="2" />\n'
    )
    draw_scatter_point(canvas, x_center, scale_right_y(mean_delta), "#111")

    offsets = [-0.06, 0.0, 0.06]
    for idx, delta in enumerate(deltas):
        x = scale_right_x(0.5 + offsets[idx % len(offsets)])
        y = scale_right_y(delta)
        draw_scatter_point(canvas, x, y, "#555")

    output_path = Path(args.out)
    output_path.write_text(canvas.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
