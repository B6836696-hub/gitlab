"""Server-side SVG charts for the Lab 04 simulator.

The charts are plain inline SVG generated from the parsed ngspice arrays. No
chart library or client-side JavaScript is required, and every plotted point
comes from the simulation output rather than from hard-coded artwork.
"""

from __future__ import annotations

import math

FONT = "'Segoe UI', Tahoma, 'Noto Sans Thai', system-ui, sans-serif"

COLOR_GAIN = "#0f766e"
COLOR_PHASE = "#4f46e5"
COLOR_VIN = "#0284c7"
COLOR_VOUT = "#ea580c"
COLOR_GRID = "#e6ebf4"
COLOR_AXIS = "#64748b"
COLOR_TEXT = "#334155"


def _freq_label(value: float) -> str:
    if value >= 1e6:
        return f"{value / 1e6:g}M"
    if value >= 1e3:
        return f"{value / 1e3:g}k"
    return f"{value:g}"


def _nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    if not math.isfinite(low) or not math.isfinite(high) or high <= low:
        return [low]
    raw_step = (high - low) / max(count, 1)
    exponent = math.floor(math.log10(raw_step))
    base = 10**exponent
    for multiplier in (1, 2, 2.5, 5, 10):
        step = multiplier * base
        if step >= raw_step:
            break
    start = math.ceil(low / step) * step
    ticks = []
    value = start
    while value <= high + step * 1e-9:
        ticks.append(round(value, 10))
        value += step
    return ticks


def _number(value: float) -> str:
    return f"{value:.6g}"


