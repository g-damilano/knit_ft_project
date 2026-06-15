
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List


FORBIDDEN_TOKENS = {
    "delivery/cover_renderer.py": [
        "knit_grid_literature_guided_v13",
        "build_consensus_response",
        "def luminance_flatfield",
        "import cv2",
        "def dog_dark",
        "cv2",
        "subprocess",
    ],
    "delivery/tiff_writer.py": [
        "knit_grid_literature_guided_v13",
        "build_consensus_response",
        "def luminance_flatfield",
        "import cv2",
        "def dog_dark",
        "cv2",
        "subprocess",
    ],
    "delivery/catalog_delivery.py": [
        "knit_grid_literature_guided_v13",
        "build_consensus_response",
        "def luminance_flatfield",
        "import cv2",
        "def dog_dark",
        "cv2",
        "subprocess",
    ],
    "adapter/v13_adapter.py": [
        "knit_grid_literature_guided_v13",
        "build_consensus_response",
        "def luminance_flatfield",
        "import cv2",
        "def dog_dark",
        "cv2",
        "subprocess",
    ],
}


def audit_project_boundaries(package_dir: str | Path) -> Dict[str, List[str]]:
    """
    Static import/keyword audit for the china-wall boundary.

    It is intentionally simple and strict. The delivery layer may read existing
    images and CSVs, render covers, and write TIFFs. It must not import or call
    the analysis pipeline.
    """
    package_dir = Path(package_dir)
    failures: Dict[str, List[str]] = {}

    for filename, forbidden in FORBIDDEN_TOKENS.items():
        path = package_dir / filename
        if not path.exists():
            failures.setdefault(filename, []).append("missing file")
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        hits = [token for token in forbidden if token in text]
        if hits:
            failures[filename] = hits

    return failures


def assert_project_boundaries(package_dir: str | Path) -> None:
    failures = audit_project_boundaries(package_dir)
    if failures:
        raise RuntimeError(f"Boundary audit failed: {failures}")
