
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


SCHEMA_ID = "knit_grid_catalog/v14"


@dataclass(frozen=True)
class GridParams:
    axis_a_px: float
    axis_b_px: float
    x0_px: float
    y0_px: float
    coordinate_space: str = "original_image_px"
    role: str = "regular_grid"


@dataclass(frozen=True)
class QualityMetrics:
    period_confidence: float
    valid_region_fraction: float
    local_deviation_rms_px: float
    orientation_fft_deg: float
    orientation_hough_deg: float
    warnings: str = ""


@dataclass(frozen=True)
class LayerAsset:
    role: str
    path: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class SampleMetadata:
    sample_id: str
    source_image_name: str
    # Lattice gauge (script-derived; manual entry flips gauge_source/measurement_state).
    needles_per_10cm: str = ""
    rows_per_10cm: str = ""
    measurement_state: str = ""
    gauge_source: str = ""
    axis_order: str = "needle / row"
    confidence: str = ""
    # Swatch identity - required alongside the gauge to make it meaningful.
    yarn_ref: str = ""
    tension_ref: str = "n/a"
    yarn_tension: str = "n/a"
    machine_ref: str = "Benchmark scan"
    bed_setup: str = "single bed"
    structure_ref: str = "plain / stockinette"
    brand: str = ""
    preset: str = ""
    wash_state: str = "unknown"
    operator: str = ""
    # Optional / advanced detail.
    weighting_ref: float = 0.0
    weight_gsm: str = ""
    dye_lot: str = ""
    fibre_composition: str = ""
    yarn_count: str = ""
    thread_count: str = "1"
    colour_ref: str = ""
    notes: str = ""


@dataclass(frozen=True)
class CatalogRecord:
    sample: SampleMetadata
    source_image_path: str
    micro_grid: GridParams
    wale_target_grid: GridParams
    wale_axis: str
    wale_multiplier: float
    quality: QualityMetrics
    layers: List[LayerAsset] = field(default_factory=list)
    analysis_source: str = "v13_literature_guided_grid_refinement"
    delivery_source: str = "v14_catalog_delivery_layer"
    source_dpi_x: float = 0.0
    source_dpi_y: float = 0.0

    def payload(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA_ID,
            "analysis_source": self.analysis_source,
            "delivery_source": self.delivery_source,
            "sample": asdict(self.sample),
            "source_image_path": self.source_image_path,
            "source_dpi_x": self.source_dpi_x,
            "source_dpi_y": self.source_dpi_y,
            "micro_grid": asdict(self.micro_grid),
            "wale_target_grid": asdict(self.wale_target_grid),
            "wale_axis": self.wale_axis,
            "wale_multiplier": self.wale_multiplier,
            "quality": asdict(self.quality),
            "layers": [asdict(x) for x in self.layers],
        }

    def metadata_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.payload(), indent=indent, ensure_ascii=False)


@dataclass(frozen=True)
class CatalogBatch:
    records: List[CatalogRecord]
    title: str = "Bottom box refinement - right-strip cover"
    delivery_source: str = "v14_catalog_delivery_layer"

    def payload(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA_ID + "/batch",
            "title": self.title,
            "delivery_source": self.delivery_source,
            "n_records": len(self.records),
            "records": [r.payload() for r in self.records],
        }
