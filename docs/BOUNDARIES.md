# Architecture Boundaries

The package keeps analysis, adaptation, delivery, interface, and production
concerns separate.

## Analysis Layer

`analysis/knit_grid_literature_guided_v13.py` is the v13 grid detector. It
produces diagnostic images, overlays, and CSV reports:

- `v13_grid_summary.csv`
- `v13_period_candidates.csv`
- `v13_quality_report.csv`

Delivery code must not import or call analysis functions.

## Adapter Boundary

`adapter/v13_adapter.py` is the only layer allowed to understand the v13 output
folder structure. It reads files, CSV rows, and optional sidecar YAML metadata.
It does not import the v13 script.

## Delivery Layer

`delivery/` receives immutable `CatalogRecord` objects and can only:

- render cover pages
- write multipage TIFF files
- write JSON metadata
- compose batch covers

It must not estimate grids, filter images, detect periods, call OpenCV, or run
subprocesses.

## Interface Layer

`interface/dropbox_gui.py` owns image/YAML loading, metadata editing,
subprocess launch, and status UI. It invokes analysis and delivery as separate
subprocesses.

## Production Layer

`production/launcher.py` is the executable entry point. It exposes hidden
subprocess modes for frozen builds:

- `--run-v13`
- `--run-delivery`

This preserves the same analysis/delivery boundary inside the executable.

## Guardrail

`guardrails.py` performs a static keyword/import audit and is called by the CLI
unless explicitly disabled.
