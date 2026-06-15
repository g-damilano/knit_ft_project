
from __future__ import annotations

from pathlib import Path
from typing import Iterable
from collections import Counter, defaultdict
import json
import re

from .contracts import CatalogBatch, CatalogRecord
from .cover_renderer import render_batch_cover, render_sample_cover
from .tiff_writer import write_layered_tiff


def _safe_filename_stem(value: str, fallback: str = "sample") -> str:
    clean = re.sub(r"\s+", "_", value.strip())
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", clean).strip("._-")
    return clean or fallback


def _output_stems(records: list[CatalogRecord]) -> dict[int, str]:
    """
    Prefer YAML/catalog sample IDs for output filenames.

    If multiple records intentionally or accidentally carry the same YAML
    sample_id, keep that sample_id in the filename and add a source-image suffix
    to avoid overwriting sibling outputs.
    """
    bases = [_safe_filename_stem(record.sample.sample_id) for record in records]
    counts = Counter(bases)
    used: set[str] = set()
    seen: defaultdict[str, int] = defaultdict(int)
    stems: dict[int, str] = {}

    for index, record in enumerate(records):
        base = bases[index]
        if base not in used:
            stem = base
        else:
            seen[base] += 1
            source_stem = _safe_filename_stem(Path(record.source_image_path).stem, f"{seen[base]:02d}")
            if source_stem == base:
                source_stem = f"{seen[base]:02d}"
            stem = f"{base}__{source_stem}"
            while stem in used:
                seen[base] += 1
                stem = f"{base}__{seen[base]:02d}"
        used.add(stem)
        stems[index] = stem

    return stems


def write_catalog_from_records(records: Iterable[CatalogRecord], out_dir: str | Path, title: str = "Bottom box refinement - right-strip cover") -> CatalogBatch:
    """
    Delivery orchestration only.

    This function accepts immutable CatalogRecord objects. It does not know how
    they were computed and performs no image analysis.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tiff_dir = out / "layered_tiff"
    json_dir = out / "metadata_json"
    cover_dir = out / "cover"
    sample_cover_dir = cover_dir / "sample_covers"
    for directory in (tiff_dir, json_dir, cover_dir, sample_cover_dir):
        directory.mkdir(exist_ok=True)

    records = list(records)
    batch = CatalogBatch(records=records, title=title)
    output_stems = _output_stems(records)

    for index, record in enumerate(records):
        output_stem = output_stems[index]
        sample_cover_path = sample_cover_dir / f"{output_stem}_cover.png"
        render_sample_cover(record).save(sample_cover_path)
        write_layered_tiff(
            record,
            tiff_dir / f"{output_stem}_catalog_layers.tiff",
            cover_page_path=sample_cover_path,
        )
        (json_dir / f"{output_stem}_metadata.json").write_text(record.metadata_json(indent=2), encoding="utf-8")

    cover = render_batch_cover(batch)
    cover.save(cover_dir / "composed_catalog_cover.png")
    (out / "batch_metadata.json").write_text(json.dumps(batch.payload(), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "ALIGNMENT_NOTE.txt").write_text(
        "Alignment status: ALIGNED\n"
        "Rule enforced: TIFF layer 0/page 0 uses the exact engineered sample "
        "cover exported to cover/sample_covers/<sample>_cover.png.\n"
        "The TIFF writer does not render or improvise an independent cover.\n",
        encoding="utf-8",
    )

    return batch
