from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple


Color = str
Point = Tuple[float, float]


class SvgCanvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._lines: List[str] = []

    def add(self, line: str) -> None:
        self._lines.append(line)

    def extend(self, lines: Iterable[str]) -> None:
        self._lines.extend(lines)

    def render(self) -> str:
        header = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}">\\n'
            '<rect x="0" y="0" width="100%" height="100%" fill="#fff"/>\\n'
            '<style>\\n'
            '  text { font-family: "Helvetica", "Arial", sans-serif; fill: #111; }\\n'
            '  .title { font-size: 16px; font-weight: 600; }\\n'
            '  .axis { stroke: #111; stroke-width: 1.2; shape-rendering: crispEdges; }\\n'
            '  .grid { stroke: #e6e6e6; stroke-width: 1; shape-rendering: crispEdges; }\\n'
            '  .tick { stroke: #111; stroke-width: 1.2; shape-rendering: crispEdges; }\\n'
            '  .tick-label { font-size: 12px; fill: #222; }\\n'
            '  .axis-label { font-size: 14px; font-weight: 500; }\\n'
            '  .series-line { fill: none; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; }\\n'
            '  .pt { stroke: #111; stroke-width: 0.6; }\\n'
            '  .legend-bg { fill: #fff; fill-opacity: 0.85; stroke: #cfcfcf; stroke-width: 1; }\\n'
            '</style>\\n'
        )
        footer = '</svg>\n'
        return header + ''.join(self._lines) + footer


def svg_escape(text: str) -> str:
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def nice_ticks(min_val: float, max_val: float, tick_count: int = 5) -> List[float]:
    if min_val == max_val:
        return [min_val]
    span = max_val - min_val
    raw_step = span / max(1, tick_count)
    magnitude = 10 ** math.floor(math.log10(abs(raw_step)))
    residual = abs(raw_step) / magnitude
    if residual >= 5:
        step = 5 * magnitude
    elif residual >= 2:
        step = 2 * magnitude
    else:
        step = magnitude
    start = math.floor(min_val / step) * step
    end = math.ceil(max_val / step) * step
    ticks = []
    value = start
    while value <= end + step * 0.5:
        ticks.append(value)
        value += step
    return ticks


def format_tick(value: float) -> str:
    abs_val = abs(value)
    if abs_val >= 100:
        return f"{value:.0f}"
    if abs_val >= 10:
        return f"{value:.1f}"
    if abs_val >= 1:
        return f"{value:.2f}"
    return f"{value:.3f}"


def linear_scale(domain_min: float, domain_max: float, range_min: float, range_max: float):
    span = domain_max - domain_min if domain_max != domain_min else 1.0

    def scale(value: float) -> float:
        return range_min + (value - domain_min) * (range_max - range_min) / span

    return scale


def draw_axes(
    canvas: SvgCanvas,
    x_ticks: Sequence[float],
    y_ticks: Sequence[float],
    scale_x,
    scale_y,
    chart_left: float,
    chart_right: float,
    chart_top: float,
    chart_bottom: float,
    x_label: str,
    y_label: str,
) -> None:
    canvas.add(
        f'<line class="axis" x1="{chart_left}" y1="{chart_bottom}" '
        f'x2="{chart_right}" y2="{chart_bottom}" />\n'
    )
    canvas.add(
        f'<line class="axis" x1="{chart_left}" y1="{chart_top}" '
        f'x2="{chart_left}" y2="{chart_bottom}" />\n'
    )
    for tick in x_ticks:
        x = scale_x(tick)
        canvas.add(
            f'<line class="grid" x1="{x}" y1="{chart_top}" '
            f'x2="{x}" y2="{chart_bottom}" />\n'
        )
        canvas.add(
            f'<line class="tick" x1="{x}" y1="{chart_bottom}" '
            f'x2="{x}" y2="{chart_bottom + 6}" />\n'
        )
        canvas.add(
            f'<text class="tick-label" x="{x}" y="{chart_bottom + 20}" '
            f'text-anchor="middle">{svg_escape(format_tick(tick))}</text>\n'
        )
    for tick in y_ticks:
        y = scale_y(tick)
        canvas.add(
            f'<line class="grid" x1="{chart_left}" y1="{y}" '
            f'x2="{chart_right}" y2="{y}" />\n'
        )
        canvas.add(
            f'<line class="tick" x1="{chart_left - 6}" y1="{y}" '
            f'x2="{chart_left}" y2="{y}" />\n'
        )
        canvas.add(
            f'<text class="tick-label" x="{chart_left - 10}" y="{y}" '
            f'text-anchor="end" dominant-baseline="middle">'
            f'{svg_escape(format_tick(tick))}</text>\n'
        )
    canvas.add(
        f'<text x="{(chart_left + chart_right) / 2}" y="{chart_bottom + 40}" '
        f'class="axis-label" text-anchor="middle">{svg_escape(x_label)}</text>\n'
    )
    canvas.add(
        f'<text x="{chart_left - 50}" y="{(chart_top + chart_bottom) / 2}" '
        f'class="axis-label" text-anchor="middle" '
        f'transform="rotate(-90 {chart_left - 50},{(chart_top + chart_bottom) / 2})">'
        f'{svg_escape(y_label)}</text>\n'
    )


def draw_legend(
    canvas: SvgCanvas,
    items: Sequence[Tuple[str, Color, str]],
    x: float,
    y: float,
    row_height: float = 18,
) -> None:
    if not items:
        return
    max_len = max(len(label) for label, _, _ in items)
    box_w = 26 + max_len * 6.5 + 16
    box_h = row_height * len(items) + 14
    canvas.add(
        f'<rect class="legend-bg" x="{x - 8}" y="{y - 12}" '
        f'width="{box_w}" height="{box_h}" rx="4" ry="4" />\n'
    )
    for idx, (label, color, marker) in enumerate(items):
        y_pos = y + idx * row_height
        if marker == 'line':
            canvas.add(
                f'<line class="series-line" x1="{x}" y1="{y_pos}" '
                f'x2="{x + 20}" y2="{y_pos}" stroke="{color}" />\n'
            )
        else:
            canvas.add(
                f'<circle class="pt" cx="{x + 10}" cy="{y_pos}" r="4" fill="{color}" />\n'
            )
        canvas.add(
            f'<text x="{x + 26}" y="{y_pos + 4}" font-size="12">'
            f'{svg_escape(label)}</text>\n'
        )


def polyline(points: Sequence[Point], scale_x, scale_y, color: Color | None = None) -> str:
    coords = ' '.join(f"{scale_x(x)},{scale_y(y)}" for x, y in points)
    color_attr = f' stroke="{color}"' if color else ""
    return f'<polyline class="series-line"{color_attr} points="{coords}" />\n'


def draw_scatter_point(canvas: SvgCanvas, x: float, y: float, color: Color) -> None:
    canvas.add(
        f'<circle class="pt" cx="{x}" cy="{y}" r="4" fill="{color}" />\n'
    )


def draw_bar(
    canvas: SvgCanvas,
    x: float,
    y: float,
    width: float,
    height: float,
    color: Color,
) -> None:
    canvas.add(
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'fill="{color}" stroke="#111" stroke-width="0.5" />\n'
    )
