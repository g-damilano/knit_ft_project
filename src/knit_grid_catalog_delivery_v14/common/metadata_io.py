from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable
import re


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}

# Lattice gauge + script-derived readouts. Owned by the detection card in the
# interface; not rendered as plain form fields.
DETECTION_KEYS = [
    "needles_per_10cm",
    "rows_per_10cm",
    "measurement_state",
    "gauge_source",
    "axis_order",
    "confidence",
]

# Required: the lattice gauge is meaningless without the swatch identified, so
# the gauge and the identity fields are one required group.
REQUIRED_KEYS = DETECTION_KEYS[:4] + [
    "sample_id",
    "yarn_ref",
    "tension_ref",
    "yarn_tension",
    "machine_ref",
    "bed_setup",
    "structure_ref",
]

OPTIONAL_KEYS = [
    "brand",
    "preset",
    "wash_state",
    "operator",
    "weighting_ref",
    "weight_gsm",
    "dye_lot",
    "fibre_composition",
    "yarn_count",
    "thread_count",
    "colour_ref",
    "notes",
]

FIELD_ORDER = REQUIRED_KEYS + ["axis_order", "confidence"] + OPTIONAL_KEYS

# Maps older sidecar YAML keys (pre-rework schema) onto the current field set so
# existing samples keep loading. Applied only when the new key is absent.
LEGACY_KEY_ALIASES = {
    "yarn_ref": ("yarn_name",),
    "tension_ref": ("tension",),
    "machine_ref": ("machine",),
    "structure_ref": ("descriptor", "swatch_type"),
    "weighting_ref": ("weight_g_per_needle", "weight_per_needle_g", "weight_per_needle"),
}


def sanitize_sample_id(value: str | None, fallback: str = "sample") -> str:
    raw = (value or "").strip() or fallback
    clean = re.sub(r"\s+", "_", raw)
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", clean).strip("._-")
    return clean or fallback


def parse_scalar(value: str) -> Any:
    text = value.strip()
    if not text:
        return ""
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    lowered = text.lower()
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    if lowered in {"null", "none", "~"}:
        return None
    try:
        if re.fullmatch(r"[-+]?\d+", text):
            return int(text)
        if re.fullmatch(r"[-+]?(\d+\.\d*|\d*\.\d+)([eE][-+]?\d+)?", text):
            return float(text)
    except ValueError:
        pass
    return text


def read_metadata_yaml(path: str | Path | None) -> Dict[str, Any]:
    if not path:
        return {}
    yaml_path = Path(path)
    if not yaml_path.exists():
        return {}

    data: Dict[str, Any] = {}
    for line in yaml_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key:
            data[key] = parse_scalar(value)
    return _migrate_legacy_keys(data)


