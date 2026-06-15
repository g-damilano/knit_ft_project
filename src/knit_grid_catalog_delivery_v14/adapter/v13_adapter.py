
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import csv

from ..common.gauge import dpi_pair
from ..common.metadata_io import (
    find_metadata_for_sample,
    read_metadata_yaml,
    sample_metadata_kwargs,
    sanitize_sample_id,
)
from ..delivery.contracts import (
    CatalogRecord,
    GridParams,
    LayerAsset,
    QualityMetrics,
    SampleMetadata,
)


def _read_csv(path: Path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _float(row, key, default=0.0) -> float:
    value = row.get(key, "")
    if value in ("", None):
        return float(default)
    return float(value)


def _layer(root: Path, sample: str, filename: str, role: str, label: str, description: str = "") -> LayerAsset:
    return LayerAsset(
        role=role,
        path=str(root / sample / filename),
        label=label,
        description=description,
    )


def _source_image_for_cover(root: Path, sample: str, fallback: Path) -> Path:
    """
    Prefer the original swatch image when it is beside the v13 output folder.

    The v13 `01_raw.png` diagnostic is often stripped of DPI/alpha metadata.
    Cover rendering needs the original image so physical counts and visible
    average colour remain faithful.
    """
    search_dirs = [root.parent]
    if len(root.parents) > 1:
        search_dirs.append(root.parent.parent)
        search_dirs.append(root.parent.parent / "samples")
    for directory in search_dirs:
        for ext in (".png", ".tif", ".tiff", ".jpg", ".jpeg", ".webp"):
            candidate = directory / f"{sample}{ext}"
            if candidate.exists():
                return candidate
    return fallback


def records_from_v13_output(v13_output_dir: str | Path) -> List[CatalogRecord]:
    """
    Adapter boundary: this function reads already-produced v13 files only.

    It intentionally does not import, call, or re-run any analysis code.
    """
    root = Path(v13_output_dir)
    summary_path = root / "v13_grid_summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing v13 summary: {summary_path}")

    records: List[CatalogRecord] = []
    for row in _read_csv(summary_path):
        sample_id = row["image"]
        sample_dir = root / sample_id
        source_layer = sample_dir / "01_raw.png"
        source = _source_image_for_cover(root, sample_id, source_layer)
        metadata_path = find_metadata_for_sample(root, sample_id, source)
        metadata = read_metadata_yaml(metadata_path)

        micro = GridParams(
            axis_a_px=_float(row, "selected_micro_axis_a_px"),
            axis_b_px=_float(row, "selected_micro_axis_b_px"),
            x0_px=_float(row, "x0_micro_px"),
            y0_px=_float(row, "y0_micro_px"),
            role="micro_regular_grid",
        )
        target = GridParams(
            axis_a_px=_float(row, "selected_target_axis_a_px"),
            axis_b_px=_float(row, "selected_target_axis_b_px"),
            x0_px=_float(row, "x0_target_px"),
            y0_px=_float(row, "y0_target_px"),
            role="wale_target_regular_grid",
        )
        quality = QualityMetrics(
            period_confidence=_float(row, "period_confidence"),
            valid_region_fraction=_float(row, "valid_region_fraction"),
            local_deviation_rms_px=_float(row, "local_deviation_rms_px"),
            orientation_fft_deg=_float(row, "orientation_fft_deg"),
            orientation_hough_deg=_float(row, "orientation_hough_deg"),
            warnings=row.get("warnings", ""),
        )
        sample = SampleMetadata(
            **sample_metadata_kwargs(metadata, sample_id=sample_id, source_image_name=source.name)
        )
        dpi_x = dpi_y = None
        try:
            from PIL import Image
            dpi_x, dpi_y = dpi_pair(Image.open(source))
        except Exception:
            pass
        if not dpi_x or not dpi_y:
            dpi_x, dpi_y = _metadata_dpi(metadata)
        layers = [
            _layer(root, sample_id, "01_raw.png", "source_image", "Source image"),
            _layer(root, sample_id, "02_luminance_flatfield.png", "luminance_flatfield", "Luminance flatfield"),
            _layer(root, sample_id, "03_consensus_strict.png", "consensus_strict", "Consensus strict"),
            _layer(root, sample_id, "04_center_confidence.png", "center_confidence", "Center confidence"),
            _layer(root, sample_id, "05_pipeline_agreement.png", "pipeline_agreement", "Pipeline agreement"),
            _layer(root, sample_id, "06_valid_region_mask.png", "valid_region_mask", "Valid-region mask"),
            _layer(root, sample_id, "07_micro_regular_grid_overlay.png", "micro_regular_grid", "Micro regular grid"),
            _layer(root, sample_id, "08_wale_target_grid_overlay.png", "wale_target_grid", "Wale-target grid"),
            _layer(root, sample_id, "09_local_deviation_overlay.png", "local_deviation", "Local deviation overlay"),
        ]
        records.append(
            CatalogRecord(
                sample=sample,
                source_image_path=str(source),
                micro_grid=micro,
                wale_target_grid=target,
                wale_axis=row.get("wale_axis", "axis_a"),
                wale_multiplier=_float(row, "wale_multiplier", 2.0),
                quality=quality,
                layers=layers,
                source_dpi_x=dpi_x or 0.0,
                source_dpi_y=dpi_y or 0.0,
            )
        )
    return records


