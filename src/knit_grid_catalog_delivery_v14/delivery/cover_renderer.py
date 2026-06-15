
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageFilter, ImageOps
import math
import json

from ..common.gauge import dpi_pair, repeats_per_10cm
from .contracts import CatalogRecord, CatalogBatch


CARD_W, CARD_H = 658, 479
PAGE_BG = (244, 244, 241)
IMAGE_H_FRAC = 304 / 479
RIGHT_STRIP_FRAC = 0.32


def _mix_rgb(a: Tuple[int, int, int], b: Tuple[int, int, int], amount: float) -> Tuple[int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return tuple(int(round(a[i] * (1.0 - amount) + b[i] * amount)) for i in range(3))


def _flatten_visible_image(img: Image.Image, background: Tuple[int, int, int] = PAGE_BG) -> Image.Image:
    if "A" not in img.getbands():
        return img.convert("RGB")
    rgba = img.convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (*background, 255))
    return Image.alpha_composite(bg, rgba).convert("RGB")


def _visible_average_rgb(img: Image.Image, alpha_threshold: int = 8) -> Tuple[int, int, int]:
    """
    Average visible input-image pixels only.

    RGBA scans often contain transparent padding; including that padding makes
    the reactive palette drift toward black/white instead of the yarn colour.
    """
    sample = img.convert("RGBA")
    sample.thumbnail((160, 160), Image.Resampling.BOX)

    r_sum = g_sum = b_sum = weight_sum = 0.0
    for r, g, b, a in sample.getdata():
        if a <= alpha_threshold:
            continue
        weight = a / 255.0
        r_sum += r * weight
        g_sum += g * weight
        b_sum += b * weight
        weight_sum += weight

    if weight_sum <= 0:
        rgb = _flatten_visible_image(img)
        return rgb.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))

    return (
        int(round(r_sum / weight_sum)),
        int(round(g_sum / weight_sum)),
        int(round(b_sum / weight_sum)),
    )


def image_reactive_palette(img: Image.Image) -> dict:
    avg = _visible_average_rgb(img)
    banner = (
        max(18, int(avg[0] * 0.45)),
        max(18, int(avg[1] * 0.38)),
        max(18, int(avg[2] * 0.35)),
    )
    return {
        "average": avg,
        "page_bg": _mix_rgb(PAGE_BG, avg, 0.035),
        "strip_tint": _mix_rgb((255, 255, 255), avg, 0.075),
        "banner": banner,
        "grid_line": (*_mix_rgb(banner, (34, 34, 34), 0.62), 175),
        "separator_light": (*_mix_rgb(banner, (255, 255, 255), 0.82), 220),
        "separator_dark": (*_mix_rgb(banner, (0, 0, 0), 0.45), 90),
        "rule": (*_mix_rgb(banner, (255, 255, 255), 0.78), 155),
        "rule_soft": (*_mix_rgb(banner, (255, 255, 255), 0.72), 120),
    }