def _migrate_legacy_keys(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill current field names from older sidecar YAML key spellings."""
    migrated = dict(raw)
    for new_key, old_keys in LEGACY_KEY_ALIASES.items():
        if migrated.get(new_key) not in (None, ""):
            continue
        for old_key in old_keys:
            value = raw.get(old_key)
            if value not in (None, ""):
                migrated[new_key] = value
                break
    if migrated.get("fibre_composition") in (None, ""):
        brand = str(raw.get("brand") or "").strip()
        fiber = str(raw.get("fiber") or "").strip()
        combined = " ".join(part for part in (brand, fiber) if part)
        if combined:
            migrated["fibre_composition"] = combined
    return migrated


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    if "\n" in text:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if not text or text.strip() != text or any(ch in text for ch in ":#{}[]&,"):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def write_metadata_yaml(path: str | Path, metadata: Dict[str, Any]) -> None:
    yaml_path = Path(path)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    keys = [key for key in FIELD_ORDER if key in metadata]
    keys.extend(sorted(key for key in metadata if key not in keys))
    lines = [f"{key}: {_yaml_scalar(metadata.get(key))}" for key in keys]
    yaml_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def find_sidecar_for_image(image_path: str | Path) -> Path | None:
    image = Path(image_path)
    for suffix in (".yaml", ".yml"):
        candidate = image.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def find_metadata_for_sample(root: Path, sample_id: str, source_image: Path) -> Path | None:
    search_paths = [
        root.parent / f"{sample_id}.yaml",
        root.parent / f"{sample_id}.yml",
        root.parent.parent / f"{sample_id}.yaml",
        root.parent.parent / f"{sample_id}.yml",
        root.parent.parent / "samples" / f"{sample_id}.yaml",
        root.parent.parent / "samples" / f"{sample_id}.yml",
        source_image.with_suffix(".yaml"),
        source_image.with_suffix(".yml"),
        root / f"{sample_id}.yaml",
        root / f"{sample_id}.yml",
    ]
    for candidate in search_paths:
        if candidate.exists():
            return candidate
    return None


def default_metadata_for_image(image_path: str | Path | None = None) -> Dict[str, Any]:
    image = Path(image_path) if image_path else None
    stem = image.stem if image else "sample"
    structure = "fuzzy / brushed" if "fuzzy" in stem.lower() else "plain / stockinette"
    return {
        "sample_id": sanitize_sample_id(stem),
        # Lattice gauge - populated by detection or manual entry.
        "needles_per_10cm": "",
        "rows_per_10cm": "",
        "measurement_state": "",
        "gauge_source": "",
        "axis_order": "needle / row",
        "confidence": "",
        # Identity.
        "yarn_ref": "",
        "tension_ref": "n/a",
        "yarn_tension": "n/a",
        "machine_ref": "Benchmark scan",
        "bed_setup": "single bed",
        "structure_ref": structure,
        # Optional / advanced.
        "brand": "",
        "preset": "",
        "wash_state": "unknown",
        "operator": "",
        "weighting_ref": 0.0,
        "weight_gsm": "",
        "dye_lot": "",
        "fibre_composition": "",
        "yarn_count": "",
        "thread_count": "1",
        "colour_ref": "",
        "notes": "",
    }


def merged_metadata(image_path: str | Path | None, sources: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    merged = default_metadata_for_image(image_path)
    for source in sources:
        for key, value in source.items():
            if value is not None:
                merged[key] = value
    if image_path:
        merged["sample_id"] = sanitize_sample_id(str(merged.get("sample_id") or ""), Path(image_path).stem)
    else:
        merged["sample_id"] = sanitize_sample_id(str(merged.get("sample_id") or "sample"))
    return merged


def _float_value(value: Any, default: float = 0.0) -> float:
    if value in ("", None):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _str_value(raw: Dict[str, Any], key: str, default: str = "") -> str:
    value = raw.get(key)
    return str(value) if value not in (None, "") else default


def sample_metadata_kwargs(raw: Dict[str, Any], sample_id: str, source_image_name: str) -> Dict[str, Any]:
    raw = _migrate_legacy_keys(raw)
    fallback_structure = "fuzzy / brushed" if "fuzzy" in sample_id.lower() else "plain / stockinette"
    return {
        "sample_id": sanitize_sample_id(str(raw.get("sample_id") or sample_id), sample_id),
        "source_image_name": source_image_name,
        "needles_per_10cm": _str_value(raw, "needles_per_10cm"),
        "rows_per_10cm": _str_value(raw, "rows_per_10cm"),
        "measurement_state": _str_value(raw, "measurement_state"),
        "gauge_source": _str_value(raw, "gauge_source"),
        "axis_order": _str_value(raw, "axis_order", "needle / row"),
        "confidence": _str_value(raw, "confidence"),
        "yarn_ref": _str_value(raw, "yarn_ref"),
        "tension_ref": _str_value(raw, "tension_ref", "n/a"),
        "yarn_tension": _str_value(raw, "yarn_tension", "n/a"),
        "machine_ref": _str_value(raw, "machine_ref", "Benchmark scan"),
        "bed_setup": _str_value(raw, "bed_setup", "single bed"),
        "structure_ref": _str_value(raw, "structure_ref", fallback_structure),
        "brand": _str_value(raw, "brand"),
        "preset": _str_value(raw, "preset"),
        "wash_state": _str_value(raw, "wash_state", "unknown"),
        "operator": _str_value(raw, "operator"),
        "weighting_ref": _float_value(raw.get("weighting_ref"), 0.0),
        "weight_gsm": _str_value(raw, "weight_gsm"),
        "dye_lot": _str_value(raw, "dye_lot"),
        "fibre_composition": _str_value(raw, "fibre_composition"),
        "yarn_count": _str_value(raw, "yarn_count"),
        "thread_count": _str_value(raw, "thread_count", "1"),
        "colour_ref": _str_value(raw, "colour_ref"),
        "notes": _str_value(raw, "notes"),
    }
