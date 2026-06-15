from __future__ import annotations

"""
Production GUI — PySide6 version.
Boundary rule: owns file selection, metadata editing, subprocess launch,
and status reporting only. Analysis/delivery run as separate subprocesses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
import collections
import csv
import io
import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from PySide6.QtCore import (
    QEvent, QObject, QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QImage, QKeySequence, QPainter, QPainterPath,
    QPalette, QPen, QPixmap, QTextCharFormat, QTextCursor,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QComboBox, QFileDialog,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QInputDialog, QMainWindow, QMenu, QMenuBar, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QTextEdit,
    QToolTip, QVBoxLayout, QWidget,
)

try:
    from PIL import Image, ImageDraw, ImageOps
except Exception:
    Image = None
    ImageDraw = None
    ImageOps = None

try:
    from ..common.metadata_io import (
        DETECTION_KEYS, FIELD_ORDER, OPTIONAL_KEYS, REQUIRED_KEYS,
        default_metadata_for_image, find_sidecar_for_image, merged_metadata,
        read_metadata_yaml, sanitize_sample_id, write_metadata_yaml,
    )
    from ..common.gauge import confidence_pct, dpi_pair, period_cm, repeats_per_10cm
    from ..adapter.v13_adapter import record_from_metadata, record_from_payload
    from ..delivery.catalog_delivery import write_catalog_from_records
    from ..delivery.contracts import SCHEMA_ID
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from knit_grid_catalog_delivery_v14.common.metadata_io import (
        DETECTION_KEYS, FIELD_ORDER, OPTIONAL_KEYS, REQUIRED_KEYS,
        default_metadata_for_image, find_sidecar_for_image, merged_metadata,
        read_metadata_yaml, sanitize_sample_id, write_metadata_yaml,
    )
    from knit_grid_catalog_delivery_v14.common.gauge import (
        confidence_pct, dpi_pair, period_cm, repeats_per_10cm,
    )
    from knit_grid_catalog_delivery_v14.adapter.v13_adapter import record_from_metadata, record_from_payload
    from knit_grid_catalog_delivery_v14.delivery.catalog_delivery import write_catalog_from_records
    from knit_grid_catalog_delivery_v14.delivery.contracts import SCHEMA_ID

# ---------------------------------------------------------------------------
# File-type constants
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
YAML_EXTENSIONS  = {".yaml", ".yml"}
IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.tif *.tiff *.webp);;All files (*.*)"
YAML_FILTER  = "YAML metadata (*.yaml *.yml);;All files (*.*)"
MIXED = " MIXED"
TIFF_TAG_IMAGE_DESCRIPTION = 270
TIFF_TAG_KNIT_GRID_CATALOG_JSON = 65000
CATALOG_PAYLOAD_SUFFIX = ".kgc_payload.json"
SUGGESTED_DETECTION_DPI = 600.0


def _make_info_btn(tip: str) -> "QPushButton":
    """Create a small (i) info button that shows `tip` both on hover and on click."""
    from PySide6.QtCore import QPoint
    btn = QPushButton("i")
    btn.setFixedSize(14, 14)
    btn.setStyleSheet(
        "QPushButton{background:transparent;border:1px solid #c8c8c4;"
        "border-radius:7px;font-size:7pt;color:#9a9a94;padding:0;}"
        "QPushButton:hover{background:#f0f0ec;}"
    )
    btn.setToolTip(tip)
    btn.clicked.connect(
        lambda _=False, b=btn, t=tip: QToolTip.showText(
            b.mapToGlobal(b.rect().bottomLeft() + QPoint(0, 4)), t, b
        )
    )
    return btn


class _ScrollFriendlyComboBox(QComboBox):
    """
    Keep page scrolling fluid when the cursor passes over closed dropdowns.

    Qt normally lets a focused/hovered combo consume the mouse wheel and change
    its value. The popup list still scrolls normally once the menu is open.
    """

    def wheelEvent(self, event) -> None:
        view = self.view()
        if view is not None and view.isVisible():
            super().wheelEvent(event)
            return
        event.ignore()

# ---------------------------------------------------------------------------
# Schema / option lists
# ---------------------------------------------------------------------------
_OPTS_CONFIG_PATH = Path(__file__).with_name("opts_config.yaml")
_OPTS_FALLBACK: dict[str, list[str]] = {
    "measurement_state": ["measured", "estimated", "target", "nominal"],
    "gauge_source": ["image analysis", "manual count", "datasheet", "operator entry", "manual entry"],
    "machine_ref": ["Benchmark scan", "Silver Reed SK840", "Shima SES", "Stoll ADF", "Brother KH-970"],
    "bed_setup": ["single bed", "double bed", "rib", "interlock", "links-links"],
    "structure_ref": ["plain / stockinette", "reverse stockinette", "rib 1x1", "rib 2x2",
                      "tuck stitch", "cable", "intarsia", "fuzzy / brushed"],
    "yarn_tension": ["-", "1", "2", "3", "4", "5", "6", "7"],
    "tension_ref": (
        ["n/a"] +
        [f"{w}" if f == 0 else f"{w} {f}/3"
         for w in range(1, 10) for f in range(0, 3)] +
        ["10"]
    ),
    "axis_order": ["row / needle", "needle / row"],
    "manual_override": ["off", "on"],
    "brand": [
        "Cima", "Lanificio", "Filpucci", "Lana Grossa", "Schachenmayr",
        "Rowan", "Drops", "Adriafil", "Malabrigo", "Lang Yarns",
        "Sandnes", "Katia", "Bergère de France", "Austermann",
    ],
    "wash_state": ["unknown", "unwashed", "washed", "dry cleaned"],
}

def _load_opts_config() -> dict[str, list[str]]:
    if not _OPTS_CONFIG_PATH.exists():
        return dict(_OPTS_FALLBACK)
    try:
        result: dict[str, list[str]] = {}
        current_key: str | None = None
        for raw_line in _OPTS_CONFIG_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.rstrip()
            if not line or line.lstrip().startswith("#"):
                continue
            if not line.startswith(" ") and not line.startswith("\t") and line.endswith(":"):
                current_key = line[:-1].strip()
                result[current_key] = []
            elif current_key and line.lstrip().startswith("- "):
                result[current_key].append(line.lstrip()[2:].strip().strip('"').strip("'"))
        merged = dict(_OPTS_FALLBACK)
        merged.update({k: v for k, v in result.items() if v})
        return merged
    except Exception:
        return dict(_OPTS_FALLBACK)

OPTS: dict[str, list[str]] = _load_opts_config()

def _selectable(key: str) -> list[str]:
    return [v for v in OPTS.get(key, []) if not v.startswith("---")]

FIELD_SPECS: list[dict[str, Any]] = [
    {"key": "needles_per_10cm",   "label": "Needles / 10 cm",    "tier": "required", "type": "num",      "unit": "wales",    "mono": True},
    {"key": "rows_per_10cm",      "label": "Rows / 10 cm",       "tier": "required", "type": "num",      "unit": "rows",     "mono": True},
    {"key": "measurement_state",  "label": "Measurement state",  "tier": "required", "type": "select"},
    {"key": "gauge_source",       "label": "Gauge source",       "tier": "required", "type": "select"},
    {"key": "sample_id",          "label": "Sample ID",          "tier": "required", "type": "text",     "mono": True,       "placeholder": "sample"},
    {"key": "yarn_ref",           "label": "Yarn",               "tier": "required", "type": "text",     "placeholder": "e.g. Cima 4/15"},
    {"key": "brand",              "label": "Brand",              "tier": "required", "type": "select"},
    {"key": "tension_ref",        "label": "Carriage tension",   "tier": "required", "type": "select"},
    {"key": "yarn_tension",       "label": "Yarn tension",       "tier": "required", "type": "select"},
    {"key": "machine_ref",        "label": "Machine",            "tier": "required", "type": "select"},
    {"key": "bed_setup",          "label": "Bed setup",          "tier": "required", "type": "select"},
    {"key": "structure_ref",      "label": "Structure",          "tier": "required", "type": "select"},
    {"key": "preset",             "label": "Preset",             "tier": "required", "type": "readonly", "span": True},
    {"key": "axis_order",         "label": "Axis order",         "tier": "optional", "type": "seg"},
    {"key": "confidence",         "label": "Confidence",         "tier": "optional", "type": "num"},
    {"key": "wash_state",         "label": "Wash state",         "tier": "optional", "type": "select"},
    {"key": "weight_gsm",         "label": "Weight",             "tier": "optional", "type": "num",      "unit": "g/m²",     "mono": True, "placeholder": "0"},
    {"key": "weighting_ref",      "label": "Weighting",          "tier": "optional", "type": "num",      "unit": "g/needle", "mono": True, "placeholder": "0"},
    {"key": "dye_lot",            "label": "Dye lot",            "tier": "optional", "type": "text",     "mono": True,       "placeholder": "n/a"},
    {"key": "fibre_composition",  "label": "Fibre composition",  "tier": "optional", "type": "text",     "placeholder": "e.g. 100% merino wool", "span": True},
    {"key": "yarn_count",         "label": "Yarn count",         "tier": "optional", "type": "text",     "mono": True,       "placeholder": "e.g. 2/30"},
    {"key": "thread_count",       "label": "Thread count",       "tier": "optional", "type": "num",      "unit": "strands",  "mono": True, "placeholder": "1"},
    {"key": "colour_ref",         "label": "Colour",             "tier": "optional", "type": "text",     "placeholder": "e.g. ecru"},
    {"key": "notes",              "label": "Notes",              "tier": "optional", "type": "textarea", "span": True},
]
FIELD_SPEC_BY_KEY = {s["key"]: s for s in FIELD_SPECS}
TIERS = [
    {"id": "required", "label": "Required — lattice gauge + swatch identity"},
    {"id": "optional", "label": "Optional / advanced"},
]
PLAIN_FIELD_KEYS = [s["key"] for s in FIELD_SPECS if s["key"] not in DETECTION_KEYS]

INFO: dict[str, str] = {
    "needles_per_10cm": "Wales — stitch columns — counted across 10 cm of fabric width.",
    "rows_per_10cm": "Courses — stitch rows — counted up 10 cm of fabric height.",
    "measurement_state": "How the gauge was obtained.",
    "gauge_source": "Where the gauge came from.",
    "axis_order": "Which image axis maps to needles vs rows.",
    "confidence": "Detection confidence score (0–100%).",
    "needle_period": "Spacing between neighbouring wales in cm. = 10 ÷ (needles/10cm).",
    "row_period": "Spacing between neighbouring courses in cm. = 10 ÷ (rows/10cm).",
    "sample_id": "Unique identifier for this swatch.",
    "source_image_name": "Filename of the scan.",
    "yarn_ref": "Yarn name or supplier reference.",
    "brand": "Yarn manufacturer or brand name.",
    "tension_ref": "Carriage stitch-cam / tension-dial setting.",
    "yarn_tension": "Tension on the yarn feed.",
    "machine_ref": "Knitting machine or scanner.",
    "bed_setup": "Needle-bed configuration.",
    "structure_ref": "Stitch structure knitted.",
    "preset": "Auto-generated shorthand: yarn (carriage tension, yarn tension, thread count).",
    "wash_state": "Whether the swatch has been washed before scanning.",
    "weight_gsm": "Swatch weight in grams per square metre (g/m²).",
    "yarn_count": "Yarn grist in count/ply notation.",
    "thread_count": "Number of strands held together.",
    "weighting_ref": "Take-down weight per needle (g/needle).",
    "fibre_composition": "Fibre content of the yarn.",
    "dye_lot": "Dye-lot code for the yarn.",
    "colour_ref": "Colour name or reference.",
    "notes": "Free-form notes.",
    "manual_override": "Manual override flag.",
}

DSTATE: dict[str, dict[str, str]] = {
    "pending":   {"label": "Not detected", "cls": "ready",   "desc": "Run lattice detection to measure stitch gauge from the scan."},
    "detecting": {"label": "Detecting…",   "cls": "running", "desc": "Analysing the swatch lattice…"},
    "detected":  {"label": "Detected",     "cls": "done",    "desc": "Gauge measured from the lattice — correct below if it looks off."},
    "failed":    {"label": "Check needed", "cls": "needs",   "desc": "Low-confidence lattice. Verify and fix the gauge by hand."},
    "manual":    {"label": "Manual",       "cls": "queued",  "desc": "Gauge was corrected by hand and flagged as a manual override."},
    "batch":     {"label": "",             "cls": "ready",   "desc": ""},
}
STATUS_LABELS: dict[str, str] = {
    "ready": "Ready", "needs": "Needs info", "queued": "Queued",
    "running": "Running", "done": "Done", "failed": "Failed",
}
CHIP_COLORS: dict[str, tuple[str, str]] = {
    "ready":   ("#e9edf3", "#4b5b71"),
    "needs":   ("#fdecd2", "#9a6116"),
    "queued":  ("#ece4fb", "#6b3fb0"),
    "running": ("#dbe9ff", "#2458c2"),
    "done":    ("#dcf3e3", "#1f8a4c"),
    "failed":  ("#fbdfdf", "#b53636"),
}

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))

@dataclass
class SampleItem:
    item_id: str
    image_path: Path | None
    yaml_path: Path | None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "ready"
    detect_state: str = ""
    elapsed_s: float | None = None
    progress: int = 0
    output_dir: Path | None = None

@dataclass(frozen=True)
class RunSnapshot:
    item_id: str
    image_path: Path
    yaml_path: Path | None
    metadata: dict[str, Any]
    run_stem: str

def _package_root() -> Path:
    return Path(__file__).resolve().parents[2]

def _default_output_root() -> Path:
    return Path.home() / "Documents" / "KnitGridCatalogRuns"

def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _launcher_cmd(*args: str) -> list[str]:
    if _is_frozen():
        return [sys.executable, *args]
    return [sys.executable, "-m", "knit_grid_catalog_delivery_v14", *args]


def _safe_filename_stem(value: str, fallback: str = "sample") -> str:
    clean = re.sub(r"\s+", "_", value.strip())
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", clean).strip("._-")
    return clean or fallback


def _sample_output_tiff_path(output_root: Path, item: SampleItem | None, fallback: str = "sample") -> Path:
    raw = str(item.metadata.get("sample_id", "") or "") if item else ""
    if not raw and item and item.image_path:
        raw = item.image_path.stem
    return output_root / f"{_safe_filename_stem(raw, fallback)}.tiff"


def _normalise_v13_axis(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if text in {"a", "axis_a"}:
        return "axis_a"
    if text in {"b", "axis_b"}:
        return "axis_b"
    return text


def _tiff_tag_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    if isinstance(value, (tuple, list)):
        if len(value) == 1:
            return _tiff_tag_text(value[0])
        if all(isinstance(x, int) for x in value):
            return bytes(value).decode("utf-8", errors="replace").strip("\x00").strip()
    return str(value).strip()


def _catalog_payload_from_tiff(img: Any) -> dict[str, Any] | None:
    if not hasattr(img, "tag_v2"):
        return None
    for tag in (TIFF_TAG_KNIT_GRID_CATALOG_JSON, TIFF_TAG_IMAGE_DESCRIPTION):
        text = _tiff_tag_text(img.tag_v2.get(tag, ""))
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue
        if isinstance(payload, dict) and str(payload.get("schema", "")).startswith("knit_grid_catalog/"):
            return payload
    return None


def _catalog_payload_sidecar(image_path: Path) -> Path:
    return image_path.with_suffix(CATALOG_PAYLOAD_SUFFIX)


def _read_catalog_payload_sidecar(image_path: Path | None) -> dict[str, Any] | None:
    if image_path is None:
        return None
    sidecar = _catalog_payload_sidecar(image_path)
    if not sidecar.exists():
        return None
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict) and str(payload.get("schema", "")).startswith("knit_grid_catalog/"):
        return payload
    return None


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _metadata_from_catalog_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sample = dict(payload.get("sample") or {})
    sample.pop("source_image_name", None)

    target = payload.get("wale_target_grid") or {}
    quality = payload.get("quality") or {}
    wale_axis = _normalise_v13_axis(payload.get("wale_axis", "axis_a"))
    dpi_x = float(payload.get("source_dpi_x") or 0.0)
    dpi_y = float(payload.get("source_dpi_y") or 0.0)
    axis_a_px = float(target.get("axis_a_px") or 0.0) if isinstance(target, dict) else 0.0
    axis_b_px = float(target.get("axis_b_px") or 0.0) if isinstance(target, dict) else 0.0

    if wale_axis == "axis_a":
        n10 = repeats_per_10cm(axis_a_px, dpi_x)
        r10 = repeats_per_10cm(axis_b_px, dpi_y)
        axis_order = "needle / row"
    else:
        n10 = repeats_per_10cm(axis_b_px, dpi_y)
        r10 = repeats_per_10cm(axis_a_px, dpi_x)
        axis_order = "row / needle"

    if not str(sample.get("needles_per_10cm", "") or "").strip() and n10:
        sample["needles_per_10cm"] = f"{n10:.1f}"
    if not str(sample.get("rows_per_10cm", "") or "").strip() and r10:
        sample["rows_per_10cm"] = f"{r10:.1f}"
    if not str(sample.get("axis_order", "") or "").strip():
        sample["axis_order"] = axis_order
    if not str(sample.get("confidence", "") or "").strip() and isinstance(quality, dict):
        conf = quality.get("period_confidence")
        if conf not in ("", None):
            try:
                sample["confidence"] = f"{float(conf):.3f}"
            except (TypeError, ValueError):
                pass
    if sample.get("needles_per_10cm") and sample.get("rows_per_10cm"):
        if not str(sample.get("measurement_state", "") or "").strip():
            sample["measurement_state"] = "measured"
        if not str(sample.get("gauge_source", "") or "").strip():
            sample["gauge_source"] = "image analysis"
    return sample


def _detection_dpi_pair(item: SampleItem, parent: QWidget | None = None) -> tuple[float | None, float | None, str]:
    dpi_x = dpi_y = None
    source = "missing"
    if item.image_path and Image:
        try:
            img = Image.open(item.image_path)
            dpi_x, dpi_y = dpi_pair(img)
            if dpi_x and dpi_y:
                source = "embedded"
        except Exception:
            pass

    if (not dpi_x or not dpi_y) and item.image_path:
        payload = _read_catalog_payload_sidecar(item.image_path)
        if payload is not None:
            px = float(payload.get("source_dpi_x") or 0.0)
            py = float(payload.get("source_dpi_y") or 0.0)
            if px > 0 and py > 0:
                dpi_x, dpi_y = px, py
                source = "embedded_payload"

    if not dpi_x or not dpi_y:
        mx = _positive_float(item.metadata.get("source_dpi_x"))
        my = _positive_float(item.metadata.get("source_dpi_y"))
        mdpi = _positive_float(item.metadata.get("source_dpi"))
        if mx and my:
            return mx, my, "operator_saved"
        if mdpi:
            return mdpi, mdpi, "operator_saved"

        default = mx or my or mdpi or SUGGESTED_DETECTION_DPI
        value, ok = QInputDialog.getDouble(
            parent,
            "Source image DPI",
            "This image has no readable DPI metadata. Enter the scan DPI to convert the detected pixel lattice into needles/rows per 10 cm:",
            default,
            1.0,
            10000.0,
            2,
        )
        if not ok or value <= 0:
            return None, None, "missing"
        dpi_x = dpi_y = float(value)
        item.metadata["source_dpi_x"] = f"{dpi_x:.4f}".rstrip("0").rstrip(".")
        item.metadata["source_dpi_y"] = f"{dpi_y:.4f}".rstrip("0").rstrip(".")
        source = "operator"
    return dpi_x, dpi_y, source


def _missing_fields(metadata: dict[str, Any]) -> list[str]:
    return [k for k in REQUIRED_KEYS if not str(metadata.get(k, "") or "").strip()]

def _recompute_status(item: SampleItem) -> str:
    if item.status in ("queued", "running", "done", "failed"):
        return item.status
    return "needs" if _missing_fields(item.metadata) else "ready"

def _detect_state_of(item: SampleItem) -> str:
    if item.detect_state:
        return item.detect_state
    n = str(item.metadata.get("needles_per_10cm", "") or "").strip()
    r = str(item.metadata.get("rows_per_10cm", "") or "").strip()
    return "detected" if (n and r) else "pending"

_PRESET_DEPS = frozenset({"yarn_ref", "brand", "tension_ref", "yarn_tension", "thread_count", "weight_gsm"})

def _compute_preset(meta: dict) -> str:
    yarn    = str(meta.get("yarn_ref",    "") or "").strip()
    brand   = str(meta.get("brand",       "") or "").strip()
    tension = str(meta.get("tension_ref", "") or "").strip()
    yarn_t  = str(meta.get("yarn_tension","") or "").strip()
    threads = str(meta.get("thread_count","") or "").strip()
    weight  = str(meta.get("weight_gsm",  "") or "").strip()
    if not yarn:
        return ""
    base = f"{brand}/{yarn}" if brand else yarn
    t_part  = tension if tension and tension != "n/a" else ""
    yt_part = yarn_t  if yarn_t  and yarn_t  != "-"   else ""
    tc_part = threads if threads and threads != "1"    else ""
    w_part  = f"{weight} g/m²" if weight and weight not in ("0", "0.0") else ""
    parts = [p for p in (t_part, yt_part, tc_part, w_part) if p]
    return f"{base} ({', '.join(parts)})" if parts else base

def _period_cm(count: Any) -> str:
    try:
        n = float(count)
    except (TypeError, ValueError):
        return "—"
    return f"{10.0 / n:.2f} cm" if n > 0 else "—"

def _conf_pct(value: Any) -> str:
    if value in ("", None):
        return "—"
    try:
        return f"{round(float(value) * 100)}%"
    except (TypeError, ValueError):
        return "—"

def _mixed_value(targets: list[SampleItem], key: str) -> tuple[bool, str]:
    if not targets:
        return False, ""
    first = str(targets[0].metadata.get(key, "") or "")
    for item in targets[1:]:
        if str(item.metadata.get(key, "") or "") != first:
            return True, ""
    return False, first

def _quote_arg(value: str) -> str:
    return f'"{value}"' if (" " in value or not value) else value

# ---------------------------------------------------------------------------
# PIL → QPixmap helper
# ---------------------------------------------------------------------------
def _pil_to_pixmap(pil_img: "Image.Image") -> QPixmap:
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    qimg = QImage.fromData(buf.getvalue())
    return QPixmap.fromImage(qimg)

def _rounded_pixmap(pixmap: QPixmap, w: int, h: int, radius: int = 6) -> QPixmap:
    """Scale pixmap cover-fill into (w×h) with rounded corners."""
    scaled = pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
    ox = (scaled.width() - w) // 2
    oy = (scaled.height() - h) // 2
    result = QPixmap(w, h)
    result.fill(Qt.GlobalColor.transparent)
    p = QPainter(result)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(-ox, -oy, scaled)
    p.end()
    return result

# ---------------------------------------------------------------------------
# Application stylesheet
# ---------------------------------------------------------------------------
APP_QSS = """
QMainWindow, QWidget { font-family: "Segoe UI", system-ui; font-size: 10pt; color: #272722; }
QWidget { background: #f8f8f6; }
QLabel  { background: transparent; color: #272722; }

QLineEdit {
    background: #ffffff; border: 1.5px solid #ddddd8; border-radius: 5px;
    padding: 5px 8px; color: #272722; selection-background-color: #1f6f5c;
}
QLineEdit:focus   { border-color: #1f6f5c; }
QLineEdit:disabled { background: #f4f4f2; color: #9a9a94; }

QComboBox {
    background: #ffffff; border: 1.5px solid #ddddd8; border-radius: 5px;
    padding: 5px 26px 5px 8px; color: #272722;
}
QComboBox:focus { border-color: #1f6f5c; }
QComboBox::drop-down {
    border: none; width: 22px;
    subcontrol-origin: padding; subcontrol-position: right center;
}
QComboBox::down-arrow {
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #9a9a94;
    margin-right: 10px;
}
QComboBox QAbstractItemView {
    background: #ffffff; border: 1px solid #ddddd8; outline: none;
    selection-background-color: #e9edf3; selection-color: #272722;
}

QPushButton {
    background: #ffffff; border: 1.5px solid #ddddd8; border-radius: 5px;
    padding: 6px 14px; color: #272722; font-weight: 500;
}
QPushButton:hover   { background: #f4f4f2; border-color: #c8c8c4; }
QPushButton:pressed { background: #eaeae6; }
QPushButton:disabled { color: #b0b0aa; border-color: #e8e8e4; background: #f4f4f2; }
QPushButton[accent="true"] { background: #1f6f5c; border-color: #1a6050; color: #ffffff; }
QPushButton[accent="true"]:hover { background: #1a6050; }
QPushButton[seg="true"] {
    border-radius: 4px; padding: 4px 10px; background: #f0f0ec;
    border-color: #ddddd8; color: #3a3a35; font-size: 9pt; font-weight: 400;
}
QPushButton[seg="true"]:checked { background: #1f6f5c; border-color: #1f6f5c; color: #ffffff; }
QPushButton[seg="true"]:hover:!checked { background: #e8e8e4; }

QScrollBar:vertical   { background: transparent; width: 8px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px; }
QScrollBar::handle:vertical   { background: #c8c8c4; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:horizontal { background: #c8c8c4; border-radius: 4px; min-width: 24px; }
QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; height: 0; width: 0; }

QSplitter::handle           { background: #ddddd8; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical   { height: 1px; }

QGroupBox {
    border: 1.5px solid #ddddd8; border-radius: 6px; margin-top: 12px;
    padding: 14px 12px 12px 12px; background: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left;
    padding: 0 6px; color: #767670; font-size: 9pt; font-weight: 700;
    background: transparent;
}

QTextEdit, QPlainTextEdit {
    border: 1.5px solid #ddddd8; border-radius: 5px; padding: 5px;
    background: #ffffff;
}
QTextEdit:focus { border-color: #1f6f5c; }

QProgressBar {
    background: #e8e8e4; border: none; border-radius: 4px; height: 6px;
    text-align: center; font-size: 0pt;
}
QProgressBar::chunk { background: #1f6f5c; border-radius: 4px; }

QToolTip {
    background: #1c2330; color: #e8ecf2; border: none;
    padding: 8px 12px; border-radius: 6px; font-size: 9pt;
}

QFrame[frameShape="4"] { color: #ddddd8; }
QFrame[frameShape="5"] { color: #ddddd8; }

QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }

QTextEdit#log_text {
    background: #161b24; color: #cfd6e1; border: none; border-radius: 6px;
    font-family: Consolas, monospace; font-size: 9pt;
}
"""

# ---------------------------------------------------------------------------
# _Chip  (status/state pill label)
# ---------------------------------------------------------------------------
class _Chip(QLabel):
    def __init__(self, parent: QWidget | None, text: str = "", cls: str = "ready") -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set(text, cls)

    def set(self, text: str, cls: str) -> None:
        bg, fg = CHIP_COLORS.get(cls, CHIP_COLORS["ready"])
        self.setText(text)
        self.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:8px; "
            f"padding:2px 8px; font-size:9pt; font-weight:700;"
        )

# ---------------------------------------------------------------------------
# _SampleCardRow
# ---------------------------------------------------------------------------
class _SampleCardRow(QFrame):
    def __init__(self, parent: QWidget, item_id: str,
                 on_click: Callable[[str, bool, bool], None]) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self._on_click = on_click
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(62)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._indicator = QFrame()
        self._indicator.setFixedWidth(3)
        self._indicator.setStyleSheet("background: transparent;")
        outer.addWidget(self._indicator)

        content = QWidget()
        cl = QHBoxLayout(content)
        cl.setContentsMargins(10, 8, 12, 8)
        cl.setSpacing(10)

        self._thumb = QLabel()
        self._thumb.setFixedSize(46, 38)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet("background:#e8e8e4; border-radius:6px;")
        cl.addWidget(self._thumb)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)
        self._name_lbl = QLabel()
        self._name_lbl.setStyleSheet("font-weight:700; font-size:10pt; color:#272722;")
        self._file_lbl = QLabel()
        self._file_lbl.setStyleSheet("font-family:Consolas; font-size:8pt; color:#9a9a94;")
        text_col.addStretch()
        text_col.addWidget(self._name_lbl)
        text_col.addWidget(self._file_lbl)
        text_col.addStretch()
        cl.addLayout(text_col, 1)

        self._chip = _Chip(content, "", "ready")
        cl.addWidget(self._chip, 0, Qt.AlignmentFlag.AlignVCenter)

        outer.addWidget(content, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#eeeee8;")

        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(sep)
        outer_wrap = QVBoxLayout()
        outer_wrap.setContentsMargins(0, 0, 0, 0)
        outer_wrap.setSpacing(0)
        outer_wrap.addLayout(outer, 1)
        outer_wrap.addWidget(sep)
        self.setLayout(outer_wrap)

        for w in (self, content, self._thumb, self._name_lbl, self._file_lbl, self._chip):
            w.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            ctrl  = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._on_click(self.item_id, ctrl, shift)
            return True
        return False

    def set_name(self, name: str) -> None:     self._name_lbl.setText(name)
    def set_filename(self, fname: str) -> None: self._file_lbl.setText(fname)

    def set_status(self, label: str, cls: str) -> None:
        self._chip.set(label, cls)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        if pixmap and not pixmap.isNull():
            self._thumb.setPixmap(_rounded_pixmap(pixmap, 46, 38, 6))
            self._thumb.setStyleSheet("background:transparent;")

    def set_selected(self, selected: bool) -> None:
        if selected == self._selected:
            return
        self._selected = selected
        self._indicator.setStyleSheet(
            "background:#1f6f5c;" if selected else "background:transparent;"
        )
        bg = "#edf1f8" if selected else "#ffffff"
        p = self.palette()
        p.setColor(QPalette.ColorRole.Window, QColor(bg))
        self.setAutoFillBackground(True)
        self.setPalette(p)
        for w in (self._name_lbl, self._file_lbl, self._chip):
            wp = w.palette()
            wp.setColor(QPalette.ColorRole.Window, QColor(bg))
            w.setAutoFillBackground(True)
            w.setPalette(wp)

# ---------------------------------------------------------------------------
# _SampleList   (scrollable card list with Treeview-compatible API)
# ---------------------------------------------------------------------------
class _SampleList(QScrollArea):
    _sel_changed = Signal()
    delete_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._body = QWidget()
        self._body.setStyleSheet("background:#ffffff;")
        self._layout = QVBoxLayout(self._body)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addStretch()
        self.setWidget(self._body)

        self._cards: dict[str, _SampleCardRow] = {}
        self._order: list[str] = []
        self._selected: set[str] = set()
        self._anchor: str | None = None
        self._pixmaps: dict[str, QPixmap] = {}

    # -- Treeview-compatible interface --

    def selection(self) -> tuple[str, ...]:
        return tuple(i for i in self._order if i in self._selected)

    def selection_set(self, ids: Any) -> None:
        self._selected = set(ids) if not isinstance(ids, str) else {ids}
        self._refresh_display()

    def selection_remove(self, *ids: str) -> None:
        for i in ids: self._selected.discard(i)
        self._refresh_display()

    def focus(self, item_id: str | None = None) -> str:
        return item_id or ""

    def see(self, item_id: str) -> None:
        card = self._cards.get(item_id)
        if card:
            self.ensureWidgetVisible(card)

    def exists(self, item_id: str) -> bool:
        return item_id in self._cards

    def delete(self, item_id: str) -> None:
        card = self._cards.pop(item_id, None)
        if card:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._order = [i for i in self._order if i != item_id]
        self._selected.discard(item_id)
        self._pixmaps.pop(item_id, None)

    def insert(self, _parent: str, _index: str, *, iid: str,
               text: str = "", values: tuple = (), tags: tuple = (),
               image: Any = None, **_kw) -> None:
        if iid in self._cards:
            self.item(iid, text=text, values=values, tags=tags, image=image)
            return
        card = _SampleCardRow(self._body, iid, on_click=self._on_card_click)
        insert_pos = self._layout.count() - 1  # before the trailing stretch
        self._layout.insertWidget(insert_pos, card)
        self._cards[iid] = card
        self._order.append(iid)
        self.item(iid, text=text, values=values, tags=tags, image=image)

    def item(self, item_id: str, *, text: str = "", values: tuple = (),
             tags: tuple = (), image: Any = None, **_kw) -> None:
        card = self._cards.get(item_id)
        if card is None:
            return
        if values:
            sample_text = str(values[0])
            parts = sample_text.split("\n", 1)
            card.set_name(parts[0] if parts else "")
            card.set_filename(parts[1] if len(parts) > 1 else "")
            if len(values) >= 2:
                cls = "ready"
                for tag in tags:
                    if tag.startswith("status_"):
                        cls = tag[7:]; break
                card.set_status(str(values[1]), cls)
        if image is not None:
            self._pixmaps[item_id] = image
            card.set_pixmap(image)

    def tag_configure(self, *_a, **_kw) -> None: pass
    def heading(self, *_a, **_kw) -> None: pass
    def column(self, *_a, **_kw) -> None: pass

    def bind(self, sequence: str, callback: Any = None, **kwargs) -> str:
        if sequence == "<<TreeviewSelect>>" and callback:
            self._sel_changed.connect(lambda: callback())
        return ""

    def _on_card_click(self, item_id: str, ctrl: bool, shift: bool) -> None:
        if shift and self._anchor:
            try:
                a, b = self._order.index(self._anchor), self._order.index(item_id)
                self._selected = set(self._order[min(a,b):max(a,b)+1])
            except ValueError:
                self._selected = {item_id}
        elif ctrl:
            self._selected.discard(item_id) if item_id in self._selected else self._selected.add(item_id)
            self._anchor = item_id
        else:
            self._selected = {item_id}
            self._anchor = item_id
        self._refresh_display()
        self._sel_changed.emit()

    def _refresh_display(self) -> None:
        for iid, card in self._cards.items():
            card.set_selected(iid in self._selected)

    def keyPressEvent(self, event: QEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected:
                self.delete_requested.emit()
                return
        super().keyPressEvent(event)

# ---------------------------------------------------------------------------
# _ImageCanvas  (QPainter-based image + grid overlay, supports drag/keyboard)
# ---------------------------------------------------------------------------
class _ImageCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMinimumSize(200, 150)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._base_pixmap: QPixmap | None = None
        self._base_w: int = 1
        self._cell_w_base: float | None = None
        self._cell_h_base: float | None = None
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0
        self._drag_start: tuple | None = None
        self._display_scale: float = 1.0
        self._display_dx: int = 0
        self._display_dy: int = 0
        self._grid_color: QColor = QColor(255, 255, 255)

    def _compute_grid_color(self) -> QColor:
        """Return the channel-inverted average color of the current pixmap."""
        if self._base_pixmap is None or self._base_pixmap.isNull():
            return QColor(255, 255, 255)
        avg = self._base_pixmap.scaled(
            1, 1,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ).toImage().pixelColor(0, 0)
        return QColor(255 - avg.red(), 255 - avg.green(), 255 - avg.blue())

    def set_pixmap(self, pixmap: QPixmap | None, base_w: int = 1) -> None:
        self._base_pixmap = pixmap
        self._base_w = max(base_w, 1)
        self._grid_color = self._compute_grid_color()
        self.update()

    def set_grid(self, cell_w: float | None, cell_h: float | None) -> None:
        self._cell_w_base = cell_w
        self._cell_h_base = cell_h
        self.setCursor(Qt.CursorShape.SizeAllCursor if (cell_w and cell_h) else Qt.CursorShape.CrossCursor)
        self.update()

    def reset_offset(self) -> None:
        self._offset_x = 0.0
        self._offset_y = 0.0
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#1b2330"))

        if self._base_pixmap is None or self._base_pixmap.isNull():
            p.setPen(QColor("#9aa6b6"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No image")
            return

        iw, ih = self._base_pixmap.width(), self._base_pixmap.height()
        # Cover-fill: scale so image fills (covers) the canvas, cropping the excess.
        scale = max(w / max(iw, 1), h / max(ih, 1))
        sw, sh = int(iw * scale), int(ih * scale)
        dx, dy = (w - sw) // 2, (h - sh) // 2
        self._display_scale = scale
        self._display_dx = dx
        self._display_dy = dy

        p.setClipRect(0, 0, w, h)
        p.drawPixmap(dx, dy, self._base_pixmap.scaled(
            sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

        cw_base = self._cell_w_base
        ch_base = self._cell_h_base
        if cw_base and ch_base:
            cw = cw_base * scale
            ch = ch_base * scale
            if cw > 1.0 and ch > 1.0:
                p.setOpacity(0.55)
                p.setPen(QPen(self._grid_color, 2))
                # Phase offset from image origin, extended to fill the whole canvas.
                ox = (self._offset_x * scale + dx) % cw
                oy = (self._offset_y * scale + dy) % ch
                x = ox - cw
                while x < w:
                    p.drawLine(QPointF(x, 0), QPointF(x, h))
                    x += cw
                y = oy - ch
                while y < h:
                    p.drawLine(QPointF(0, y), QPointF(w, y))
                    y += ch

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self._drag_start = (event.x(), event.y(), self._offset_x, self._offset_y)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None or self._base_pixmap is None:
            return
        scale = max(self._display_scale, 1e-6)
        self._offset_x = self._drag_start[2] + (event.x() - self._drag_start[0]) / scale
        self._offset_y = self._drag_start[3] + (event.y() - self._drag_start[1]) / scale
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start = None

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_R:
            self.reset_offset(); return
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        step = max(1.0, (self._cell_w_base or 24.0) / 8.0) * (5.0 if shift else 1.0)
        if   key == Qt.Key.Key_Left:  self._offset_x -= step
        elif key == Qt.Key.Key_Right: self._offset_x += step
        elif key == Qt.Key.Key_Up:    self._offset_y -= step
        elif key == Qt.Key.Key_Down:  self._offset_y += step
        else: super().keyPressEvent(event); return
        self.update()

# ---------------------------------------------------------------------------
# _ImagePanel  (inline lattice inspector embedded in inspector column)
# ---------------------------------------------------------------------------
class _ImagePanel(QWidget):
    CTRL_W = 260

    def __init__(self, parent: QWidget,
                 on_close: Callable[[], None],
                 on_gauge_changed: Callable[[str, str, str], None],
                 on_detect: Callable[[str], None]) -> None:
        super().__init__(parent)
        self.on_close = on_close
        self.on_gauge_changed = on_gauge_changed
        self.on_detect = on_detect
        self.item: SampleItem | None = None
        self._debounce: QTimer = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._update_grid)
        self._dpi_x: float | None = None
        self._dpi_y: float | None = None
        self._thumb_scale: float = 1.0
        self._axis_order: str = "needle / row"
        self._loading = False
        self._build()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._canvas = _ImageCanvas()
        root.addWidget(self._canvas, 1)

        ctrl_scroll = QScrollArea()
        ctrl_scroll.setWidgetResizable(True)
        ctrl_scroll.setFixedWidth(self.CTRL_W)
        ctrl_scroll.setFrameShape(QFrame.Shape.NoFrame)
        ctrl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(ctrl_scroll)

        ctrl = QWidget()
        ctrl_scroll.setWidget(ctrl)
        cl = QVBoxLayout(ctrl)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(8)

        back_btn = QPushButton("← Form")
        back_btn.clicked.connect(self.on_close)
        cl.addWidget(back_btn)
        cl.addWidget(self._hsep())

        self._id_lbl = QLabel()
        self._id_lbl.setStyleSheet("font-size:11pt; font-weight:700; color:#272722;")
        self._id_lbl.setWordWrap(True)
        self._fname_lbl = QLabel()
        self._fname_lbl.setStyleSheet("font-size:8pt; color:#767670;")
        self._fname_lbl.setWordWrap(True)
        cl.addWidget(self._id_lbl)
        cl.addWidget(self._fname_lbl)
        cl.addWidget(self._hsep())

        gauge_lbl = QLabel("GAUGE")
        gauge_lbl.setStyleSheet("font-size:8pt; font-weight:700; color:#9a9a94;")
        cl.addWidget(gauge_lbl)

        g = QGridLayout()
        g.setSpacing(4)
        g.addWidget(QLabel("Needles / 10 cm"), 0, 0, 1, 2)
        self._needles_entry = QLineEdit()
        self._needles_entry.setFixedWidth(80)
        self._needles_entry.setFont(QFont("Consolas", 11))
        g.addWidget(self._needles_entry, 1, 0)
        unit1 = QLabel("wales"); unit1.setStyleSheet("color:#9a9a94;")
        g.addWidget(unit1, 1, 1)
        cross = QLabel("×"); cross.setStyleSheet("font-size:13pt; color:#c0c0bc;")
        g.addWidget(cross, 2, 0)
        g.addWidget(QLabel("Rows / 10 cm"), 3, 0, 1, 2)
        self._rows_entry = QLineEdit()
        self._rows_entry.setFixedWidth(80)
        self._rows_entry.setFont(QFont("Consolas", 11))
        g.addWidget(self._rows_entry, 4, 0)
        unit2 = QLabel("rows"); unit2.setStyleSheet("color:#9a9a94;")
        g.addWidget(unit2, 4, 1)
        cl.addLayout(g)

        self._needles_entry.textChanged.connect(self._on_gauge_input)
        self._rows_entry.textChanged.connect(self._on_gauge_input)
        self._needles_entry.keyPressEvent = self._make_step_key("needles_per_10cm",
                                                                 self._needles_entry.keyPressEvent)
        self._rows_entry.keyPressEvent = self._make_step_key("rows_per_10cm",
                                                              self._rows_entry.keyPressEvent)
        cl.addWidget(self._hsep())

        self._ro_labels: dict[str, QLabel] = {}
        for key, label in [("needle_period", "Needle period"), ("row_period", "Row period"),
                            ("confidence", "Confidence"), ("gauge_source", "Source"),
                            ("measurement_state", "State")]:
            lbl = QLabel(label); lbl.setStyleSheet("color:#9a9a94; font-size:8pt;")
            val = QLabel("—"); val.setStyleSheet("font-weight:700; font-size:9pt;")
            cl.addWidget(lbl)
            cl.addWidget(val)
            self._ro_labels[key] = val

        cl.addWidget(self._hsep())
        self._detect_btn = QPushButton("Detect lattice")
        self._detect_btn.clicked.connect(self._on_detect_clicked)
        cl.addWidget(self._detect_btn)

        cl.addWidget(self._hsep())
        hints = QLabel("↑↓ in entry  ±1\nClick+drag  shift grid\nShift+arrows  ×5\nR  reset")
        hints.setStyleSheet("color:#b0b0aa; font-family:Consolas; font-size:8pt;")
        cl.addWidget(hints)
        cl.addStretch()

    @staticmethod
    def _hsep() -> QFrame:
        f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("color:#ddddd8;"); return f

    def _make_step_key(self, field_key: str, original_fn):
        def handler(event):
            if event.key() == Qt.Key.Key_Up:
                self._step_gauge(field_key, +1); event.accept(); return
            if event.key() == Qt.Key.Key_Down:
                self._step_gauge(field_key, -1); event.accept(); return
            original_fn(event)
        return handler

    def load_item(self, item: SampleItem) -> None:
        self.item = item
        self._canvas.reset_offset()
        self._load_image()
        self._id_lbl.setText(str(item.metadata.get("sample_id", "sample") or "sample"))
        self._fname_lbl.setText(item.image_path.name if item.image_path else "no image")
        self._axis_order = str(item.metadata.get("axis_order", "") or "needle / row")
        self._loading = True
        self._needles_entry.setText(str(item.metadata.get("needles_per_10cm", "") or ""))
        self._rows_entry.setText(str(item.metadata.get("rows_per_10cm", "") or ""))
        self._loading = False
        self._refresh_readouts()
        self._update_grid()
        sl = DSTATE.get(_detect_state_of(item), {}).get("label", "")
        self._detect_btn.setEnabled(True)
        self._detect_btn.setText("Re-detect" if sl in ("Detected", "Check needed", "Manual") else "Detect lattice")
        self._canvas.setFocus()

    def _load_image(self) -> None:
        if Image is None or self.item is None:
            self._canvas.set_pixmap(None); return
        p = self.item.image_path
        if not p or not p.exists():
            self._canvas.set_pixmap(None); return
        try:
            orig = Image.open(p)
            self._dpi_x, self._dpi_y = dpi_pair(orig)
            orig_w = orig.width
            img = orig.convert("RGB")
            img.thumbnail((1400, 1100), Image.Resampling.LANCZOS)
            self._thumb_scale = img.width / max(orig_w, 1)
            pixmap = _pil_to_pixmap(img)
            self._canvas.set_pixmap(pixmap, img.width)
        except Exception:
            self._canvas.set_pixmap(None)

    def _on_gauge_input(self) -> None:
        if self._loading: return
        self._debounce.start(160)
        if self.item:
            self.on_gauge_changed(self.item.item_id,
                                  self._needles_entry.text().strip(),
                                  self._rows_entry.text().strip())
        self._refresh_readouts()

    def _update_grid(self) -> None:
        n = self._numeric(self._needles_entry.text())
        r = self._numeric(self._rows_entry.text())
        if n and r:
            # When rows run along X (row/needle axis), swap cell dimensions.
            cn, cr = (r, n) if self._axis_order == "row / needle" else (n, r)
            if self._dpi_x and self._dpi_y:
                cw = self._dpi_x / 2.54 * 10.0 / cn * self._thumb_scale
                ch = self._dpi_y / 2.54 * 10.0 / cr * self._thumb_scale
            else:
                cw = (self._canvas._base_pixmap.width() if self._canvas._base_pixmap else 400) / cn
                ch = (self._canvas._base_pixmap.height() if self._canvas._base_pixmap else 300) / cr
            self._canvas.set_grid(max(1.5, cw), max(1.5, ch))
        else:
            self._canvas.set_grid(None, None)

    def _refresh_readouts(self) -> None:
        n = self._needles_entry.text().strip()
        r = self._rows_entry.text().strip()
        self._ro_labels["needle_period"].setText(_period_cm(n) if n else "—")
        self._ro_labels["row_period"].setText(_period_cm(r) if r else "—")
        if self.item:
            self._ro_labels["confidence"].setText(_conf_pct(self.item.metadata.get("confidence")))
            self._ro_labels["gauge_source"].setText(str(self.item.metadata.get("gauge_source") or "").strip() or "—")
            self._ro_labels["measurement_state"].setText(str(self.item.metadata.get("measurement_state") or "").strip() or "—")

    @staticmethod
    def _numeric(v: Any) -> float | None:
        try:
            n = float(str(v).strip()); return n if n > 0 else None
        except (TypeError, ValueError): return None

    def _step_gauge(self, key: str, delta: float) -> None:
        entry = self._needles_entry if key == "needles_per_10cm" else self._rows_entry
        try: cur = float(entry.text().strip() or "0")
        except ValueError: cur = 0.0
        entry.setText(str(max(0.1, round(cur + delta, 1))))

    def _on_detect_clicked(self) -> None:
        if self.item is None: return
        self._detect_btn.setEnabled(False)
        self._detect_btn.setText("Detecting…")
        self.on_detect(self.item.item_id)

    def update_from_item(self, item: SampleItem) -> None:
        old_n = str(self.item.metadata.get("needles_per_10cm", "") or "") if self.item else ""
        old_r = str(self.item.metadata.get("rows_per_10cm", "") or "") if self.item else ""
        self.item = item
        new_n = str(item.metadata.get("needles_per_10cm", "") or "")
        new_r = str(item.metadata.get("rows_per_10cm", "") or "")
        self._axis_order = str(item.metadata.get("axis_order", "") or "needle / row")
        if new_n != old_n or new_r != old_r:
            self._canvas.reset_offset()
        self._loading = True
        if self._needles_entry.text().strip() != new_n: self._needles_entry.setText(new_n)
        if self._rows_entry.text().strip()    != new_r: self._rows_entry.setText(new_r)
        self._loading = False
        self._refresh_readouts()
        self._update_grid()
        sl = DSTATE.get(_detect_state_of(item), {}).get("label", "")
        self._detect_btn.setEnabled(True)
        self._detect_btn.setText("Re-detect" if sl in ("Detected", "Check needed", "Manual") else "Detect lattice")


# ---------------------------------------------------------------------------
# _SegControl  (horizontal segmented button row)
# ---------------------------------------------------------------------------
class _SegControl(QWidget):
    value_changed = Signal(str)

    def __init__(self, options: list[str], parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._options = options
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        for i, opt in enumerate(options):
            btn = QPushButton(opt)
            btn.setProperty("seg", "true")
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            self._group.addButton(btn, i)
            lay.addWidget(btn)
        # Fixed policy so the widget doesn't expand — lets the parent stretch push it flush-right
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._group.idClicked.connect(lambda _id: self.value_changed.emit(self.value()))

    def value(self) -> str:
        btn = self._group.checkedButton()
        return btn.text() if btn else ""

    def set_value(self, v: str) -> None:
        for btn in self._group.buttons():
            btn.blockSignals(True)
            btn.setChecked(btn.text() == v)
            btn.blockSignals(False)


# ---------------------------------------------------------------------------
# _SinglePreview  (172×130 thumbnail with right-34% gauge-grid overlay)
# ---------------------------------------------------------------------------
class _SinglePreview(QWidget):
    THUMB_W, THUMB_H = 172, 130
    OVERLAY_FRAC = 0.34
    clicked = Signal()

    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.THUMB_W, self.THUMB_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pixmap: "QPixmap | None" = None
        self._needles: "float | None" = None
        self._rows: "float | None" = None
        self._structure = ""
        self._axis_order = "needle / row"
        self._source_w = 0
        self._source_h = 0
        self._dpi_x: "float | None" = None
        self._dpi_y: "float | None" = None

    def set_axis_order(self, order: str) -> None:
        self._axis_order = order or "needle / row"
        self.update()

    def set_source_metrics(
        self,
        source_size: "tuple[int, int] | None",
        dpi_x: "float | None" = None,
        dpi_y: "float | None" = None,
    ) -> None:
        if source_size:
            self._source_w = max(0, int(source_size[0]))
            self._source_h = max(0, int(source_size[1]))
        else:
            self._source_w = 0
            self._source_h = 0
        self._dpi_x = dpi_x if dpi_x and dpi_x > 0 else None
        self._dpi_y = dpi_y if dpi_y and dpi_y > 0 else None
        self.update()

    def set_image(self, pixmap: "QPixmap | None") -> None:
        self._pixmap = pixmap
        self.update()

    def set_gauge(self, needles: "float | None", rows: "float | None") -> None:
        self._needles = needles
        self._rows = rows
        self.update()

    def set_structure(self, s: str) -> None:
        self._structure = s
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _grid_in_source_pixels(self) -> "tuple[float, float, float, float] | None":
        n, r = self._needles, self._rows
        if not (n and n > 0 and r and r > 0):
            return None

        # When rows run along X (row/needle axis), swap cell dimensions.
        cn, cr = (r, n) if self._axis_order == "row / needle" else (n, r)
        if not (cn and cn > 0 and cr and cr > 0):
            return None

        if self._dpi_x and self._dpi_y:
            cw = self._dpi_x / 2.54 * 10.0 / cn
            ch = self._dpi_y / 2.54 * 10.0 / cr
        elif self._source_w > 0 and self._source_h > 0:
            cw = self._source_w / cn
            ch = self._source_h / cr
        else:
            return None

        return (cw, ch, 0.0, 0.0) if cw > 0 and ch > 0 else None

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.THUMB_W, self.THUMB_H
        source_scale = 1.0
        crop_left = 0.0
        crop_top = 0.0

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 12, 12)
        p.setClipPath(clip)

        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            ox = (scaled.width() - w) // 2
            oy = (scaled.height() - h) // 2
            source_w = self._source_w or self._pixmap.width()
            source_h = self._source_h or self._pixmap.height()
            if source_w > 0:
                source_scale = scaled.width() / source_w
            elif source_h > 0:
                source_scale = scaled.height() / source_h
            crop_left = float(ox)
            crop_top = float(oy)
            p.drawPixmap(-ox, -oy, scaled)
        else:
            p.fillRect(0, 0, w, h, QColor("#e8e8e4"))

        ovx = int(w * (1.0 - self.OVERLAY_FRAC))
        p.fillRect(ovx, 0, w - ovx, h, QColor(255, 255, 255, 128))
        p.setPen(QPen(QColor(255, 255, 255, 178), 1.5))
        p.drawLine(QPointF(ovx, 0), QPointF(ovx, h))

        grid = self._grid_in_source_pixels()
        if grid is not None:
            cell_w, cell_h, x0_src, y0_src = grid
            cw = cell_w * source_scale
            ch = cell_h * source_scale
            p.setPen(QPen(QColor(26, 26, 28, 158), 1))
            p.save()
            p.setClipRect(QRectF(ovx, 0, w - ovx, h))
            if cw > 1.0:
                x0 = x0_src * source_scale - crop_left
                k0 = math.floor((ovx - x0) / cw) - 1
                k1 = math.ceil((w - x0) / cw) + 1
                for k in range(k0, k1 + 1):
                    x = x0 + k * cw
                    if ovx <= x <= w:
                        p.drawLine(QPointF(x, 0), QPointF(x, h))
            if ch > 1.0:
                y0 = y0_src * source_scale - crop_top
                k0 = math.floor((0 - y0) / ch) - 1
                k1 = math.ceil((h - y0) / ch) + 1
                for k in range(k0, k1 + 1):
                    y = y0 + k * ch
                    if 0 <= y <= h:
                        p.drawLine(QPointF(ovx, y), QPointF(w, y))
            p.restore()
        else:
            p.setPen(QColor("#9a9a94"))
            f = p.font(); f.setPointSize(7); p.setFont(f)
            p.drawText(
                QRectF(ovx + 2, 0, w - ovx - 4, h),
                Qt.AlignmentFlag.AlignCenter,
                "detect to\npreview grid",
            )

        if self._structure:
            p.setClipping(False)
            text = self._structure[:22]
            f = p.font(); f.setPointSize(7); f.setBold(False); p.setFont(f)
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(text)
            bw, bh = tw + 10, 16
            p.fillRect(QRectF(5, 5, bw, bh), QColor(0, 0, 0, 100))
            p.setPen(QColor(255, 255, 255, 210))
            p.drawText(10, 5 + bh - 4, text)

        p.end()


# ---------------------------------------------------------------------------
# _SingleHeader  (scan thumbnail + identity block)
# ---------------------------------------------------------------------------
class _SingleHeader(QWidget):
    canvas_requested = Signal(str)

    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._item: "SampleItem | None" = None
        self._build()

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)

        self._preview = _SinglePreview()
        self._preview.clicked.connect(
            lambda: self._item and self.canvas_requested.emit(self._item.item_id)
        )
        lay.addWidget(self._preview)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)

        top = QHBoxLayout()
        self._crumb = QLabel("SAMPLE")
        self._crumb.setStyleSheet(
            "font-size:8pt; font-weight:700; color:#9a9a94; letter-spacing:0.5px;"
        )
        self._status_chip = _Chip(None, "Ready", "ready")
        top.addWidget(self._crumb)
        top.addStretch()
        top.addWidget(self._status_chip)
        rl.addLayout(top)

        self._title = QLabel("—")
        self._title.setStyleSheet("font-size:14pt; font-weight:600; color:#272722;")
        self._title.setWordWrap(True)
        rl.addWidget(self._title)

        chips = QHBoxLayout(); chips.setSpacing(5)
        self._img_chip = QLabel()
        self._img_chip.setStyleSheet(
            "font-size:8pt; color:#5a5a55; background:#f0f0ec; border-radius:4px; padding:2px 6px;"
        )
        self._yaml_chip = QLabel()
        self._yaml_chip.setStyleSheet(
            "font-size:8pt; color:#5a5a55; background:#f0f0ec; border-radius:4px; padding:2px 6px;"
        )
        chips.addWidget(self._img_chip)
        chips.addWidget(self._yaml_chip)
        chips.addStretch()
        rl.addLayout(chips)

        meta_row = QHBoxLayout(); meta_row.setSpacing(14)
        self._meta: list[QLabel] = []
        for _ in range(4):
            lbl = QLabel()
            lbl.setStyleSheet("font-size:8pt; color:#9a9a94;")
            meta_row.addWidget(lbl)
            self._meta.append(lbl)
        meta_row.addStretch()
        rl.addLayout(meta_row)

        canvas_btn = QPushButton("Open canvas →")
        canvas_btn.setFixedHeight(26)
        canvas_btn.setStyleSheet("font-size:8pt; padding:2px 10px;")
        canvas_btn.clicked.connect(
            lambda: self._item and self.canvas_requested.emit(self._item.item_id)
        )
        rl.addWidget(canvas_btn, 0, Qt.AlignmentFlag.AlignLeft)
        rl.addStretch()
        lay.addWidget(right, 1)

    def load_item(self, item: "SampleItem") -> None:
        self._item = item
        meta = item.metadata

        self._preview.set_structure(str(meta.get("structure_ref", "") or ""))
        self._preview.set_axis_order(str(meta.get("axis_order", "") or "needle / row"))
        try:
            n = float(str(meta.get("needles_per_10cm", "") or ""))
            r = float(str(meta.get("rows_per_10cm", "") or ""))
            self._preview.set_gauge(n if n > 0 else None, r if r > 0 else None)
        except (ValueError, TypeError):
            self._preview.set_gauge(None, None)

        if Image and item.image_path and item.image_path.exists():
            try:
                orig = Image.open(item.image_path)
                dpi_x, dpi_y = dpi_pair(orig)
                if not dpi_x or not dpi_y:
                    mx = _positive_float(meta.get("source_dpi_x"))
                    my = _positive_float(meta.get("source_dpi_y"))
                    mdpi = _positive_float(meta.get("source_dpi"))
                    if mx and my:
                        dpi_x, dpi_y = mx, my
                    elif mdpi:
                        dpi_x = dpi_y = mdpi
                self._preview.set_source_metrics(orig.size, dpi_x, dpi_y)
                img = orig.convert("RGB")
                img.thumbnail((344, 260))
                self._preview.set_image(_pil_to_pixmap(img))
            except Exception:
                self._preview.set_source_metrics(None)
                self._preview.set_image(None)
        else:
            self._preview.set_source_metrics(None)
            self._preview.set_image(None)

        self._title.setText(str(meta.get("sample_id", "") or "(untitled)"))
        self._status_chip.set(STATUS_LABELS.get(item.status, item.status), item.status)

        img_name = item.image_path.name if item.image_path else "no image"
        self._img_chip.setText(f"⌖ {img_name}")
        if item.yaml_path:
            self._yaml_chip.setText(f"⎎ {item.yaml_path.name}")
            self._yaml_chip.setStyleSheet(
                "font-size:8pt; color:#5a5a55; background:#f0f0ec; border-radius:4px; padding:2px 6px;"
            )
        else:
            self._yaml_chip.setText("⎎ no sidecar YAML")
            self._yaml_chip.setStyleSheet(
                "font-size:8pt; color:#b53636; background:#fbdfdf; border-radius:4px; padding:2px 6px;"
            )

        n_str = str(meta.get("needles_per_10cm", "") or "")
        r_str = str(meta.get("rows_per_10cm", "") or "")
        gauge_str = f"{n_str}×{r_str}/10 cm" if (n_str and r_str) else "not set"
        elapsed = f"{item.elapsed_s:.1f}s" if item.elapsed_s else "—"
        for lbl, (k, v) in zip(self._meta, [
            ("Machine",   str(meta.get("machine_ref",   "") or "—")),
            ("Structure", str(meta.get("structure_ref", "") or "—")),
            ("Gauge",     gauge_str),
            ("Last run",  elapsed),
        ]):
            lbl.setText(f"<span style='color:#b0b0aa;'>{k} </span>{v}")

    def update_preview_gauge(self, needles: "float | None", rows: "float | None") -> None:
        self._preview.set_gauge(needles, rows)

    def update_preview_axis_order(self, order: str) -> None:
        self._preview.set_axis_order(order)


# ---------------------------------------------------------------------------
# _BatchHeader  (multi-selection header)
# ---------------------------------------------------------------------------
class _BatchHeader(QWidget):
    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        ic = QLabel("⧉")
        ic.setFixedSize(44, 44)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet(
            "background:#ece4fb; border-radius:10px; font-size:18pt; color:#6b3fb0;"
        )
        lay.addWidget(ic)

        col = QVBoxLayout()
        self._title = QLabel("Editing samples together")
        self._title.setStyleSheet("font-size:14pt; font-weight:600; color:#272722;")
        self._desc = QLabel(
            "Changes apply to all selected. Fields that differ show “Multiple.”"
        )
        self._desc.setStyleSheet("font-size:9pt; color:#9a9a94;")
        self._desc.setWordWrap(True)
        col.addWidget(self._title)
        col.addWidget(self._desc)
        lay.addLayout(col, 1)

    def load_targets(self, targets: "list[SampleItem]") -> None:
        self._title.setText(f"Editing {len(targets)} samples together")


# ---------------------------------------------------------------------------
# _DetectReadouts  (3 col × 2 row read-only detection results)
# ---------------------------------------------------------------------------
class _DetectReadouts(QWidget):
    axis_changed    = Signal(str)
    readout_changed = Signal(str, str)   # key, value

    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(16)
        lay.setVerticalSpacing(8)
        lay.setColumnStretch(0, 14)
        lay.setColumnStretch(1, 10)
        lay.setColumnStretch(2, 10)

        def _ro_cell(label: str, tip: str = "") -> "tuple[QWidget, QLabel]":
            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            cl = QVBoxLayout(cell); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(3)
            lbl_row = QHBoxLayout(); lbl_row.setSpacing(4)
            lbl = QLabel(label); lbl.setStyleSheet("font-size:8pt; color:#9a9a94;")
            lbl_row.addWidget(lbl)
            if tip:
                lbl_row.addWidget(_make_info_btn(tip))
            lbl_row.addStretch()
            cl.addLayout(lbl_row)
            val = QLabel("—")
            val.setStyleSheet("font-size:10pt; font-weight:700; color:#272722;")
            cl.addWidget(val)
            return cell, val

        # row 0: axis_order (editable seg), gauge_source, measurement_state
        ax_cell = QWidget()
        ax_cell.setStyleSheet("background: transparent;")
        ax_lay = QVBoxLayout(ax_cell); ax_lay.setContentsMargins(0, 0, 0, 0); ax_lay.setSpacing(3)
        ax_lbl_row = QHBoxLayout(); ax_lbl_row.setSpacing(4)
        ax_lbl = QLabel("Axis order (x / y)")
        ax_lbl.setStyleSheet("font-size:8pt; color:#9a9a94;")
        ax_lbl_row.addWidget(ax_lbl)
        ax_lbl_row.addWidget(_make_info_btn(INFO.get("axis_order", ""))); ax_lbl_row.addStretch()
        ax_lay.addLayout(ax_lbl_row)
        self._axis_seg = _SegControl(["row / needle", "needle / row"])
        self._axis_seg.value_changed.connect(self.axis_changed)
        ax_lay.addWidget(self._axis_seg)
        lay.addWidget(ax_cell, 0, 0)

        def _select_cell(key: str, label: str, tip: str = "") -> "tuple[QWidget, QComboBox]":
            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            cl = QVBoxLayout(cell); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(3)
            lbl_row = QHBoxLayout(); lbl_row.setSpacing(4)
            lbl = QLabel(label); lbl.setStyleSheet("font-size:8pt; color:#9a9a94;")
            lbl_row.addWidget(lbl)
            if tip:
                lbl_row.addWidget(_make_info_btn(tip))
            lbl_row.addStretch()
            cl.addLayout(lbl_row)
            combo = _ScrollFriendlyComboBox()
            combo.setEditable(False)
            for opt in OPTS.get(key, []):
                combo.addItem(opt)
            cl.addWidget(combo)
            return cell, combo

        gs_cell, self._gs_combo = _select_cell("gauge_source", "Gauge source", INFO.get("gauge_source", ""))
        self._gs_combo.currentTextChanged.connect(lambda v: self.readout_changed.emit("gauge_source", v))
        lay.addWidget(gs_cell, 0, 1)
        ms_cell, self._ms_combo = _select_cell("measurement_state", "Measurement state", INFO.get("measurement_state", ""))
        self._ms_combo.currentTextChanged.connect(lambda v: self.readout_changed.emit("measurement_state", v))
        lay.addWidget(ms_cell, 0, 2)

        # row 1: needle_period, row_period, confidence (read-only labels)
        np_cell, self._np_val = _ro_cell("Needle period", INFO.get("needle_period", ""))
        lay.addWidget(np_cell, 1, 0)
        rp_cell, self._rp_val = _ro_cell("Row period", INFO.get("row_period", ""))
        lay.addWidget(rp_cell, 1, 1)
        cf_cell, self._cf_val = _ro_cell("Confidence", INFO.get("confidence", ""))
        lay.addWidget(cf_cell, 1, 2)

    def update_from_targets(self, targets: "list[SampleItem]") -> None:
        mixed_ax, ax_val = _mixed_value(targets, "axis_order")
        self._axis_seg.blockSignals(True)
        self._axis_seg.set_value("" if mixed_ax else ax_val)
        self._axis_seg.blockSignals(False)

        for combo, key in ((self._gs_combo, "gauge_source"), (self._ms_combo, "measurement_state")):
            combo.blockSignals(True)
            mixed, val = _mixed_value(targets, key)
            idx = combo.findText(val) if not mixed else -1
            combo.setCurrentIndex(max(0, idx))
            combo.blockSignals(False)

        single = targets[0] if len(targets) == 1 else None
        if single:
            m = single.metadata
            self._np_val.setText(_period_cm(m.get("needles_per_10cm")))
            self._rp_val.setText(_period_cm(m.get("rows_per_10cm")))
            self._cf_val.setText(_conf_pct(m.get("confidence")))
        else:
            for w in (self._np_val, self._rp_val, self._cf_val):
                w.setText("—")


# ---------------------------------------------------------------------------
# _DetectionCard  (lattice detection control card)
# ---------------------------------------------------------------------------
class _DetectionCard(QFrame):
    detect_requested = Signal(list)   # list[str] item_ids
    items_changed    = Signal(list)   # list[str] item_ids – after gauge edit

    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._targets: "list[SampleItem]" = []
        self._loading = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._commit_gauge)
        self._build()

    def _build(self) -> None:
        self._set_card_style(False)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # head: icon tile + title/desc + status chip
        head = QHBoxLayout(); head.setSpacing(10)
        ic = QLabel("⋗")
        ic.setFixedSize(36, 36)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("background:#dcf3e3; border-radius:8px; font-size:16pt; color:#1f6f5c;")
        head.addWidget(ic)
        head_text = QVBoxLayout()
        _ht = QLabel("Lattice detection")
        _ht.setStyleSheet("font-size:10pt; font-weight:700; color:#272722;")
        self._head_desc = QLabel("Run lattice detection to measure stitch gauge from the scan.")
        self._head_desc.setStyleSheet("font-size:8.5pt; color:#9a9a94;")
        self._head_desc.setWordWrap(True)
        head_text.addWidget(_ht)
        head_text.addWidget(self._head_desc)
        head.addLayout(head_text, 1)
        self._chip = _Chip(None, "Not detected", "ready")
        head.addWidget(self._chip, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(head)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("QFrame{background:#e8e8e4; max-height:1px; border:none;}")
        root.addWidget(sep)

        # body: gauge inputs + detect button
        body = QHBoxLayout(); body.setSpacing(12)
        gauge_row = QHBoxLayout(); gauge_row.setSpacing(8)

        def _inp_col(label: str, unit: str) -> "tuple[QWidget, QLineEdit, QLabel]":
            col = QWidget()
            col.setStyleSheet("background: transparent;")
            cl = QVBoxLayout(col); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(3)
            lbl = QLabel(label); lbl.setStyleSheet("font-size:8pt; color:#9a9a94;")
            inp = QLineEdit(); inp.setFixedWidth(80); inp.setFont(QFont("Consolas", 12))
            inp_row = QHBoxLayout(); inp_row.setSpacing(4)
            inp_row.addWidget(inp)
            ul = QLabel(unit); ul.setStyleSheet("font-size:8pt; color:#9a9a94;")
            inp_row.addWidget(ul); inp_row.addStretch()
            cl.addWidget(lbl); cl.addLayout(inp_row)
            return col, inp, lbl

        n_col, self._needles_entry, self._n_lbl = _inp_col("Needles / 10 cm", "wales")
        x_lbl = QLabel("×"); x_lbl.setStyleSheet("font-size:13pt; color:#c0c0bc;")
        r_col, self._rows_entry, self._r_lbl = _inp_col("Rows / 10 cm", "rows")
        gauge_row.addWidget(n_col)
        gauge_row.addWidget(x_lbl, 0, Qt.AlignmentFlag.AlignBottom)
        gauge_row.addWidget(r_col)
        gauge_row.addStretch()

        self._detect_btn = QPushButton("Detect lattice")
        self._detect_btn.setProperty("accent", "true")
        self._detect_btn.setFixedHeight(34)
        self._detect_btn.clicked.connect(self._on_detect_clicked)

        body.addLayout(gauge_row, 1)
        body.addWidget(self._detect_btn, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(body)

        # readouts
        self._readouts = _DetectReadouts()
        self._readouts.axis_changed.connect(self._on_axis_changed)
        self._readouts.readout_changed.connect(self._on_readout_changed)
        root.addWidget(self._readouts)

        self._needles_entry.textChanged.connect(lambda _: self._on_gauge_input())
        self._rows_entry.textChanged.connect(lambda _: self._on_gauge_input())

    def _update_axis_labels(self, order: str) -> None:
        if order == "row / needle":
            self._n_lbl.setText("Rows\xa0/\xa010\xa0cm  (x)")
            self._r_lbl.setText("Needles\xa0/\xa010\xa0cm  (y)")
        else:
            self._n_lbl.setText("Needles\xa0/\xa010\xa0cm")
            self._r_lbl.setText("Rows\xa0/\xa010\xa0cm")

    def _set_card_style(self, alert: bool) -> None:
        if alert:
            self.setStyleSheet("QFrame{background:#fef9f0;}")
        else:
            self.setStyleSheet("QFrame{background:#ffffff;}")

    def load_targets(self, targets: "list[SampleItem]") -> None:
        self._targets = targets
        if not targets:
            return
        self._loading = True
        try:
            mixed_n, n_val = _mixed_value(targets, "needles_per_10cm")
            mixed_r, r_val = _mixed_value(targets, "rows_per_10cm")
            self._needles_entry.blockSignals(True)
            self._rows_entry.blockSignals(True)
            self._needles_entry.setText("" if mixed_n else n_val)
            self._needles_entry.setPlaceholderText(MIXED if mixed_n else "")
            self._rows_entry.setText("" if mixed_r else r_val)
            self._rows_entry.setPlaceholderText(MIXED if mixed_r else "")
            self._needles_entry.blockSignals(False)
            self._rows_entry.blockSignals(False)

            running = any(t.status == "running" for t in targets)
            if len(targets) == 1:
                ds = _detect_state_of(targets[0])
                info = DSTATE.get(ds, DSTATE["pending"])
                self._chip.set(info["label"], info["cls"])
                self._head_desc.setText(info["desc"])
                settled = ds in ("detected", "failed", "manual")
                self._detect_btn.setEnabled(not running)
                self._detect_btn.setText(
                    "Detecting…" if running else
                    "Re-detect"      if settled  else "Detect lattice"
                )
                self._set_card_style(ds == "failed")
            else:
                self._chip.set("", "ready")
                self._head_desc.setText(
                    f"Detect lattice for all {len(targets)} selected samples."
                )
                self._detect_btn.setEnabled(not running)
                self._detect_btn.setText("Detect all selected")
                self._set_card_style(False)

            self._readouts.update_from_targets(targets)
            mixed_ax, ax_val = _mixed_value(targets, "axis_order")
            self._update_axis_labels("" if mixed_ax else ax_val)
        finally:
            self._loading = False

    def _on_gauge_input(self) -> None:
        if not self._loading:
            self._debounce.start(150)

    def _commit_gauge(self) -> None:
        if not self._targets:
            return
        n_text = self._needles_entry.text().strip()
        r_text = self._rows_entry.text().strip()
        changed: set = set()
        for t in self._targets:
            if n_text and n_text != str(t.metadata.get("needles_per_10cm", "") or ""):
                t.metadata["needles_per_10cm"] = n_text
                changed.add(t.item_id)
            if r_text and r_text != str(t.metadata.get("rows_per_10cm", "") or ""):
                t.metadata["rows_per_10cm"] = r_text
                changed.add(t.item_id)
        if changed:
            self._readouts.update_from_targets(self._targets)
            self.items_changed.emit(list(changed))

    def _on_detect_clicked(self) -> None:
        ids = [t.item_id for t in self._targets]
        if ids:
            self.detect_requested.emit(ids)

    def _on_axis_changed(self, value: str) -> None:
        for t in self._targets:
            t.metadata["axis_order"] = value
        self._update_axis_labels(value)
        if self._targets:
            self.items_changed.emit([t.item_id for t in self._targets])

    def _on_readout_changed(self, key: str, value: str) -> None:
        for t in self._targets:
            t.metadata[key] = value
        if self._targets:
            self.items_changed.emit([t.item_id for t in self._targets])


# ---------------------------------------------------------------------------
# _FieldGrid  (2-column label-above-input form grid)
# ---------------------------------------------------------------------------
class _FieldGrid(QWidget):
    field_changed = Signal(str, str)   # key, value

    def __init__(self, specs: "list[dict]", parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._specs = specs
        self._widgets: "dict[str, QWidget]" = {}
        self._loading = False
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(20)
        lay.setVerticalSpacing(14)
        lay.setColumnStretch(0, 1)
        lay.setColumnStretch(1, 1)
        col, row = 0, 0
        for spec in specs:
            cell, w = self._make_cell(spec)
            self._widgets[spec["key"]] = w
            span = spec.get("span") or spec.get("type") == "textarea"
            if span:
                if col == 1:
                    row += 1; col = 0
                lay.addWidget(cell, row, 0, 1, 2)
                row += 1; col = 0
            else:
                lay.addWidget(cell, row, col)
                col += 1
                if col == 2:
                    col = 0; row += 1

    def _make_cell(self, spec: dict) -> "tuple[QWidget, QWidget]":
        key = spec["key"]
        ftype = spec.get("type", "text")
        cell = QWidget()
        cl = QVBoxLayout(cell); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(4)

        lbl_row = QHBoxLayout(); lbl_row.setSpacing(4)
        lbl = QLabel(spec["label"]); lbl.setStyleSheet("font-size:8.5pt; color:#767670;")
        lbl_row.addWidget(lbl)
        if spec.get("tier") == "required":
            rq = QLabel("*"); rq.setStyleSheet("color:#b53636; font-size:8pt;")
            lbl_row.addWidget(rq)
        tip = INFO.get(key, "")
        if tip:
            lbl_row.addWidget(_make_info_btn(tip))
        lbl_row.addStretch()
        cl.addLayout(lbl_row)

        unit = spec.get("unit", "")
        ph = spec.get("placeholder", "")
        mono = spec.get("mono", False)

        if ftype == "readonly":
            w: QWidget = QLabel()
            w.setStyleSheet(
                "background:#f4f4f2; border:1px solid #e8e8e4; border-radius:5px;"
                "padding:5px 8px; color:#5a5a55; font-size:9pt;"
            )
            w.setWordWrap(False)
        elif ftype == "textarea":
            w: QWidget = QTextEdit()
            w.setFixedHeight(68)
            w.setPlaceholderText(ph)
            w.textChanged.connect(lambda k=key: self._on_change(k))
        elif ftype == "select":
            w = _ScrollFriendlyComboBox()
            # Predefined-only fields: show as a true dropdown (non-editable, native arrow).
            # Other select fields keep editable so users can type to filter.
            strict_select = key in ("machine_ref", "bed_setup", "structure_ref", "wash_state")
            if strict_select:
                w.setEditable(False)
            else:
                w.setEditable(True)
                w.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            for opt in OPTS.get(key, _selectable(key)):
                if opt.strip().startswith("---"):
                    header = opt.strip().strip("-").strip()
                    w.addItem(f"  {header}")
                    grp_item = w.model().item(w.count() - 1)
                    if grp_item:
                        grp_item.setEnabled(False)
                        grp_item.setData(QColor("#9a9a94"), Qt.ItemDataRole.ForegroundRole)
                else:
                    w.addItem(opt)
            if ph and not strict_select:
                w.setPlaceholderText(ph)
            w.currentTextChanged.connect(lambda v, k=key: self._on_change(k))
        elif ftype == "seg":
            w = _SegControl(_selectable(key))
            w.value_changed.connect(lambda v, k=key: self._on_change(k))
        else:
            w = QLineEdit()
            w.setPlaceholderText(ph)
            if mono:
                w.setFont(QFont("Consolas", 10))
            w.textChanged.connect(lambda v, k=key: self._on_change(k))

        if unit:
            inp_row = QHBoxLayout(); inp_row.setSpacing(4)
            inp_row.addWidget(w, 1)
            ul = QLabel(unit); ul.setStyleSheet("font-size:8pt; color:#9a9a94;")
            inp_row.addWidget(ul)
            cl.addLayout(inp_row)
        else:
            cl.addWidget(w)

        return cell, w

    def _get_val(self, key: str) -> str:
        spec = FIELD_SPEC_BY_KEY.get(key, {})
        ftype = spec.get("type", "text")
        w = self._widgets.get(key)
        if w is None:
            return ""
        if ftype == "readonly":
            return w.text()
        if ftype == "textarea":
            return w.toPlainText()
        if ftype == "select":
            text = w.currentText()
            # Skip separator-header entries (they start with two spaces)
            return "" if text.startswith("  ") else text
        if ftype == "seg":
            return w.value()
        return w.text()

    def _on_change(self, key: str) -> None:
        if self._loading:
            return
        val = self._get_val(key)
        if val or val == "":   # always emit, even empty (clearing a field)
            self.field_changed.emit(key, val)

    def set_values(self, targets: "list[SampleItem]") -> None:
        self._loading = True
        try:
            for spec in self._specs:
                key = spec["key"]
                w = self._widgets.get(key)
                if w is None:
                    continue
                mixed, val = _mixed_value(targets, key)
                ftype = spec.get("type", "text")
                ph = "Multiple values…" if mixed else spec.get("placeholder", "")
                display = "" if mixed else val
                if ftype == "readonly":
                    w.setText(display)
                elif ftype == "textarea":
                    w.blockSignals(True)
                    w.setPlainText(display)
                    w.setPlaceholderText(ph)
                    w.blockSignals(False)
                elif ftype == "select":
                    w.blockSignals(True)
                    idx = w.findText(display)
                    w.setCurrentIndex(idx) if idx >= 0 else w.setCurrentText(display)
                    w.blockSignals(False)
                elif ftype == "seg":
                    w.blockSignals(True)
                    w.set_value("" if mixed else val)
                    w.blockSignals(False)
                else:
                    w.blockSignals(True)
                    w.setText(display)
                    w.setPlaceholderText(ph)
                    w.blockSignals(False)
        finally:
            self._loading = False

    def set_one(self, key: str, value: str) -> None:
        spec = FIELD_SPEC_BY_KEY.get(key, {})
        w = self._widgets.get(key)
        if w is None:
            return
        ftype = spec.get("type", "text")
        if ftype == "readonly":
            w.setText(value)
        elif ftype == "select":
            w.blockSignals(True)
            idx = w.findText(value)
            w.setCurrentIndex(idx) if idx >= 0 else w.setCurrentText(value)
            w.blockSignals(False)
        elif ftype == "textarea":
            w.blockSignals(True); w.setPlainText(value); w.blockSignals(False)
        elif ftype == "seg":
            w.blockSignals(True); w.set_value(value); w.blockSignals(False)
        else:
            w.blockSignals(True); w.setText(value); w.blockSignals(False)


# ---------------------------------------------------------------------------
# _ScopeBar  (Required / All fields switcher)
# ---------------------------------------------------------------------------
class _ScopeBar(QWidget):
    scope_changed = Signal(str)   # "required" | "all"

    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(10)

        lbl = QLabel("Fields shown")
        lbl.setStyleSheet("font-size:8.5pt; font-weight:600; color:#272722;")
        self._count = QLabel()
        self._count.setStyleSheet("font-size:8.5pt; color:#9a9a94;")
        lay.addWidget(lbl)
        lay.addWidget(self._count)
        lay.addStretch()

        self._seg = _SegControl(["Required", "All fields"])
        self._seg.set_value("Required")
        self._seg.value_changed.connect(
            lambda v: self.scope_changed.emit("required" if v == "Required" else "all")
        )
        lay.addWidget(self._seg)

    def update_count(self, scope: str) -> None:
        plain = [s for s in FIELD_SPECS if s["key"] not in DETECTION_KEYS]
        vis = sum(1 for s in plain if s.get("tier") == "required") if scope == "required" else len(plain)
        self._count.setText(f"{vis} of {len(plain)} fields")


# ---------------------------------------------------------------------------
# _Inspector  (scrollable right panel: header + scope + form + actions)
# ---------------------------------------------------------------------------
class _Inspector(QScrollArea):
    detect_requested = Signal(list)   # list[str] item_ids
    items_changed    = Signal(list)   # list[str] item_ids – after any metadata edit
    save_yaml        = Signal(list)
    attach_yaml      = Signal(list)
    reload_yaml      = Signal(list)
    reset_metadata   = Signal(list)
    canvas_requested = Signal(str)    # item_id

    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._targets: "list[SampleItem]" = []
        self._scope = "required"
        self._build()

    def _build(self) -> None:
        body = QWidget()
        self.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(24, 24, 24, 28)
        root.setSpacing(0)

        # empty state
        self._empty = QWidget()
        el = QVBoxLayout(self._empty)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addStretch()
        big = QLabel("No sample selected")
        big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        big.setStyleSheet("font-size:14pt; font-weight:600; color:#b0b0aa;")
        sub = QLabel("Pick a sample from the queue to inspect it,\nor select several to edit together.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size:9pt; color:#c0c0ba;")
        sub.setWordWrap(True)
        el.addWidget(big); el.addSpacing(6); el.addWidget(sub); el.addStretch()
        self._empty.setMinimumHeight(320)
        root.addWidget(self._empty)

        # content (shown when items selected)
        self._content = QWidget()
        self._content.setVisible(False)
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        self._single_head = _SingleHeader()
        self._single_head.canvas_requested.connect(self.canvas_requested)
        self._batch_head = _BatchHeader()
        cl.addWidget(self._single_head)
        cl.addWidget(self._batch_head)
        cl.addSpacing(16)

        div0 = QFrame(); div0.setFrameShape(QFrame.Shape.HLine)
        div0.setStyleSheet("QFrame{background:#ddddd8; max-height:1px; border:none;}")
        cl.addWidget(div0)
        cl.addSpacing(12)

        self._scope_bar = _ScopeBar()
        self._scope_bar.scope_changed.connect(self._on_scope_changed)
        cl.addWidget(self._scope_bar)
        cl.addSpacing(12)

        div1 = QFrame(); div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet("QFrame{background:#ddddd8; max-height:1px; border:none;}")
        cl.addWidget(div1)
        cl.addSpacing(16)

        # required section: detection card + required identity fields
        self._req_section = QWidget()
        req_lay = QVBoxLayout(self._req_section)
        req_lay.setContentsMargins(0, 0, 0, 0); req_lay.setSpacing(12)
        req_legend = QLabel("REQUIRED — LATTICE GAUGE + SWATCH IDENTITY")
        req_legend.setStyleSheet(
            "font-size:8pt; font-weight:700; color:#9a9a94; letter-spacing:0.4px;"
        )
        req_lay.addWidget(req_legend)

        self._detect_card = _DetectionCard()
        self._detect_card.detect_requested.connect(self.detect_requested)
        self._detect_card.items_changed.connect(self._on_card_items_changed)
        self._detect_card._needles_entry.textChanged.connect(self._on_gauge_live)
        self._detect_card._rows_entry.textChanged.connect(self._on_gauge_live)
        req_lay.addWidget(self._detect_card)

        req_plain = [s for s in FIELD_SPECS
                     if s["key"] not in DETECTION_KEYS and s.get("tier") == "required"]
        self._req_grid = _FieldGrid(req_plain)
        self._req_grid.field_changed.connect(self._on_field_changed)
        req_lay.addWidget(self._req_grid)
        cl.addWidget(self._req_section)
        cl.addSpacing(16)

        # optional section
        self._opt_section = QWidget()
        opt_lay = QVBoxLayout(self._opt_section)
        opt_lay.setContentsMargins(0, 0, 0, 0); opt_lay.setSpacing(12)
        opt_legend = QLabel("OPTIONAL / ADVANCED")
        opt_legend.setStyleSheet(
            "font-size:8pt; font-weight:700; color:#9a9a94; letter-spacing:0.4px;"
        )
        opt_lay.addWidget(opt_legend)
        opt_plain = [s for s in FIELD_SPECS
                     if s["key"] not in DETECTION_KEYS and s.get("tier") != "required"]
        self._opt_grid = _FieldGrid(opt_plain)
        self._opt_grid.field_changed.connect(self._on_field_changed)
        opt_lay.addWidget(self._opt_grid)
        self._opt_section.setVisible(False)
        cl.addWidget(self._opt_section)
        cl.addSpacing(16)

        # form actions
        actions = QWidget()
        al = QHBoxLayout(actions)
        al.setContentsMargins(0, 0, 0, 0); al.setSpacing(6)
        save_btn = QPushButton("Save YAML")
        save_btn.setProperty("accent", "true")
        save_btn.clicked.connect(lambda: self.save_yaml.emit([t.item_id for t in self._targets]))
        attach_btn = QPushButton("Attach…")
        attach_btn.clicked.connect(lambda: self.attach_yaml.emit([t.item_id for t in self._targets]))
        reload_btn = QPushButton("↺ Reload")
        reload_btn.clicked.connect(lambda: self.reload_yaml.emit([t.item_id for t in self._targets]))
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(lambda: self.reset_metadata.emit([t.item_id for t in self._targets]))
        al.addWidget(save_btn); al.addWidget(attach_btn); al.addWidget(reload_btn)
        al.addStretch(); al.addWidget(reset_btn)
        cl.addWidget(actions)
        cl.addStretch()

        root.addWidget(self._content)
        root.addStretch()
        self._scope_bar.update_count(self._scope)

    def _on_gauge_live(self, _text: str = "") -> None:
        if len(self._targets) != 1 or not self._single_head.isVisible():
            return
        try: n = float(self._detect_card._needles_entry.text().strip())
        except (ValueError, TypeError): n = None
        try: r = float(self._detect_card._rows_entry.text().strip())
        except (ValueError, TypeError): r = None
        self._single_head.update_preview_gauge(n if n and n > 0 else None,
                                                r if r and r > 0 else None)

    def _on_scope_changed(self, scope: str) -> None:
        self._scope = scope
        self._opt_section.setVisible(scope == "all")
        self._scope_bar.update_count(scope)

    def _on_field_changed(self, key: str, value: str) -> None:
        if not self._targets:
            return
        for t in self._targets:
            t.metadata[key] = value
            if key in _PRESET_DEPS:
                t.metadata["preset"] = _compute_preset(t.metadata)
            t.status = _recompute_status(t)
        if key in _PRESET_DEPS:
            preset_val = _compute_preset(self._targets[0].metadata) if len(self._targets) == 1 else ""
            self._req_grid.set_one("preset", preset_val)
            self._opt_grid.set_one("preset", preset_val)
        self.items_changed.emit([t.item_id for t in self._targets])

    def _on_card_items_changed(self, ids: list) -> None:
        for t in self._targets:
            if t.item_id in ids:
                t.status = _recompute_status(t)
                n = str(t.metadata.get("needles_per_10cm", "") or "").strip()
                r = str(t.metadata.get("rows_per_10cm", "") or "").strip()
                if n and r and t.detect_state not in ("detected", "detecting"):
                    t.detect_state = "manual"
        if len(self._targets) == 1 and self._targets[0].item_id in ids:
            t0 = self._targets[0]
            try:
                n = float(str(t0.metadata.get("needles_per_10cm", "") or ""))
                r = float(str(t0.metadata.get("rows_per_10cm", "") or ""))
                self._single_head.update_preview_gauge(n if n > 0 else None, r if r > 0 else None)
            except (ValueError, TypeError):
                self._single_head.update_preview_gauge(None, None)
            self._single_head.update_preview_axis_order(
                str(t0.metadata.get("axis_order", "") or "needle / row")
            )
            self._single_head._refresh_readouts()
        self.items_changed.emit(ids)

    def load_targets(self, targets: "list[SampleItem]") -> None:
        self._targets = targets
        has = bool(targets)
        self._empty.setVisible(not has)
        self._content.setVisible(has)
        if not has:
            return
        batch = len(targets) > 1
        self._single_head.setVisible(not batch)
        self._batch_head.setVisible(batch)
        if not batch:
            self._single_head.load_item(targets[0])
        else:
            self._batch_head.load_targets(targets)
        self._detect_card.load_targets(targets)
        self._req_grid.set_values(targets)
        self._opt_grid.set_values(targets)

    def update_item(self, item: "SampleItem") -> None:
        for i, t in enumerate(self._targets):
            if t.item_id == item.item_id:
                self._targets[i] = item
                break
        else:
            return
        self.load_targets(self._targets)


# ---------------------------------------------------------------------------
# _RunDock  (bottom: log toggle + status + progress + save buttons)
# ---------------------------------------------------------------------------
class _RunDock(QWidget):
    save_selected_clicked = Signal()
    save_all_clicked      = Signal()

    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._log_open = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # collapsible log area
        self._log_area = QWidget()
        la = QVBoxLayout(self._log_area)
        la.setContentsMargins(12, 8, 12, 0)
        self._log_text = QTextEdit()
        self._log_text.setObjectName("log_text")
        self._log_text.setReadOnly(True)
        self._log_text.setFixedHeight(160)
        la.addWidget(self._log_text)
        self._log_area.setVisible(False)
        root.addWidget(self._log_area)

        # dock bar (always visible)
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            "QWidget{background:#f0f0ec; border-top:1px solid #ddddd8;}"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 0, 12, 0)
        bl.setSpacing(10)

        self._log_toggle = QPushButton("▲ Log")
        self._log_toggle.setFixedSize(64, 28)
        self._log_toggle.clicked.connect(self._toggle_log)
        bl.addWidget(self._log_toggle)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet("font-size:9pt; color:#5a5a55;")
        bl.addWidget(self._status_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(6)
        self._progress.setFixedWidth(120)
        self._progress.setVisible(False)
        bl.addWidget(self._progress)
        bl.addStretch()

        self._save_sel_btn = QPushButton("Save selected")
        self._save_sel_btn.setFixedHeight(30)
        self._save_sel_btn.clicked.connect(self.save_selected_clicked)
        self._save_all_btn = QPushButton("Save all")
        self._save_all_btn.setFixedHeight(30)
        self._save_all_btn.clicked.connect(self.save_all_clicked)
        bl.addWidget(self._save_sel_btn)
        bl.addWidget(self._save_all_btn)

        root.addWidget(bar)

    def _toggle_log(self) -> None:
        self._log_open = not self._log_open
        self._log_area.setVisible(self._log_open)
        self._log_toggle.setText("▼ Log" if self._log_open else "▲ Log")

    def append_log(self, text: str, color: str = "") -> None:
        cursor = self._log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        ts = datetime.now().strftime("%H:%M:%S")
        cursor.insertText(f"[{ts}] ", QTextCharFormat())
        if color:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.insertText(text, fmt)
            cursor.insertText("\n", QTextCharFormat())
        else:
            cursor.insertText(text + "\n", QTextCharFormat())
        self._log_text.setTextCursor(cursor)
        self._log_text.ensureCursorVisible()

    def set_status(self, text: str, progress: "int | None" = None) -> None:
        self._status_lbl.setText(text)
        if progress is None:
            self._progress.setVisible(False)
        else:
            self._progress.setVisible(True)
            self._progress.setValue(progress)


# ---------------------------------------------------------------------------
# KnitGridApp  (main window)
# ---------------------------------------------------------------------------
class KnitGridApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._items: list[SampleItem] = []
        self._items_by_id: dict[str, SampleItem] = {}
        self._selected_ids: list[str] = []
        self._output_root = _default_output_root()
        self._detect_procs: dict[str, subprocess.Popen] = {}
        self._detect_starts: dict[str, float] = {}
        self._delivery_procs: dict[str, subprocess.Popen] = {}
        self._delivery_starts: dict[str, float] = {}
        self._extract_tmp_dir: Path | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(400)
        self._poll_timer.timeout.connect(self._poll_detect)
        self._poll_timer.timeout.connect(self._poll_delivery)
        self.setAcceptDrops(True)
        self._build_ui()
        self.setWindowTitle("Knit Grid Inspector")
        self.resize(1240, 820)
        self._poll_timer.start()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setStyleSheet(APP_QSS)
        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        main_lay.addWidget(self._build_toolbar())

        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("QFrame{background:#ddddd8; max-height:1px; border:none;}")
        main_lay.addWidget(div)

        # main split: queue left | inspector/canvas right
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)

        # left: queue panel
        queue_panel = QWidget()
        queue_panel.setMinimumWidth(220)
        queue_panel.setMaximumWidth(380)
        ql = QVBoxLayout(queue_panel)
        ql.setContentsMargins(0, 0, 0, 0)
        ql.setSpacing(0)

        q_hdr = QWidget()
        q_hdr.setFixedHeight(40)
        q_hdr.setStyleSheet(
            "QWidget{background:#f0f0ec; border-bottom:1px solid #ddddd8;}"
        )
        qhl = QHBoxLayout(q_hdr)
        qhl.setContentsMargins(14, 0, 8, 0)
        self._queue_count_lbl = QLabel("0 samples")
        self._queue_count_lbl.setStyleSheet("font-size:9pt; font-weight:600; color:#272722;")
        qhl.addWidget(self._queue_count_lbl)
        qhl.addStretch()
        self._needs_chip = _Chip(None, "0 need info", "needs")
        self._needs_chip.setVisible(False)
        qhl.addWidget(self._needs_chip)
        ql.addWidget(q_hdr)

        self._sample_list = _SampleList()
        self._sample_list._sel_changed.connect(self._on_selection_changed)
        self._sample_list.delete_requested.connect(self._remove_selected)
        ql.addWidget(self._sample_list, 1)
        self._splitter.addWidget(queue_panel)

        # right: stacked (inspector page 0, canvas page 1)
        self._stack = QStackedWidget()

        self._inspector = _Inspector()
        self._inspector.detect_requested.connect(self._start_detect)
        self._inspector.items_changed.connect(self._on_items_changed)
        self._inspector.save_yaml.connect(self._save_sidecar_for)
        self._inspector.attach_yaml.connect(self._attach_yaml_for)
        self._inspector.reload_yaml.connect(self._reload_metadata_for)
        self._inspector.reset_metadata.connect(self._reset_metadata_for)
        self._inspector.canvas_requested.connect(self._open_canvas)
        self._stack.addWidget(self._inspector)

        # canvas page
        self._canvas_item_id: "str | None" = None
        canvas_page = QWidget()
        cp_lay = QVBoxLayout(canvas_page)
        cp_lay.setContentsMargins(0, 0, 0, 0)
        cp_lay.setSpacing(0)
        back_bar = QWidget()
        back_bar.setFixedHeight(36)
        back_bar.setStyleSheet(
            "QWidget{background:#f0f0ec; border-bottom:1px solid #ddddd8;}"
        )
        bbl = QHBoxLayout(back_bar)
        bbl.setContentsMargins(12, 0, 12, 0)
        back_btn = QPushButton("← Back to inspector")
        back_btn.setFixedHeight(28)
        back_btn.setStyleSheet("font-size:8.5pt; padding:2px 10px;")
        back_btn.clicked.connect(self._close_canvas)
        bbl.addWidget(back_btn); bbl.addStretch()
        cp_lay.addWidget(back_bar)
        self._canvas_panel = _ImagePanel(
            canvas_page,
            on_close=self._close_canvas,
            on_gauge_changed=self._on_canvas_gauge_changed,
            on_detect=lambda iid: self._start_detect([iid]),
        )
        cp_lay.addWidget(self._canvas_panel, 1)
        self._stack.addWidget(canvas_page)

        self._splitter.addWidget(self._stack)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([290, 950])
        main_lay.addWidget(self._splitter, 1)

        self._dock = _RunDock()
        self._dock.save_selected_clicked.connect(
            lambda: self._deliver_for(self._selected_ids)
        )
        self._dock.save_all_clicked.connect(
            lambda: self._deliver_for([i.item_id for i in self._items])
        )
        main_lay.addWidget(self._dock)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(48)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(10)

        # "Add ▾" dropdown — flush LEFT
        add_menu_btn = QPushButton("Add ▾")
        add_menu_btn.setFixedHeight(34)
        add_menu_btn.setStyleSheet("padding: 6px 14px;")
        file_menu = QMenu(add_menu_btn)
        file_menu.addAction("Add image files…", self._add_images)
        file_menu.addAction("Open folder of scans…", self._open_folder)
        file_menu.addSeparator()
        file_menu.addAction("Clear all", self._clear_all)
        add_menu_btn.setMenu(file_menu)
        lay.addWidget(add_menu_btn)

        # Drop-zone hint (faint, shown when queue is empty)
        self._drop_hint = QLabel("Drop images or folders here")
        self._drop_hint.setStyleSheet("font-size:9pt; color:#c0c0ba;")
        lay.addWidget(self._drop_hint)
        lay.addStretch()

        self._out_btn = QPushButton()
        self._out_btn.setStyleSheet("font-size:8.5pt; padding:4px 10px; font-family:Consolas;")
        self._out_btn.clicked.connect(self._choose_output_dir)
        self._update_out_label()
        lay.addWidget(self._out_btn)

        # "Open output folder" — flush RIGHT
        open_out_btn = QPushButton("Open output ↗")
        open_out_btn.setFixedHeight(34)
        open_out_btn.setStyleSheet("padding: 4px 12px; font-size:8.5pt;")
        open_out_btn.clicked.connect(self._open_output_dir)
        lay.addWidget(open_out_btn)

        return bar

    # ── drag and drop ────────────────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                self._open_folder_path(path)
            elif path.suffix.lower() in IMAGE_EXTENSIONS:
                self._add_image_path(path)
        event.acceptProposedAction()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _update_out_label(self) -> None:
        s = str(self._output_root)
        if len(s) > 42:
            s = "…" + s[-40:]
        self._out_btn.setText(f"Out: {s}")

    def _open_output_dir(self) -> None:
        self._output_root.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(self._output_root))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(self._output_root)])
        else:
            subprocess.Popen(["xdg-open", str(self._output_root)])

    def _update_queue_header(self) -> None:
        n = len(self._items)
        needs = sum(1 for i in self._items if i.status == "needs")
        self._queue_count_lbl.setText(f"{n} sample{'s' if n != 1 else ''}")
        self._drop_hint.setVisible(n == 0)
        if needs > 0:
            self._needs_chip.set(f"{needs} need info", "needs")
            self._needs_chip.setVisible(True)
        else:
            self._needs_chip.setVisible(False)

    def _sync_row(self, item: "SampleItem") -> None:
        sid = str(item.metadata.get("sample_id", "") or item.item_id)
        fname = item.image_path.name if item.image_path else ""
        values = (f"{sid}\n{fname}", STATUS_LABELS.get(item.status, item.status))
        tags = (f"status_{item.status}",)
        if not self._sample_list.exists(item.item_id):
            thumb = self._load_thumb(item)
            self._sample_list.insert("", "end", iid=item.item_id,
                                      values=values, tags=tags, image=thumb)
        else:
            self._sample_list.item(item.item_id, values=values, tags=tags)

    @staticmethod
    def _load_thumb(item: "SampleItem") -> "QPixmap | None":
        if Image is None or not item.image_path or not item.image_path.exists():
            return None
        try:
            img = Image.open(item.image_path).convert("RGB")
            img.thumbnail((92, 76))
            return _rounded_pixmap(_pil_to_pixmap(img), 46, 38, 6)
        except Exception:
            return None

    def _on_items_changed(self, ids: list) -> None:
        for iid in ids:
            item = self._items_by_id.get(iid)
            if item:
                self._sync_row(item)
        self._update_queue_header()

    # ── file operations ───────────────────────────────────────────────────────

    def _choose_output_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Choose output folder",
                                             str(self._output_root))
        if d:
            self._output_root = Path(d)
            self._update_out_label()

    def _add_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add scan images", "", IMAGE_FILTER)
        for p in paths:
            self._add_image_path(Path(p))

    def _open_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Open folder of scans", "")
        if d:
            self._open_folder_path(Path(d))

    def _open_folder_path(self, folder: Path) -> None:
        imgs = sorted(
            p for p in folder.iterdir()
            if p.suffix.lower() in IMAGE_EXTENSIONS and not p.name.startswith(".")
        )
        for p in imgs:
            self._add_image_path(p)

    def _extract_layered_tiff(self, path: Path) -> Path | None:
        """
        If `path` is one of our v14 layered catalog TIFFs (cover page + source
        image page, with the catalog JSON embedded in the private catalog tag),
        extract the source image and a YAML sidecar into a per-session temp
        directory (cleaned up on app close) and return the extracted image path.
        Returns None for ordinary TIFFs, which are loaded as plain images.
        """
        if Image is None:
            return None
        try:
            img = Image.open(path)
            if getattr(img, "n_frames", 1) < 2:
                return None
            payload = _catalog_payload_from_tiff(img)
            if payload is None:
                return None
            sample = payload.get("sample") or {}
            source_name = str(sample.get("source_image_name") or "").strip()
            sample_id = str(sample.get("sample_id") or "").strip()
            stem = _safe_filename_stem(
                sample_id,
                _safe_filename_stem(path.stem, Path(source_name).stem if source_name else "sample"),
            )
            suffix = Path(source_name).suffix or ".png"
            if self._extract_tmp_dir is None:
                self._extract_tmp_dir = Path(tempfile.mkdtemp(prefix="kgc_extract_"))
            dest = self._extract_tmp_dir / f"{stem}{suffix}"
            # Always (re)write the extracted image and sidecar from the tiff's
            # embedded payload, even if a stale extraction already exists on
            # disk from a previous drop (e.g. one made before DPI was tracked).
            img.seek(1)
            mode = "RGBA" if "A" in img.getbands() else "RGB"
            page = img.convert(mode)
            dpi_x = float(payload.get("source_dpi_x") or 0.0)
            dpi_y = float(payload.get("source_dpi_y") or 0.0)
            save_kwargs = {"dpi": (dpi_x, dpi_y)} if dpi_x > 0 and dpi_y > 0 else {}
            page.save(dest, **save_kwargs)
            _catalog_payload_sidecar(dest).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            sidecar = dest.with_suffix(".yaml")
            meta = _metadata_from_catalog_payload(payload)
            write_metadata_yaml(sidecar, meta)
            return dest
        except Exception:
            return None

    def _add_image_path(self, path: Path) -> None:
        if path.suffix.lower() in (".tif", ".tiff"):
            extracted = self._extract_layered_tiff(path)
            if extracted is not None:
                path = extracted
        if any(i.image_path == path for i in self._items):
            return
        yaml_path = find_sidecar_for_image(path)
        meta = merged_metadata(path, [read_metadata_yaml(yaml_path)] if yaml_path else [])
        item = SampleItem(
            item_id=f"item_{len(self._items):04d}_{path.stem}",
            image_path=path,
            yaml_path=yaml_path,
            metadata=meta,
        )
        item.status = _recompute_status(item)
        self._items.append(item)
        self._items_by_id[item.item_id] = item
        self._sync_row(item)
        self._update_queue_header()
        # Auto-detect if gauge is not already in the sidecar
        n_val = str(item.metadata.get("needles_per_10cm", "") or "").strip()
        r_val = str(item.metadata.get("rows_per_10cm", "") or "").strip()
        if not n_val or not r_val:
            QTimer.singleShot(300, lambda iid=item.item_id: self._start_detect([iid]))

    def _remove_selected(self) -> None:
        ids = list(self._sample_list.selection())
        if not ids:
            return
        for iid in ids:
            self._items = [i for i in self._items if i.item_id != iid]
            self._items_by_id.pop(iid, None)
            if iid in self._selected_ids:
                self._selected_ids.remove(iid)
            for procs in (self._detect_procs, self._delivery_procs):
                proc = procs.pop(iid, None)
                if proc:
                    try: proc.terminate()
                    except Exception: pass
            self._detect_starts.pop(iid, None)
            self._delivery_starts.pop(iid, None)
            self._sample_list.delete(iid)
        self._inspector.load_targets([])
        self._update_queue_header()

    def _clear_all(self) -> None:
        self._items.clear()
        self._items_by_id.clear()
        self._selected_ids.clear()
        for iid in list(self._detect_procs):
            try: self._detect_procs[iid].terminate()
            except Exception: pass
        self._detect_procs.clear()
        self._detect_starts.clear()
        for iid in list(self._delivery_procs):
            try: self._delivery_procs[iid].terminate()
            except Exception: pass
        self._delivery_procs.clear()
        self._delivery_starts.clear()
        # Rebuild the list widget contents
        for card_id in list(self._sample_list._cards):
            self._sample_list.delete(card_id)
        self._inspector.load_targets([])
        self._update_queue_header()

    # ── selection ────────────────────────────────────────────────────────────

    def _on_selection_changed(self) -> None:
        ids = list(self._sample_list.selection())
        self._selected_ids = ids
        targets = [self._items_by_id[i] for i in ids if i in self._items_by_id]
        self._inspector.load_targets(targets)
        if self._stack.currentIndex() == 1:
            self._close_canvas()

    # ── canvas view ──────────────────────────────────────────────────────────

    def _open_canvas(self, item_id: str) -> None:
        item = self._items_by_id.get(item_id)
        if not item:
            return
        self._canvas_item_id = item_id
        self._canvas_panel.load_item(item)
        self._stack.setCurrentIndex(1)

    def _close_canvas(self) -> None:
        self._stack.setCurrentIndex(0)
        self._canvas_item_id = None

    def _on_canvas_gauge_changed(self, item_id: str, needles: str, rows: str) -> None:
        item = self._items_by_id.get(item_id)
        if not item:
            return
        if needles:
            item.metadata["needles_per_10cm"] = needles
        if rows:
            item.metadata["rows_per_10cm"] = rows
        item.status = _recompute_status(item)
        self._sync_row(item)

    # ── metadata save / reload / reset ──────────────────────────────────────

    def _is_extracted_temp_path(self, path: Path | None) -> bool:
        if path is None or self._extract_tmp_dir is None:
            return False
        try:
            path.resolve().relative_to(self._extract_tmp_dir.resolve())
            return True
        except ValueError:
            return False

    def _yaml_save_path_for(self, item: SampleItem) -> Path | None:
        if item.image_path and self._is_extracted_temp_path(item.image_path):
            sample_id = _safe_filename_stem(
                str(item.metadata.get("sample_id", "") or ""),
                item.image_path.stem,
            )
            return self._output_root / f"{sample_id}.yaml"
        if item.yaml_path:
            return item.yaml_path
        if item.image_path:
            return item.image_path.with_suffix(".yaml")
        return None

    def _save_sidecar_for(self, ids: list) -> None:
        for iid in ids:
            item = self._items_by_id.get(iid)
            if not item:
                continue
            yaml_path = self._yaml_save_path_for(item)
            if yaml_path:
                try:
                    # Write yarn_name alias alongside yarn_ref for retrocompatibility.
                    meta_out = dict(item.metadata)
                    yarn_ref = str(meta_out.get("yarn_ref", "") or "").strip()
                    if yarn_ref:
                        meta_out["yarn_name"] = yarn_ref
                    write_metadata_yaml(yaml_path, meta_out)
                    item.yaml_path = yaml_path
                    self._dock.append_log(f"Saved YAML: {yaml_path}", "#86efac")
                except Exception as exc:
                    self._dock.append_log(f"Save failed: {exc}", "#fca5a5")

    def _deliver_for(self, ids: list) -> None:
        self._save_sidecar_for(ids)
        for iid in ids:
            item = self._items_by_id.get(iid)
            if item:
                self._launch_delivery(item)

    def _launch_delivery(self, item: "SampleItem") -> None:
        iid = item.item_id
        if iid in self._delivery_procs:
            return
        sample_id = _safe_filename_stem(
            str(item.metadata.get("sample_id", "") or ""), item.image_path.stem if item.image_path else "sample"
        )
        deliver_out = self._output_root / sample_id
        deliver_out.mkdir(parents=True, exist_ok=True)

        out_dir = item.output_dir
        has_v13_output = bool(out_dir and (out_dir / "v13_grid_summary.csv").exists())
        if not has_v13_output:
            self._deliver_from_metadata_only(item, deliver_out)
            return

        # Copy YAML into the v13 output dir so the delivery adapter can find it.
        if item.yaml_path and item.yaml_path.exists():
            try:
                shutil.copy2(item.yaml_path, out_dir / f"{sample_id}.yaml")
            except Exception:
                pass
        cmd = _launcher_cmd(
            "--run-delivery",
            "--v13-output", str(out_dir),
            "--out", str(deliver_out),
        )
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(_package_root()),
            )
        except Exception as exc:
            self._dock.append_log(f"Delivery launch failed: {exc}", "#fca5a5")
            return
        self._delivery_procs[iid] = proc
        self._delivery_starts[iid] = time.monotonic()
        self._dock.append_log(
            f"Delivering {item.image_path.name if item.image_path else sample_id} → {deliver_out.name}",
            "#93c5fd",
        )
        self._update_dock_status()

    def _deliver_from_metadata_only(self, item: "SampleItem", deliver_out: Path) -> None:
        """
        Build the catalog TIFF straight from saved YAML metadata when no v13
        analysis output exists for this item (e.g. the gauge values were
        already filled in from a previous session). The wale-target grid is
        reconstructed from needles_per_10cm/rows_per_10cm; no diagnostic
        layer images are included.
        """
        name = item.image_path.name if item.image_path else item.item_id
        if not item.image_path or not item.image_path.exists():
            self._dock.append_log(f"Save skipped for {name}: source image not found.", "#fca5a5")
            return
        try:
            payload = _read_catalog_payload_sidecar(item.image_path)
            if payload is not None:
                record = record_from_payload(item.image_path, item.metadata, payload)
            else:
                record = record_from_metadata(item.image_path, item.metadata)
            write_catalog_from_records([record], deliver_out)
        except Exception as exc:
            self._dock.append_log(f"Delivery failed for {name}: {exc}", "#fca5a5")
            return
        tiffs = sorted((deliver_out / "layered_tiff").glob("*.tiff"))
        if not tiffs:
            self._dock.append_log(f"Delivered {name}, but no TIFF was produced in {deliver_out}", "#fca5a5")
            return
        for tiff_path in tiffs:
            dest = _sample_output_tiff_path(self._output_root, item, Path(tiff_path).stem)
            try:
                shutil.copy2(tiff_path, dest)
                self._dock.append_log(
                    f"Saved {name} → {dest} (from saved metadata, no v13 layers)", "#86efac"
                )
            except Exception as exc:
                self._dock.append_log(f"Copy failed for {tiff_path.name}: {exc}", "#fca5a5")
        shutil.rmtree(deliver_out, ignore_errors=True)

    def _poll_delivery(self) -> None:
        if not self._delivery_procs:
            return
        finished = []
        for iid, proc in list(self._delivery_procs.items()):
            rc = proc.poll()
            if rc is None:
                continue
            finished.append(iid)
            _stdout, stderr = proc.communicate()
            item = self._items_by_id.get(iid)
            name = item.image_path.name if (item and item.image_path) else iid
            if rc == 0:
                sample_id = _safe_filename_stem(
                    str(item.metadata.get("sample_id", "") or "") if item else "", "sample"
                )
                deliver_out = self._output_root / sample_id
                tiffs = sorted((deliver_out / "layered_tiff").glob("*.tiff"))
                if not tiffs:
                    self._dock.append_log(f"Delivered {name}, but no TIFF was produced in {deliver_out}", "#fca5a5")
                else:
                    for tiff_path in tiffs:
                        dest = _sample_output_tiff_path(self._output_root, item, Path(tiff_path).stem)
                        try:
                            shutil.copy2(tiff_path, dest)
                            self._dock.append_log(f"Saved {name} → {dest}", "#86efac")
                        except Exception as exc:
                            self._dock.append_log(f"Copy failed for {tiff_path.name}: {exc}", "#fca5a5")
                shutil.rmtree(deliver_out, ignore_errors=True)
            else:
                detail = (stderr or "").strip().splitlines()
                detail_msg = detail[-1] if detail else ""
                self._dock.append_log(f"Delivery failed (rc={rc}): {name} — {detail_msg}", "#fca5a5")
        for iid in finished:
            self._delivery_procs.pop(iid, None)
            self._delivery_starts.pop(iid, None)
        if finished:
            self._update_dock_status()

    def _attach_yaml_for(self, ids: list) -> None:
        if not ids:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Attach YAML sidecar", "", YAML_FILTER)
        if not path:
            return
        yaml_path = Path(path)
        meta = read_metadata_yaml(yaml_path)
        for iid in ids:
            item = self._items_by_id.get(iid)
            if item:
                item.yaml_path = yaml_path
                item.metadata.update(
                    {k: v for k, v in meta.items() if v not in (None, "")}
                )
                item.status = _recompute_status(item)
                self._sync_row(item)
        targets = [self._items_by_id[i] for i in ids if i in self._items_by_id]
        self._inspector.load_targets(targets)
        self._update_queue_header()

    def _reload_metadata_for(self, ids: list) -> None:
        for iid in ids:
            item = self._items_by_id.get(iid)
            if not item or not item.yaml_path:
                continue
            meta = read_metadata_yaml(item.yaml_path)
            item.metadata = merged_metadata(item.image_path, [meta])
            item.status = _recompute_status(item)
            self._sync_row(item)
        targets = [self._items_by_id[i] for i in ids if i in self._items_by_id]
        self._inspector.load_targets(targets)

    def _reset_metadata_for(self, ids: list) -> None:
        for iid in ids:
            item = self._items_by_id.get(iid)
            if not item:
                continue
            item.metadata = merged_metadata(item.image_path, [])
            item.detect_state = ""
            item.status = _recompute_status(item)
            self._sync_row(item)
        targets = [self._items_by_id[i] for i in ids if i in self._items_by_id]
        self._inspector.load_targets(targets)
        self._update_queue_header()

    # ── detection subprocess ─────────────────────────────────────────────────

    def _start_detect(self, ids: list) -> None:
        for iid in ids:
            item = self._items_by_id.get(iid)
            if not item or not item.image_path or not item.image_path.exists():
                continue
            if iid in self._detect_procs:
                continue
            self._launch_detect_item(item)

    def _launch_detect_item(self, item: "SampleItem") -> None:
        iid = item.item_id
        out_dir = Path(tempfile.mkdtemp(prefix="kgc_detect_"))
        item.output_dir = out_dir
        item.status = "running"
        item.detect_state = "detecting"
        item.progress = 0
        item.elapsed_s = None

        label = sanitize_sample_id(
            str(item.metadata.get("sample_id", "") or ""), item.image_path.stem
        )
        cmd = _launcher_cmd(
            "--run-v13",
            "--input", f"{label}={item.image_path}",
            "--out", str(out_dir),
        )
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(_package_root()),
            )
        except Exception as exc:
            item.status = "failed"
            item.detect_state = "failed"
            self._dock.append_log(f"Launch failed: {exc}", "#fca5a5")
            self._sync_row(item)
            return

        self._detect_procs[iid] = proc
        self._detect_starts[iid] = time.monotonic()
        self._dock.append_log(
            f"Detection started: {item.image_path.name}", "#93c5fd"
        )
        self._sync_row(item)
        if any(t.item_id == iid for t in self._inspector._targets):
            self._inspector.update_item(item)

    def _poll_detect(self) -> None:
        if not self._detect_procs:
            return
        finished: list[str] = []
        for iid, proc in list(self._detect_procs.items()):
            item = self._items_by_id.get(iid)
            if not item:
                finished.append(iid); continue
            rc = proc.poll()
            if rc is None:
                elapsed = time.monotonic() - self._detect_starts.get(iid, time.monotonic())
                item.elapsed_s = elapsed
                item.progress = min(95, int(elapsed * 10))
                continue
            finished.append(iid)
            item.elapsed_s = time.monotonic() - self._detect_starts.get(iid, time.monotonic())
            stdout, stderr = proc.communicate()
            if rc == 0:
                self._ingest_detect_result(item)
            else:
                item.status = "failed"
                item.detect_state = "failed"
                detail_lines = [line for line in (stderr or stdout or "").strip().splitlines() if line.strip()]
                detail = f" - {detail_lines[-1]}" if detail_lines else ""
                self._dock.append_log(
                    f"Detection failed (rc={rc}): {item.image_path.name if item.image_path else iid}{detail}",
                    "#fca5a5",
                )
            self._sync_row(item)
            if any(t.item_id == iid for t in self._inspector._targets):
                self._inspector.update_item(item)

        for iid in finished:
            self._detect_procs.pop(iid, None)
            self._detect_starts.pop(iid, None)
        if finished:
            self._update_queue_header()
        self._update_dock_status()

    def _update_dock_status(self) -> None:
        if self._delivery_procs:
            elapsed = max(
                (time.monotonic() - start for start in self._delivery_starts.values()),
                default=0.0,
            )
            n = len(self._delivery_procs)
            label = f"Saving {n} item{'s' if n != 1 else ''}…"
            self._dock.set_status(label, min(95, int(elapsed * 8)))
        elif self._detect_procs:
            elapsed = max(
                (time.monotonic() - start for start in self._detect_starts.values()),
                default=0.0,
            )
            n = len(self._detect_procs)
            label = f"Detecting {n} item{'s' if n != 1 else ''}…"
            self._dock.set_status(label, min(95, int(elapsed * 10)))
        else:
            self._dock.set_status("Ready")

    def _ingest_detect_result(self, item: "SampleItem") -> None:
        out_dir = item.output_dir
        if not out_dir:
            return
        summary = out_dir / "v13_grid_summary.json"
        if not summary.exists():
            item.status = "failed"
            item.detect_state = "failed"
            self._dock.append_log(
                f"No summary JSON: {item.image_path.name if item.image_path else '?'}",
                "#fca5a5",
            )
            return
        try:
            raw = json.loads(summary.read_text(encoding="utf-8"))
            data = raw[0] if isinstance(raw, list) else raw
            if not isinstance(data, dict):
                raise ValueError("unexpected JSON shape")
        except Exception:
            item.status = "failed"; item.detect_state = "failed"; return

        dpi_x, dpi_y, dpi_source = _detection_dpi_pair(item, self)
        if not dpi_x or not dpi_y:
            item.status = "failed"
            item.detect_state = "failed"
            self._dock.append_log(
                f"Detection needs DPI: {item.image_path.name if item.image_path else '?'}",
                "#fca5a5",
            )
            return

        wale_axis = _normalise_v13_axis(data.get("wale_axis", "axis_a"))
        axis_a_px = float(data.get("selected_target_axis_a_px", 0) or 0)
        axis_b_px = float(data.get("selected_target_axis_b_px", 0) or 0)
        conf = float(data.get("period_confidence", 0) or 0)

        if wale_axis == "axis_a":
            needle_px, row_px = axis_a_px, axis_b_px
            dn, dr = dpi_x, dpi_y
        else:
            needle_px, row_px = axis_b_px, axis_a_px
            dn, dr = dpi_y, dpi_x

        n10 = repeats_per_10cm(needle_px, dn)
        r10 = repeats_per_10cm(row_px, dr)

        if n10 and r10 and n10 > 0 and r10 > 0:
            item.metadata["needles_per_10cm"] = f"{n10:.1f}"
            item.metadata["rows_per_10cm"]    = f"{r10:.1f}"
            item.metadata["axis_order"]       = "needle / row" if wale_axis == "axis_a" else "row / needle"
            item.metadata["gauge_source"]     = "image analysis"
            item.metadata["measurement_state"] = "measured"
            item.metadata["confidence"]       = f"{conf:.3f}"
            item.detect_state = "detected" if conf >= 0.6 else "failed"
            item.status = ""  # clear transient "running" so _recompute_status evaluates fields
            item.status = _recompute_status(item)
            dpi_note = f", dpi {dpi_x:g} ({dpi_source.replace('_', ' ')})"
            self._dock.append_log(
                f"Detected {item.image_path.name if item.image_path else '?'}: "
                f"{item.metadata['needles_per_10cm']}×{item.metadata['rows_per_10cm']}"
                f" — conf {conf:.0%}{dpi_note}",
                "#86efac",
            )
        else:
            item.status = "failed"
            item.detect_state = "failed"
            self._dock.append_log(
                f"Detection zero-period: {item.image_path.name if item.image_path else '?'}",
                "#fca5a5",
            )

    def closeEvent(self, event) -> None:
        for proc in self._detect_procs.values():
            try:
                proc.terminate()
            except Exception:
                pass
        if self._extract_tmp_dir is not None:
            shutil.rmtree(self._extract_tmp_dir, ignore_errors=True)
            self._extract_tmp_dir = None
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def gui_main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("KnitGridInspector")
    win = KnitGridApp()
    win.show()
    sys.exit(app.exec())


def main() -> None:
    gui_main()


if __name__ == "__main__":
    main()
