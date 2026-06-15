
from __future__ import annotations

from pathlib import Path
from typing import List
from datetime import datetime
import json
from PIL import Image, TiffImagePlugin

from ..common.gauge import dpi_pair
from .contracts import CatalogRecord


TIFF_TAG_IMAGE_DESCRIPTION = 270
TIFF_TAG_DOCUMENT_NAME = 269
TIFF_TAG_SOFTWARE = 305
TIFF_TAG_DATETIME = 306
TIFF_TAG_ARTIST = 315
TIFF_TAG_KNIT_GRID_CATALOG_JSON = 65000


def _load_page(path: str | Path, mode: str = "RGB") -> Image.Image:
    return Image.open(path).convert(mode)


def _load_cover_page(path: str | Path) -> Image.Image:
    img = Image.open(path)
    if "A" in img.getbands():
        return img.convert("RGBA")
    return img.convert("RGB")


def _record_dpi(record: CatalogRecord) -> tuple[float, float] | None:
    dpi_x = float(record.source_dpi_x or 0.0)
    dpi_y = float(record.source_dpi_y or 0.0)
    if dpi_x > 0 and dpi_y > 0:
        return dpi_x, dpi_y
    try:
        src = Image.open(record.source_image_path)
        src_x, src_y = dpi_pair(src)
    except Exception:
        return None
    if src_x and src_y and src_x > 0 and src_y > 0:
        return src_x, src_y
    return None


def _apply_dpi(page: Image.Image, dpi: tuple[float, float] | None) -> Image.Image:
    if dpi is not None:
        page.info["dpi"] = dpi
    return page


def _compact_text(value: object, max_len: int = 80) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[: max_len - 3].rstrip() + "..."
    return text


def _image_description(record: CatalogRecord) -> str:
    sample = record.sample
    fields = [
        ("Sample ID", sample.sample_id),
        ("Source", sample.source_image_name),
        ("Needles/10cm", sample.needles_per_10cm),
        ("Rows/10cm", sample.rows_per_10cm),
        ("Yarn", sample.yarn_ref),
        ("Brand", sample.brand),
        ("Machine", sample.machine_ref),
        ("Structure", sample.structure_ref),
        ("Colour", sample.colour_ref),
    ]
    parts = [
        "Knit Grid Catalog v14",
        "full JSON metadata embedded in TIFF private tag 65000",
    ]
    parts.extend(f"{key}: {_compact_text(value)}" for key, value in fields if _compact_text(value))
    return "; ".join(parts)


def _catalog_json(record: CatalogRecord) -> str:
    return json.dumps(record.payload(), separators=(",", ":"), ensure_ascii=True)


def _tiff_info(record: CatalogRecord) -> TiffImagePlugin.ImageFileDirectory_v2:
    info = TiffImagePlugin.ImageFileDirectory_v2()
    info[TIFF_TAG_IMAGE_DESCRIPTION] = _image_description(record)
    info[TIFF_TAG_KNIT_GRID_CATALOG_JSON] = _catalog_json(record)
    info[TIFF_TAG_DOCUMENT_NAME] = record.sample.sample_id
    info[TIFF_TAG_SOFTWARE] = "knit_grid_catalog_delivery_v14"
    info[TIFF_TAG_DATETIME] = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
    info[TIFF_TAG_ARTIST] = record.sample.operator
    return info


def write_layered_tiff(record: CatalogRecord, output_path: str | Path, cover_page_path: str | Path) -> Path:
    """
    Write a two-page TIFF:
      page 0: engineered per-sample cover
      page 1: original source scan

    A short human-readable summary is embedded in ImageDescription. The full
    JSON payload is embedded in first-page private TIFF tag 65000.
    Diagnostic analysis layers are intentionally omitted to keep file size small.
    """
    output_path = Path(output_path)
    cover_page_path = Path(cover_page_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not cover_page_path.exists():
        raise FileNotFoundError(f"Missing engineered cover page: {cover_page_path}")

    dpi = _record_dpi(record)
    cover_page = _apply_dpi(_load_cover_page(cover_page_path), dpi)
    pages: List[Image.Image] = [cover_page]

    src_path = Path(record.source_image_path)
    if src_path.exists():
        pages.append(_apply_dpi(_load_page(src_path, cover_page.mode), dpi))

    save_kwargs = {"dpi": dpi} if dpi is not None else {}
    pages[0].save(
        output_path,
        save_all=True,
        append_images=pages[1:],
        compression="tiff_deflate",
        tiffinfo=_tiff_info(record),
        **save_kwargs,
    )
    return output_path