def _float_or(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _metadata_dpi(metadata: Dict[str, Any]) -> Tuple[float | None, float | None]:
    dpi_x = _float_or(metadata.get("source_dpi_x"), 0.0)
    dpi_y = _float_or(metadata.get("source_dpi_y"), 0.0)
    if dpi_x > 0 and dpi_y > 0:
        return dpi_x, dpi_y
    dpi = _float_or(metadata.get("source_dpi"), 0.0)
    if dpi > 0:
        return dpi, dpi
    return None, None


def _spacing_px(repeats_per_10cm: float, dpi: float | None) -> float:
    """Inverse of `gauge.repeats_per_10cm`: gauge value -> pixel period."""
    if not dpi or repeats_per_10cm <= 0:
        return 0.0
    return (dpi / 2.54 * 10.0) / repeats_per_10cm


def record_from_metadata(image_path: str | Path, metadata: Dict[str, Any]) -> CatalogRecord:
    """
    Adapter boundary: build a minimal CatalogRecord straight from sidecar YAML
    metadata, with no v13 analysis output available.

    The wale-target grid pixel periods are reconstructed from the saved
    `needles_per_10cm` / `rows_per_10cm` gauge values and the source image's
    DPI, so the cover still renders the correct stitch scale and grid lines.
    No diagnostic layer images are available in this path.
    """
    image_path = Path(image_path)
    sample_id = sanitize_sample_id(str(metadata.get("sample_id") or "") or image_path.stem, image_path.stem)

    dpi_x = dpi_y = None
    try:
        from PIL import Image
        dpi_x, dpi_y = dpi_pair(Image.open(image_path))
    except Exception:
        pass
    if not dpi_x or not dpi_y:
        dpi_x, dpi_y = _metadata_dpi(metadata)

    n10 = _float_or(metadata.get("needles_per_10cm"))
    r10 = _float_or(metadata.get("rows_per_10cm"))
    axis_order = str(metadata.get("axis_order", "") or "needle / row").strip().lower()

    if axis_order == "row / needle":
        wale_axis = "axis_b"
        axis_a_px = _spacing_px(r10, dpi_x)
        axis_b_px = _spacing_px(n10, dpi_y)
    else:
        wale_axis = "axis_a"
        axis_a_px = _spacing_px(n10, dpi_x)
        axis_b_px = _spacing_px(r10, dpi_y)

    grid = GridParams(
        axis_a_px=axis_a_px,
        axis_b_px=axis_b_px,
        x0_px=0.0,
        y0_px=0.0,
        role="wale_target_regular_grid",
    )
    quality = QualityMetrics(
        period_confidence=_float_or(metadata.get("confidence")),
        valid_region_fraction=0.0,
        local_deviation_rms_px=0.0,
        orientation_fft_deg=0.0,
        orientation_hough_deg=0.0,
        warnings="metadata-only delivery: no v13 analysis output available",
    )
    sample = SampleMetadata(
        **sample_metadata_kwargs(metadata, sample_id=sample_id, source_image_name=image_path.name)
    )
    return CatalogRecord(
        sample=sample,
        source_image_path=str(image_path),
        micro_grid=grid,
        wale_target_grid=grid,
        wale_axis=wale_axis,
        wale_multiplier=2.0,
        quality=quality,
        layers=[],
        source_dpi_x=dpi_x or 0.0,
        source_dpi_y=dpi_y or 0.0,
    )


def _grid_from_payload(raw: Any, fallback: GridParams) -> GridParams:
    if not isinstance(raw, dict):
        return fallback
    return GridParams(
        axis_a_px=_float_or(raw.get("axis_a_px"), fallback.axis_a_px),
        axis_b_px=_float_or(raw.get("axis_b_px"), fallback.axis_b_px),
        x0_px=_float_or(raw.get("x0_px"), fallback.x0_px),
        y0_px=_float_or(raw.get("y0_px"), fallback.y0_px),
        coordinate_space=str(raw.get("coordinate_space") or fallback.coordinate_space),
        role=str(raw.get("role") or fallback.role),
    )


def _grid_periods_match_visible_metadata(payload_grid: GridParams, metadata_grid: GridParams) -> bool:
    """
    Return False when the visible YAML gauge clearly implies different periods.

    Imported catalog TIFFs carry an exact grid payload, which is preferable when
    it still agrees with the editable metadata. If the operator changes the
    visible gauge later, keep delivery aligned with what the inspector canvas
    shows instead of silently preserving stale embedded periods.
    """
    if metadata_grid.axis_a_px <= 0 or metadata_grid.axis_b_px <= 0:
        return True
    if payload_grid.axis_a_px <= 0 or payload_grid.axis_b_px <= 0:
        return False

    rel_a = abs(payload_grid.axis_a_px - metadata_grid.axis_a_px) / metadata_grid.axis_a_px
    rel_b = abs(payload_grid.axis_b_px - metadata_grid.axis_b_px) / metadata_grid.axis_b_px
    return max(rel_a, rel_b) <= 0.01


def _quality_from_payload(raw: Any, fallback: QualityMetrics) -> QualityMetrics:
    if not isinstance(raw, dict):
        return fallback
    return QualityMetrics(
        period_confidence=_float_or(raw.get("period_confidence"), fallback.period_confidence),
        valid_region_fraction=_float_or(raw.get("valid_region_fraction"), fallback.valid_region_fraction),
        local_deviation_rms_px=_float_or(raw.get("local_deviation_rms_px"), fallback.local_deviation_rms_px),
        orientation_fft_deg=_float_or(raw.get("orientation_fft_deg"), fallback.orientation_fft_deg),
        orientation_hough_deg=_float_or(raw.get("orientation_hough_deg"), fallback.orientation_hough_deg),
        warnings=str(raw.get("warnings") or fallback.warnings),
    )


def record_from_payload(
    image_path: str | Path,
    metadata: Dict[str, Any],
    payload: Dict[str, Any],
) -> CatalogRecord:
    """
    Rebuild a CatalogRecord from a previously exported layered TIFF payload.

    The current editable metadata wins for labels. Embedded grid periods/phase
    are preserved when they still agree with that visible metadata; otherwise
    the visible metadata grid is used so re-saving cannot keep a stale overlay.
    """
    fallback = record_from_metadata(image_path, metadata)
    image_path = Path(image_path)
    sample_id = sanitize_sample_id(str(metadata.get("sample_id") or "") or fallback.sample.sample_id, image_path.stem)

    sample = SampleMetadata(
        **sample_metadata_kwargs(metadata, sample_id=sample_id, source_image_name=image_path.name)
    )
    micro_grid = _grid_from_payload(payload.get("micro_grid"), fallback.micro_grid)
    target_grid = _grid_from_payload(payload.get("wale_target_grid"), fallback.wale_target_grid)
    use_metadata_grid = not _grid_periods_match_visible_metadata(target_grid, fallback.wale_target_grid)
    if use_metadata_grid:
        micro_grid = fallback.micro_grid
        target_grid = fallback.wale_target_grid

    return CatalogRecord(
        sample=sample,
        source_image_path=str(image_path),
        micro_grid=micro_grid,
        wale_target_grid=target_grid,
        wale_axis=fallback.wale_axis if use_metadata_grid else str(payload.get("wale_axis") or fallback.wale_axis),
        wale_multiplier=fallback.wale_multiplier if use_metadata_grid else _float_or(payload.get("wale_multiplier"), fallback.wale_multiplier),
        quality=_quality_from_payload(payload.get("quality"), fallback.quality),
        layers=[],
        analysis_source=str(payload.get("analysis_source") or fallback.analysis_source),
        delivery_source=str(payload.get("delivery_source") or fallback.delivery_source),
        source_dpi_x=_float_or(payload.get("source_dpi_x"), fallback.source_dpi_x),
        source_dpi_y=_float_or(payload.get("source_dpi_y"), fallback.source_dpi_y),
    )