def _escaped(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _open_svg(width: int, height: int, title: str, description: str) -> list[str]:
    return [
        f'<svg class="chart-svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-labelledby="chart-title" aria-describedby="chart-desc" '
        f'xmlns="http://www.w3.org/2000/svg" style="font-family:{FONT}">',
        f"<title id=\"chart-title\">{_escaped(title)}</title>",
        f"<desc id=\"chart-desc\">{_escaped(description)}</desc>",
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
    ]


def _polyline(points: list[tuple[float, float]], color: str, width: float = 2.2) -> str:
    if len(points) < 2:
        return ""
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return (
        f'<polyline points="{path}" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'
    )


def _grid_and_axes(
    *,
    left: float,
    right: float,
    top: float,
    bottom: float,
    x_ticks: list[tuple[float, str]],
    y_ticks: list[tuple[float, str]],
    x_label: str,
    y_label: str,
) -> list[str]:
    parts = [
        f'<rect x="{left:.1f}" y="{top:.1f}" width="{right - left:.1f}" '
        f'height="{bottom - top:.1f}" fill="#fbfdff" stroke="{COLOR_GRID}"/>'
    ]
    for x, label in x_ticks:
        parts.append(
            f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" '
            f'y2="{bottom:.1f}" stroke="{COLOR_GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{bottom + 17:.1f}" text-anchor="middle" '
            f'font-size="11" fill="{COLOR_AXIS}">{_escaped(label)}</text>'
        )
    for y, label in y_ticks:
        parts.append(
            f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{right:.1f}" '
            f'y2="{y:.1f}" stroke="{COLOR_GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 8:.1f}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="{COLOR_AXIS}">{_escaped(label)}</text>'
        )
    parts.append(
        f'<text x="{(left + right) / 2:.1f}" y="{bottom + 36:.1f}" '
        f'text-anchor="middle" font-size="11.5" fill="{COLOR_TEXT}">'
        f"{_escaped(x_label)}</text>"
    )
    parts.append(
        f'<text x="14" y="{(top + bottom) / 2:.1f}" text-anchor="middle" '
        f'font-size="11.5" fill="{COLOR_TEXT}" '
        f'transform="rotate(-90 14 {(top + bottom) / 2:.1f})">'
        f"{_escaped(y_label)}</text>"
    )
    return parts


def _legend(items: list[tuple[str, str]], x: float, y: float) -> list[str]:
    parts = []
    for index, (label, color) in enumerate(items):
        offset = index * 110
        parts.append(
            f'<line x1="{x + offset:.1f}" y1="{y:.1f}" x2="{x + offset + 20:.1f}" '
            f'y2="{y:.1f}" stroke="{color}" stroke-width="3"/>'
        )
        parts.append(
            f'<text x="{x + offset + 26:.1f}" y="{y + 4:.1f}" font-size="11" '
            f'fill="{COLOR_TEXT}">{_escaped(label)}</text>'
        )
    return parts


def bode_svg(
    frequency_hz: list[float],
    gain_db: list[float],
    phase_deg: list[float],
    *,
    lower_cutoff_hz: float | None = None,
    upper_cutoff_hz: float | None = None,
    title: str = "Bode plot จาก ngspice",
    description: str = "ขนาดอัตราขยายและเฟสตามความถี่",
) -> str:
    width, height = 820, 450
    left, right = 66, width - 20
    mag_top, mag_bottom = 34, 258
    phase_top, phase_bottom = 308, 402

    valid = [
        (f, g, p)
        for f, g, p in zip(frequency_hz, gain_db, phase_deg)
        if f > 0 and math.isfinite(g) and math.isfinite(p)
    ]
    if len(valid) < 2:
        return '<p class="chart-empty">ไม่มีข้อมูล AC จาก ngspice</p>'

    freq = [row[0] for row in valid]
    gains = [max(row[1], -140.0) for row in valid]
    phases = [row[2] for row in valid]

    f_min, f_max = min(freq), max(freq)
    log_min, log_max = math.log10(f_min), math.log10(f_max)
    if log_max <= log_min:
        log_max = log_min + 1

    def x_for(f: float) -> float:
        ratio = (math.log10(max(f, 1e-12)) - log_min) / (log_max - log_min)
        return left + ratio * (right - left)

    gain_low = min(gains)
    gain_high = max(gains)
    span = max(gain_high - gain_low, 12.0)
    gain_low = math.floor((gain_low - span * 0.08) / 5) * 5
    gain_high = math.ceil((gain_high + span * 0.08) / 5) * 5
    if gain_high <= gain_low:
        gain_high = gain_low + 10

    def y_gain(value: float) -> float:
        ratio = (value - gain_low) / (gain_high - gain_low)
        return mag_bottom - ratio * (mag_bottom - mag_top)

    phase_low = math.floor(min(phases) / 30) * 30
    phase_high = math.ceil(max(phases) / 30) * 30
    if phase_high <= phase_low:
        phase_high = phase_low + 90

    def y_phase(value: float) -> float:
        ratio = (value - phase_low) / (phase_high - phase_low)
        return phase_bottom - ratio * (phase_bottom - phase_top)

    parts = _open_svg(width, height, title, description)

    decades = list(range(math.ceil(log_min), math.floor(log_max) + 1))
    x_ticks = [(x_for(10**decade), _freq_label(10**decade)) for decade in decades]
    if len(x_ticks) < 2:
        x_ticks = [(x_for(f), _freq_label(f)) for f in (f_min, f_max)]

    gain_ticks = [
        (y_gain(value), f"{value:g}")
        for value in _nice_ticks(gain_low, gain_high, 5)
    ]
    parts += _grid_and_axes(
        left=left, right=right, top=mag_top, bottom=mag_bottom,
        x_ticks=x_ticks, y_ticks=gain_ticks,
        x_label="ความถี่ (Hz)", y_label="อัตราขยาย (dB)",
    )
    parts += _legend([("Gain (dB)", COLOR_GAIN)], left + 4, mag_top + 15)
    parts.append(
        f'<text x="{left + 4:.1f}" y="{mag_top + 34:.1f}" font-size="11" '
        f'fill="{COLOR_AXIS}">Vout / Vin (แหล่งสัญญาณอุดมคติ 1 V)</text>'
    )

    max_gain = max(gains)
    threshold = max_gain - 3.0103
    if gain_low < threshold < gain_high:
        y = y_gain(threshold)
        parts.append(
            f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{right:.1f}" y2="{y:.1f}" '
            f'stroke="#94a3b8" stroke-width="1" stroke-dasharray="5 4"/>'
        )
        parts.append(
            f'<text x="{right - 4:.1f}" y="{y - 5:.1f}" text-anchor="end" '
            f'font-size="10" fill="{COLOR_AXIS}">-3 dB จากยอด</text>'
        )

    for cutoff, label in ((lower_cutoff_hz, "fL"), (upper_cutoff_hz, "fH")):
        if cutoff and f_min <= cutoff <= f_max:
            x = x_for(cutoff)
            parts.append(
                f'<line x1="{x:.1f}" y1="{mag_top:.1f}" x2="{x:.1f}" '
                f'y2="{mag_bottom:.1f}" stroke="{COLOR_PHASE}" '
                f'stroke-width="1" stroke-dasharray="3 4" opacity="0.55"/>'
            )
            parts.append(
                f'<text x="{x + 4:.1f}" y="{mag_top + 14:.1f}" font-size="10" '
                f'fill="{COLOR_PHASE}">{label} {_freq_label(cutoff)}Hz</text>'
            )

    parts.append(
        _polyline([(x_for(f), y_gain(g)) for f, g in zip(freq, gains)], COLOR_GAIN)
    )

    phase_ticks = [
        (y_phase(value), f"{value:g}°")
        for value in _nice_ticks(phase_low, phase_high, 4)
    ]
    parts += _grid_and_axes(
        left=left, right=right, top=phase_top, bottom=phase_bottom,
        x_ticks=x_ticks, y_ticks=phase_ticks,
        x_label="ความถี่ (Hz) — สเกลลอการิทึม", y_label="เฟส (องศา)",
    )
    parts += _legend([("Phase (°)", COLOR_PHASE)], left + 4, phase_top + 15)
    parts.append(
        _polyline(
            [(x_for(f), y_phase(p)) for f, p in zip(freq, phases)],
            COLOR_PHASE,
            2.0,
        )
    )

    parts.append("</svg>")
    return "".join(parts)


def transient_svg(
    time_s: list[float],
    vin_v: list[float],
    vout_v: list[float],
    *,
    title: str = "Transient waveform จาก ngspice",
    description: str = "แรงดันอินพุตและเอาต์พุตตามเวลา",
) -> str:
    width, height = 820, 360
    left, right = 66, width - 20
    top, bottom = 54, 292

    rows = [
        (t, a, b)
        for t, a, b in zip(time_s, vin_v, vout_v)
        if math.isfinite(t) and math.isfinite(a) and math.isfinite(b)
    ]
    if len(rows) < 2:
        return '<p class="chart-empty">ไม่มีข้อมูล Transient จาก ngspice</p>'

    t0 = rows[0][0]
    t_values = [(row[0] - t0) * 1e3 for row in rows]
    vin_mv = [row[1] * 1e3 for row in rows]
    vout_mv = [row[2] * 1e3 for row in rows]

    x_min, x_max = min(t_values), max(t_values)
    if x_max <= x_min:
        x_max = x_min + 1

    values = vin_mv + vout_mv
    y_min, y_max = min(values), max(values)
    span = max(y_max - y_min, 1e-6)
    y_min -= span * 0.12
    y_max += span * 0.12

    def x_for(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * (right - left)

    def y_for(value: float) -> float:
        return bottom - (value - y_min) / (y_max - y_min) * (bottom - top)

    parts = _open_svg(width, height, title, description)
    x_ticks = [
        (x_for(value), _number(value))
        for value in _nice_ticks(x_min, x_max, 6)
    ]
    y_ticks = [
        (y_for(value), _number(value))
        for value in _nice_ticks(y_min, y_max, 5)
    ]
    parts += _grid_and_axes(
        left=left, right=right, top=top, bottom=bottom,
        x_ticks=x_ticks, y_ticks=y_ticks,
        x_label="เวลา (ms) — หน้าต่างสภาวะคงตัว", y_label="แรงดัน (mV)",
    )

    if y_min < 0 < y_max:
        zero = y_for(0)
        parts.append(
            f'<line x1="{left:.1f}" y1="{zero:.1f}" x2="{right:.1f}" '
            f'y2="{zero:.1f}" stroke="#cbd5e1" stroke-width="1"/>'
        )

    parts += _legend(
        [("Vin", COLOR_VIN), ("Vout", COLOR_VOUT)], left + 4, 22
    )
    parts.append(
        _polyline([(x_for(x), y_for(y)) for x, y in zip(t_values, vin_mv)], COLOR_VIN)
    )
    parts.append(
        _polyline(
            [(x_for(x), y_for(y)) for x, y in zip(t_values, vout_mv)],
            COLOR_VOUT,
            2.4,
        )
    )

    parts.append("</svg>")
    return "".join(parts)