def load_font(size: int = 18, bold: bool = False) -> ImageFont.ImageFont:
    paths = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def draw_text_fit(draw: ImageDraw.ImageDraw, text: str, box, fill=(255, 255, 255), max_size=30, min_size=9, bold=False) -> int:
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    text = "" if text is None else str(text)
    for size in range(max_size, min_size - 1, -1):
        font = load_font(size, bold)
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        if tw <= (x1 - x0) and th <= (y1 - y0):
            draw.text((x0, y0 + ((y1 - y0) - th) // 2 - bb[1]), text, fill=fill, font=font)
            return size
    font = load_font(min_size, bold)
    text = _ellipsize(draw, text, font, max(1, x1 - x0))
    bb = draw.textbbox((0, 0), text, font=font)
    th = bb[3] - bb[1]
    draw.text((x0, y0 + max(0, ((y1 - y0) - th) // 2) - bb[1]), text, fill=fill, font=font)
    return min_size


def _ellipsize(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    suffix = "..."
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        candidate = text[:mid].rstrip() + suffix
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + suffix if lo > 0 else suffix


def _rounded_alpha_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    scale = 4
    w, h = size
    mask = Image.new("L", (w * scale, h * scale), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, w * scale - 1, h * scale - 1), radius=radius * scale, fill=255)
    return mask.resize(size, Image.Resampling.LANCZOS)


def _apply_rounded_card_mask(card: Image.Image, radius: int) -> Image.Image:
    rounded = card.convert("RGBA")
    mask = _rounded_alpha_mask(rounded.size, radius)
    alpha = ImageChops.multiply(rounded.getchannel("A"), mask)
    rounded.putalpha(alpha)
    return rounded


def coverfit_transform(src_w: int, src_h: int, out_w: int, out_h: int):
    scale = max(out_w / src_w, out_h / src_h)
    resized_w = src_w * scale
    resized_h = src_h * scale
    crop_left = (resized_w - out_w) / 2.0
    crop_top = (resized_h - out_h) / 2.0
    return scale, crop_left, crop_top


def draw_detected_grid_overlay(
    draw: ImageDraw.ImageDraw,
    grid,
    source_size: Tuple[int, int],
    strip_x0: int,
    strip_w: int,
    main_h: int,
    full_top_w: int,
    line=(40, 40, 40, 165),
    line_w: int = 2,
    transform: Tuple[float, float, float] | None = None,
):
    src_w, src_h = source_size
    if transform is None:
        scale, crop_left, crop_top = coverfit_transform(src_w, src_h, full_top_w, main_h)
    else:
        scale, crop_left, crop_top = transform

    a = float(grid.axis_a_px) * scale
    b = float(grid.axis_b_px) * scale
    x0 = float(grid.x0_px) * scale - crop_left
    y0 = float(grid.y0_px) * scale - crop_top

    x_start = strip_x0
    x_end = strip_x0 + strip_w

    if a > 0:
        k0 = math.floor((x_start - x0) / a) - 1
        k1 = math.ceil((x_end - x0) / a) + 1
        for k in range(k0, k1 + 1):
            x_full = x0 + k * a
            if x_start <= x_full <= x_end:
                x_local = x_full - strip_x0
                draw.line((x_local, 0, x_local, main_h), fill=line, width=line_w)

    if b > 0:
        k0 = math.floor((0 - y0) / b) - 1
        k1 = math.ceil((main_h - y0) / b) + 1
        for k in range(k0, k1 + 1):
            y = y0 + k * b
            if 0 <= y <= main_h:
                draw.line((0, y, strip_w, y), fill=line, width=line_w)


def average_banner_color(img: Image.Image) -> Tuple[int, int, int]:
    return image_reactive_palette(img)["banner"]


def aligned_strip(
    full_top: Image.Image,
    strip_x0: int,
    strip_w: int,
    main_h: int,
    tint: Tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    strip = full_top.crop((strip_x0, 0, strip_x0 + strip_w, main_h)).convert("RGB")
    strip = strip.filter(ImageFilter.GaussianBlur(radius=0.35))
    gray = ImageOps.grayscale(strip).convert("RGB")
    strip = Image.blend(strip, gray, 0.35)
    # lighten to let grid be visible
    white = Image.new("RGB", strip.size, tint)
    strip = Image.blend(strip, white, 0.62)
    return strip.convert("RGBA")


def grid_reference_transform(
    grid,
    source_size: Tuple[int, int],
    out_w: int,
    out_h: int,
    strip_w: int,
) -> Tuple[float, float, float]:
    """
    Use the same cover-fill image projection for texture and grid overlay.

    Earlier cover cards scaled the crop from the grid period so the right strip
    always showed a small fixed number of cells. That made the cover disagree
    with the inspector canvas. Keeping the transform image-based means the
    grid is rendered in original image pixels, then projected into the crop.
    """
    src_w, src_h = source_size
    return coverfit_transform(src_w, src_h, out_w, out_h)


def render_grid_referenced_top(
    img: Image.Image,
    grid,
    out_w: int,
    out_h: int,
    strip_w: int,
) -> Tuple[Image.Image, Tuple[float, float, float]]:
    transform = grid_reference_transform(grid, img.size, out_w, out_h, strip_w)
    scale, crop_left, crop_top = transform
    resized_w = max(out_w, int(round(img.width * scale)))
    resized_h = max(out_h, int(round(img.height * scale)))
    resized = img.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
    crop_x = min(max(0, int(round(crop_left))), max(0, resized_w - out_w))
    crop_y = min(max(0, int(round(crop_top))), max(0, resized_h - out_h))
    crop = resized.crop((
        crop_x,
        crop_y,
        crop_x + out_w,
        crop_y + out_h,
    ))
    return crop.convert("RGB"), (scale, float(crop_x), float(crop_y))


def _display_sample_name(sample_id: str) -> str:
    text = str(sample_id or "").strip()
    if not text:
        return "SAMPLE"
    if text.upper().endswith("_FUZZY"):
        text = text[:-6] + " FUZZY"
    return text.upper()


def _float_or_none(value) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _format_gauge(value, unit: str) -> str | None:
    count = _float_or_none(value)
    if count is None or count <= 0:
        return None
    if abs(count - round(count)) < 0.05:
        text = str(int(round(count)))
    else:
        text = f"{count:.1f}"
    return f"{text} {unit}/10cm"


def _measurement_line(record: CatalogRecord, source: Image.Image) -> str:
    sample = record.sample
    left = _format_gauge(getattr(sample, "needles_per_10cm", ""), "st")
    right = _format_gauge(getattr(sample, "rows_per_10cm", ""), "rows")

    if left is None or right is None:
        dpi_x, dpi_y = dpi_pair(source)
        stitches = repeats_per_10cm(float(record.wale_target_grid.axis_a_px), dpi_x)
        rows = repeats_per_10cm(float(record.wale_target_grid.axis_b_px), dpi_y)
        if left is None:
            left = f"{stitches:.1f} st/10cm" if stitches is not None else "-- st/10cm"
        if right is None:
            right = f"{rows:.1f} rows/10cm" if rows is not None else "-- rows/10cm"

    line = f"{left}   |   {right}"
    weight_gsm = str(getattr(record.sample, "weight_gsm", "") or "").strip()
    if weight_gsm:
        line = f"{line}   |   {weight_gsm} g/sqmt"
    return line


def _yarn_line(sample) -> str:
    yarn = str(getattr(sample, "yarn_ref", "") or "").strip()
    fibre = str(getattr(sample, "fibre_composition", "") or "").strip()
    structure = str(getattr(sample, "structure_ref", "") or "").strip()
    if yarn and fibre:
        return f"{yarn} | {fibre}"
    if yarn:
        return yarn
    if fibre:
        return fibre
    if structure and structure not in ("", "knit grid retrieval", "knitted swatch"):
        return structure
    return "yarn details"


def _bed_setup_label(sample) -> str:
    value = str(getattr(sample, "bed_setup", "") or "").strip()
    return value if value else "bed n/a"


def _bed_setup_is_double(sample) -> bool:
    value = str(getattr(sample, "bed_setup", "") or "").strip().lower()
    return value not in ("", "single bed")


def _weight_label(sample) -> str:
    value = float(getattr(sample, "weighting_ref", 0.0) or 0.0)
    if abs(value - round(value)) < 1e-6:
        text = str(int(round(value)))
    else:
        text = f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{text} g/needle"


def _short_metadata_value(value, fallback: str = "n/a") -> str:
    text = str(value or "").strip()
    if not text or text in ("-", "--"):
        return fallback
    return text


def _tension_thread_label(sample) -> str:
    carriage = _short_metadata_value(getattr(sample, "tension_ref", ""))
    thread_tension = _short_metadata_value(getattr(sample, "yarn_tension", ""))
    thread_count = _short_metadata_value(getattr(sample, "thread_count", ""), "1")
    return f"C{carriage}, T{thread_tension}, tc{thread_count}"


def _icon_geometry(box):
    x0, y0, x1, y1 = [float(v) for v in box]
    w, h = x1 - x0, y1 - y0

    def p(x: float, y: float) -> Tuple[float, float]:
        return x0 + w * (x / 24.0), y0 + h * (y / 24.0)

    def r(xa: float, ya: float, xb: float, yb: float):
        ax, ay = p(xa, ya)
        bx, by = p(xb, yb)
        return (ax, ay, bx, by)

    return p, r


def _round_line(draw: ImageDraw.ImageDraw, points, fill, width: int) -> None:
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) < 2:
        return
    draw.line(pts, fill=fill, width=width, joint="curve")
    radius = max(1.0, width / 2.0)
    for x, y in (pts[0], pts[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _cubic_points(p0, p1, p2, p3, steps: int = 18):
    points = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1.0 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def draw_thread_icon(draw: ImageDraw.ImageDraw, box, fill, width: int) -> None:
    p, r = _icon_geometry(box)
    fine = max(1, width - 1)
    outer = [
        *_cubic_points(p(6.5, 5.0), p(7.4, 6.4), p(16.6, 6.4), p(17.5, 5.0), 10),
        p(20.0, 17.9),
        *_cubic_points(p(20.0, 17.9), p(20.5, 20.2), p(3.5, 20.2), p(4.0, 17.9), 16),
        p(6.5, 5.0),
    ]
    draw.line(outer, fill=fill, width=width, joint="curve")
    draw.ellipse(r(7.0, 2.8, 17.0, 5.8), outline=fill, width=width)
    draw.ellipse(r(10.1, 3.7, 13.9, 4.8), outline=fill, width=fine)
    _round_line(draw, [p(7.6, 4.4), p(7.6, 5.3)], fill, width)
    _round_line(draw, [p(16.4, 4.4), p(16.4, 5.3)], fill, width)
    _round_line(draw, [p(6.0, 20.0), p(6.0, 21.3)], fill, width)
    _round_line(draw, [p(18.0, 20.0), p(18.0, 21.3)], fill, width)
    _round_line(draw, _cubic_points(p(6.0, 21.3), p(8.5, 22.4), p(15.5, 22.4), p(18.0, 21.3), 14), fill, width)

    wraps = [
        (5.9, 8.3, 17.1, 10.4),
        (18.0, 7.8, 5.2, 11.4),
        (4.6, 12.0, 19.2, 14.2),
        (18.7, 11.7, 6.6, 15.0),
        (4.3, 15.5, 19.0, 17.5),
        (17.8, 16.0, 8.2, 17.9),
    ]
    for xa, ya, xb, yb in wraps:
        _round_line(draw, [p(xa, ya), p(xb, yb)], fill, fine)

    tail = _cubic_points(p(18.1, 20.3), p(20.5, 19.8), p(21.2, 20.0), p(21.7, 21.0), 8)
    tail += _cubic_points(p(21.7, 21.0), p(22.0, 22.0), p(22.7, 22.1), p(23.4, 22.1), 8)[1:]
    _round_line(draw, tail, fill, fine)


def draw_balance_icon(draw: ImageDraw.ImageDraw, box, fill, width: int) -> None:
    p, r = _icon_geometry(box)
    draw.ellipse(r(10.8, 2.8, 13.2, 5.2), outline=fill, width=width)
    _round_line(draw, [p(12.0, 5.2), p(12.0, 7.0)], fill, width)
    draw.ellipse(r(10.7, 7.0, 13.3, 9.6), outline=fill, width=width)
    _round_line(draw, [p(3.6, 8.3), p(20.4, 8.3)], fill, width)
    _round_line(draw, [p(12.0, 9.6), p(12.0, 19.0)], fill, width)

    for cx, outer_x in ((6.0, 3.6), (18.0, 20.4)):
        pan = [p(outer_x, 8.3), p(cx - 3.7, 15.5), p(cx + 3.7, 15.5), p(outer_x, 8.3)]
        draw.line(pan, fill=fill, width=width, joint="curve")
        bowl = _cubic_points(p(cx - 3.7, 15.5), p(cx - 3.2, 18.8), p(cx + 3.2, 18.8), p(cx + 3.7, 15.5), 18)
        _round_line(draw, bowl, fill, width)

    draw.rounded_rectangle(r(9.3, 19.0, 14.7, 20.4), radius=max(1, width), outline=fill, width=width)
    draw.rounded_rectangle(r(7.8, 20.4, 16.2, 21.8), radius=max(1, width), outline=fill, width=width)


def draw_drop_icon(draw: ImageDraw.ImageDraw, box, fill, width: int, washed: bool = False) -> None:
    p, _ = _icon_geometry(box)
    outline = [
        *_cubic_points(p(12.0, 3.0), p(9.5, 7.1), p(4.8, 12.3), p(4.7, 15.6), 14),
        *_cubic_points(p(4.7, 15.6), p(4.5, 19.1), p(7.9, 21.0), p(11.9, 21.1), 14)[1:],
        *_cubic_points(p(11.9, 21.1), p(16.0, 21.2), p(19.4, 19.0), p(19.3, 15.7), 14)[1:],
        *_cubic_points(p(19.3, 15.7), p(19.2, 12.2), p(14.6, 7.1), p(12.0, 3.0), 14)[1:],
    ]
    draw.line(outline, fill=fill, width=width, joint="curve")
    highlight = _cubic_points(p(17.0, 16.2), p(16.7, 17.8), p(15.7, 19.0), p(14.4, 19.6), 10)
    _round_line(draw, highlight, fill, max(1, width - 1))
    if not washed:
        _round_line(draw, [p(3.5, 5.4), p(20.5, 20.5)], fill, width)
        _round_line(draw, [p(20.5, 5.4), p(3.5, 20.5)], fill, width)


def render_card(
    record: CatalogRecord,
    use_grid: str = "wale_target",
    card_size: Tuple[int, int] = (CARD_W, CARD_H),
) -> Image.Image:
    card_w, card_h = card_size
    sx = card_w / CARD_W
    sy = card_h / CARD_H
    scale = min(sx, sy)

    def xs(value: float) -> int:
        return int(round(value * sx))

    def ys(value: float) -> int:
        return int(round(value * sy))

    def fs(value: float) -> int:
        return max(1, int(round(value * scale)))

    source = Image.open(record.source_image_path)
    palette = image_reactive_palette(source)
    bg = _flatten_visible_image(source)
    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card, "RGBA")

    main_h = int(round(card_h * IMAGE_H_FRAC))
    strip_w = int(round(card_w * RIGHT_STRIP_FRAC))
    left_w = card_w - strip_w
    grid = record.wale_target_grid if use_grid == "wale_target" else record.micro_grid

    full_top, top_transform = render_grid_referenced_top(bg, grid, card_w, main_h, strip_w)
    card.paste(full_top.crop((0, 0, left_w, main_h)), (0, 0))

    strip = aligned_strip(full_top, left_w, strip_w, main_h, tint=palette["strip_tint"])
    sd = ImageDraw.Draw(strip, "RGBA")
    draw_detected_grid_overlay(
        sd,
        grid,
        bg.size,
        left_w,
        strip_w,
        main_h,
        card_w,
        line=palette["grid_line"],
        line_w=max(1, fs(2)),
        transform=top_transform,
    )
    card.alpha_composite(strip, (left_w, 0))

    draw.line((left_w - xs(2), 0, left_w - xs(2), main_h), fill=palette["separator_light"], width=max(1, fs(3)))
    draw.line((left_w + xs(1), 0, left_w + xs(1), main_h), fill=palette["separator_dark"], width=max(1, fs(1)))

    banner_y = main_h
    banner_color = palette["banner"]
    draw.rectangle((0, banner_y, card_w, card_h), fill=(*banner_color, 242))
    draw.rectangle((0, banner_y, card_w, banner_y + ys(18)), fill=(*banner_color, 240))

    white = (255, 255, 255, 245)
    sample = record.sample

    draw_text_fit(
        draw,
        f"{_display_sample_name(sample.sample_id)}  |  {sample.machine_ref}",
        (xs(36), banner_y + ys(14), card_w - xs(36), banner_y + ys(43)),
        white,
        fs(23),
        max(8, fs(11)),
        True,
    )
    draw_text_fit(draw, _yarn_line(sample), (xs(36), banner_y + ys(47), card_w - xs(36), banner_y + ys(77)), white, fs(22), max(9, fs(12)), True)
    draw_text_fit(draw, _measurement_line(record, source), (xs(36), banner_y + ys(80), card_w - xs(36), banner_y + ys(108)), white, fs(20), max(8, fs(11)), False)

    divider_y = banner_y + ys(119)
    draw.line((xs(25), divider_y, card_w - xs(25), divider_y), fill=palette["rule"], width=max(1, fs(1)))

    lower_y0 = divider_y + ys(16)
    lower_y1 = card_h - ys(15)
    row_h = max(1, lower_y1 - lower_y0)
    icon_w = min(fs(36), max(fs(20), row_h - ys(2)))
    icon_gap = fs(17)
    column_pad = fs(18)
    text_fill = white
    icon_fill = (255, 255, 255, 235)
    lower_items = [
        (draw_thread_icon, _tension_thread_label(sample), None),
        (draw_balance_icon, _weight_label(sample), None),
        (draw_drop_icon, _bed_setup_label(sample), _bed_setup_is_double(sample)),
    ]

    content_left = xs(25)
    content_right = card_w - xs(25)
    col_w = (content_right - content_left) / 3.0
    sep_top = lower_y0 + int(round(row_h * 0.11))
    sep_bottom = lower_y1 - int(round(row_h * 0.11))
    for idx in (1, 2):
        rule_x = int(round(content_left + col_w * idx))
        draw.line((rule_x, sep_top, rule_x, sep_bottom), fill=palette["rule_soft"], width=max(1, fs(1)))

    for idx, (icon_fn, text, icon_state) in enumerate(lower_items):
        col_left = content_left + col_w * idx
        col_right = content_left + col_w * (idx + 1)
        available_w = max(1, int(round(col_right - col_left - column_pad * 2)))
        text_w_limit = max(1, available_w - icon_w - icon_gap)
        label_font = load_font(fs(20), False)
        for size in range(fs(20), max(8, fs(11)) - 1, -1):
            candidate = load_font(size, False)
            bb = draw.textbbox((0, 0), text, font=candidate)
            if bb[2] - bb[0] <= text_w_limit:
                label_font = candidate
                break
        text = _ellipsize(draw, text, label_font, text_w_limit)
        bb = draw.textbbox((0, 0), text, font=label_font)
        text_w = bb[2] - bb[0]
        text_h = bb[3] - bb[1]
        group_w = icon_w + icon_gap + text_w
        group_x = col_left + max(column_pad, ((col_right - col_left) - group_w) / 2.0)
        icon_y = lower_y0 + (row_h - icon_w) / 2.0
        icon_box = (
            int(round(group_x)),
            int(round(icon_y)),
            int(round(group_x + icon_w)),
            int(round(icon_y + icon_w)),
        )
        if icon_state is None:
            icon_fn(draw, icon_box, icon_fill, max(1, fs(2)))
        else:
            icon_fn(draw, icon_box, icon_fill, max(1, fs(2)), icon_state)
        text_x = int(round(group_x + icon_w + icon_gap))
        text_y = int(round(lower_y0 + (row_h - text_h) / 2.0 - bb[1]))
        draw.text((text_x, text_y), text, fill=text_fill, font=label_font)

    return _apply_rounded_card_mask(card, fs(18))


def _render_report_sample_cover(record: CatalogRecord, size=(1600, 1200)) -> Image.Image:
    page = Image.new("RGB", size, PAGE_BG)
    draw = ImageDraw.Draw(page)

    title_font = load_font(42, True)
    body_font = load_font(22, False)
    small_font = load_font(18, False)

    draw.text((54, 34), "Knit grid analysis catalog", fill=(26, 26, 24), font=title_font)
    draw.text((56, 88), f"Sample: {record.sample.sample_id}   |   Schema: knit_grid_catalog/v14", fill=(70, 70, 66), font=body_font)

    raw = Image.open(record.source_image_path).convert("RGB")
    hero = ImageOps.fit(raw, (850, 760), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    page.paste(hero, (54, 150))

    # right measurement panel
    panel = Image.new("RGB", (560, 760), (255, 255, 255))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle((0, 0, 559, 759), radius=24, fill=(255, 255, 255), outline=(220, 220, 215), width=2)

    y = 36
    pd.text((34, y), "Regular grid retrieval", fill=(30, 30, 30), font=load_font(30, True)); y += 56
    rows = [
        ("micro axis a", f"{record.micro_grid.axis_a_px:.2f} px"),
        ("micro axis b", f"{record.micro_grid.axis_b_px:.2f} px"),
        ("wale target axis a", f"{record.wale_target_grid.axis_a_px:.2f} px"),
        ("wale target axis b", f"{record.wale_target_grid.axis_b_px:.2f} px"),
        ("wale axis", record.wale_axis),
        ("wale multiplier", f"{record.wale_multiplier:.2f}×"),
        ("confidence", f"{record.quality.period_confidence:.3f}"),
        ("valid region", f"{record.quality.valid_region_fraction:.2%}"),
        ("local deviation RMS", f"{record.quality.local_deviation_rms_px:.2f} px"),
    ]
    for label, value in rows:
        pd.text((34, y), label, fill=(82, 82, 78), font=small_font)
        pd.text((300, y), value, fill=(25, 25, 25), font=load_font(22, True))
        y += 48

    if record.quality.warnings:
        pd.text((34, y + 10), "warnings", fill=(120, 75, 20), font=load_font(19, True))
        pd.text((34, y + 40), record.quality.warnings[:90], fill=(120, 75, 20), font=small_font)
    else:
        pd.text((34, y + 10), "warnings: none", fill=(65, 110, 60), font=load_font(19, True))

    page.paste(panel, (960, 150))

    # bottom strip of three diagnostic thumbnails
    thumb_y = 950
    thumb_w, thumb_h = 470, 155
    diag_roles = ["consensus_strict", "micro_regular_grid", "wale_target_grid"]
    for i, role in enumerate(diag_roles):
        asset = next((x for x in record.layers if x.role == role), None)
        x = 54 + i * (thumb_w + 34)
        if asset and Path(asset.path).exists():
            im = Image.open(asset.path).convert("RGB")
            im = ImageOps.fit(im, (thumb_w, thumb_h), method=Image.Resampling.LANCZOS)
            page.paste(im, (x, thumb_y))
        draw.text((x, thumb_y + thumb_h + 8), role.replace("_", " "), fill=(65, 65, 62), font=small_font)

    return page


def render_sample_cover(record: CatalogRecord, size=(2048, 2048)) -> Image.Image:
    """
    Render the per-sample TIFF cover with the same card language as the
    composed catalog cover.

    Earlier builds used a separate report-style page here, which made TIFF
    page 0 visually diverge from the engineered target cover. Keeping this
    as a scaled single card makes the batch cover and per-sample cover one
    design system.
    """
    return render_card(record, use_grid="wale_target", card_size=size)


def render_batch_cover(batch: CatalogBatch) -> Image.Image:
    cols = 2
    rows = math.ceil(len(batch.records) / cols)
    margin_x, margin_y = 42, 67
    gap_x, gap_y = 31, 23
    page_w = max(1448, margin_x * 2 + cols * CARD_W + (cols - 1) * gap_x)
    page_h = margin_y + rows * CARD_H + (rows - 1) * gap_y + 38

    page = Image.new("RGBA", (page_w, page_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(page)
    draw.text((34, 18), batch.title, fill=(0, 0, 0), font=load_font(32, True))
    draw.text((54, 68), "Composed cover — each card uses the external grid result; no analysis is performed in the cover renderer.", fill=(80, 80, 76), font=load_font(17, False))

    for idx, record in enumerate(batch.records):
        r = idx // cols
        c = idx % cols
        x = margin_x + c * (CARD_W + gap_x)
        y = margin_y + r * (CARD_H + gap_y)
        card = render_card(record, use_grid="wale_target")
        # shadow
        shadow = Image.new("RGBA", (CARD_W + 14, CARD_H + 14), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((6, 6, CARD_W + 6, CARD_H + 6), radius=16, fill=(0, 0, 0, 50))
        shadow = shadow.filter(ImageFilter.GaussianBlur(3))
        page.paste(shadow, (x - 5, y - 5), shadow)
        page.alpha_composite(card, (x, y))

    return page
