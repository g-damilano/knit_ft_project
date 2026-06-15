from __future__ import annotations

"""
Pixel-period <-> stitch-gauge conversion helpers.

Shared by the interface (lattice detection) and the delivery cover renderer so
both report the same "needles / rows per 10 cm" numbers from the same v13
pixel-period measurements. Pure arithmetic only - no image-analysis imports -
so it is safe on both sides of the analyzer/delivery boundary.
"""

from typing import Any, Tuple


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def dpi_pair(image) -> Tuple[float | None, float | None]:
    """Read an (x, y) DPI pair from a Pillow image's info dict, if present."""
    dpi = getattr(image, "info", {}).get("dpi")
    if isinstance(dpi, tuple) and len(dpi) >= 2:
        x = _positive_float(dpi[0])
        y = _positive_float(dpi[1])
        if x and y:
            return x, y
    if isinstance(dpi, (int, float)):
        value = _positive_float(dpi)
        if value:
            return value, value

    tag_v2 = getattr(image, "tag_v2", None)
    if tag_v2 is not None:
        x_res = _positive_float(tag_v2.get(282))
        y_res = _positive_float(tag_v2.get(283))
        unit = int(tag_v2.get(296, 2) or 2)
        if x_res and y_res:
            if unit == 3:  # pixels per centimetre
                return x_res * 2.54, y_res * 2.54
            return x_res, y_res

    exif = getattr(image, "getexif", lambda: {})()
    if exif:
        x_res = _positive_float(exif.get(282))
        y_res = _positive_float(exif.get(283))
        unit = int(exif.get(296, 2) or 2)
        if x_res and y_res:
            if unit == 3:
                return x_res * 2.54, y_res * 2.54
            return x_res, y_res
    return None, None


def repeats_per_10cm(spacing_px: float, dpi: float | None) -> float | None:
    """Convert a pixel period into stitch repeats per 10 cm using image DPI."""
    if not dpi or spacing_px <= 0:
        return None
    return (dpi / 2.54 * 10.0) / spacing_px


def period_cm(repeats_per_10cm_value) -> str:
    """Format the cm spacing implied by a `<count> per 10 cm` gauge value."""
    try:
        count = float(repeats_per_10cm_value)
    except (TypeError, ValueError):
        return "—"
    if count <= 0:
        return "—"
    return f"{10.0 / count:.2f} cm"


def confidence_pct(value) -> str:
    """Format a 0-1 confidence score as a rounded percentage string."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "—"
    if score != score:  # NaN guard
        return "—"
    return f"{round(score * 100)}%"
