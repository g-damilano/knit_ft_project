# Knit Grid Catalog Delivery

Knit Grid Catalog Delivery is a local desktop workflow for turning knit swatch
images and sidecar metadata into catalog-ready assets.

The maintained application is now the root project:

- `src/knit_grid_catalog_delivery_v14/` contains the Python package.
- `samples/` contains the retained sample/product swatch images and YAML notes.
- `docs/` contains architecture notes, audit notes, and design handoff material.
- `dist/`, `build/`, `outputs/`, archives, zips, and diagnostics are generated
  locally and ignored for GitHub publication.

The older detector strand and bulky diagnostic output have been removed from
the publishable tree. The package name keeps the `v14` suffix for import and
launcher compatibility.

## What The App Does

The GUI lets an operator:

- load one or more swatch images
- auto-load or edit matching `.yaml` metadata sidecars
- run the v13 grid analysis
- render the v14 catalog cover with right-strip grid overlay
- export cover PNGs, layered TIFFs, and JSON metadata

The cover renderer preserves the image-reactive color concept: the bottom box
color is derived from the visible average color of the source image. The card
image crop and right-strip grid overlay share the same grid-referenced
transform, so swatches with different source sizes can still be presented at a
consistent visual stitch scale.

## Install For Development

Use Python 3.10 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate the environment again.

## Run The GUI

```powershell
python -m knit_grid_catalog_delivery_v14
```

or, after editable install:

```powershell
knit-grid-catalog
```

Typical workflow:

1. Click `Add images` and choose one or more swatch images.
2. If `image_name.yaml` exists beside an image, it is loaded automatically.
3. If no YAML is present, default metadata fields are shown for editing.
4. Optionally attach or save YAML metadata from the GUI.
5. Choose an output root.
6. Click `Run selected` or `Run all`.

The GUI creates a run folder for each sample. That folder keeps a copied source
image, copied YAML sidecar, v13 analysis output, and v14 delivery output. The
copy is intentional: it preserves source DPI/alpha information for physical
scale and reactive color rendering.

## Metadata YAML

Keep sidecar metadata beside the image when possible:

```text
SWA004_TITANWOOL01.png
SWA004_TITANWOOL01.yaml
```

Current fields include:

| Field | Use |
| --- | --- |
| `sample_id` | Output folder and catalog sample label. Keep it filesystem-safe. |
| `needles_per_10cm`, `rows_per_10cm` | Lattice gauge values from detection or manual entry. |
| `measurement_state`, `gauge_source`, `axis_order`, `confidence` | Traceability for the gauge measurement. |
| `yarn_ref`, `tension_ref`, `yarn_tension` | Yarn and knitting tension references. |
| `machine_ref`, `bed_setup`, `structure_ref` | Machine and swatch construction identity. |
| `wash_state`, `weighting_ref`, `weight_gsm` | Delivery labels and metadata. |
| `brand`, `preset`, `operator`, `notes` | Optional catalog traceability. |

The parser supports simple one-line scalar YAML values. Older sidecar keys such
as `machine`, `descriptor`, `tension`, `yarn_name`, and
`weight_per_needle_g` are migrated when loaded.

## Output Guide

After a successful GUI run, expect:

```text
<output root>\<sample_id>\
  <sample_id>.png
  <sample_id>.yaml
  analysis\
    v13\
      v13_grid_summary.csv
      v13_period_candidates.csv
      v13_quality_report.csv
      <sample_id>\
        01_raw.png
        08_wale_target_grid_overlay.png
        09_local_deviation_overlay.png
        ...
  delivery\
    catalog\
      cover\
        composed_catalog_cover.png
        sample_covers\<sample_id>_cover.png
      layered_tiff\<sample_id>_catalog_layers.tiff
      metadata_json\<sample_id>_metadata.json
      batch_metadata.json
```

Generated output is deliberately ignored by Git. Keep only selected source
samples and docs in the repository.

## CLI Workflow

Use the GUI when possible. To run delivery from existing v13 output:

```powershell
python -m knit_grid_catalog_delivery_v14.cli `
  --v13-output path\to\analysis\v13 `
  --out path\to\delivery\catalog
```

The adapter searches for the original source image and YAML beside the v13
folder parent and one level above it. This supports both compact CLI runs and
the GUI's `analysis/v13` layout.

## Build The Windows Executable

From the repository root:

```powershell
.\build_windows_exe.bat
```

The script uses the conda environment named `pyinstaller`. It installs
production requirements, installs this package in editable mode, then runs
PyInstaller.

Build output is written locally to:

```text
dist\KnitGridCatalogDelivery.exe
dist\README_DISTRIBUTION.txt
```

`dist/` and PyInstaller build folders are ignored. Publish source, docs, and
selected samples; distribute executable builds separately unless there is a
specific release reason to attach them.

## Repository Layout

```text
.
  README.md
  pyproject.toml
  requirements.txt
  requirements-production.txt
  build_windows_exe.bat
  src\
    knit_grid_catalog_delivery_v14\
      analysis\
      adapter\
      common\
      delivery\
      interface\
      production\
  samples\
  docs\
    BOUNDARIES.md
    REPOSITORY_LAYOUT.md
    design_handoff_knit_grid_inspector\
```

The package has separated rails:

- `analysis/` runs v13 image analysis and grid detection.
- `adapter/` reads existing v13 output and optional YAML metadata.
- `delivery/` renders covers, TIFFs, and metadata JSON.
- `interface/` owns the GUI and subprocess orchestration.
- `production/` owns executable launch/build entry points.
- `common/` contains shared metadata and gauge helpers.

Thin compatibility wrappers remain at the package root for older imports.

## Development Checks

Compile the package:

```powershell
python -m compileall -q src\knit_grid_catalog_delivery_v14
```

Run the static boundary audit through the CLI when you have v13 output
available:

```powershell
python -m knit_grid_catalog_delivery_v14.cli `
  --v13-output path\to\analysis\v13 `
  --out outputs\catalog_delivery_smoke
```

Check whether Numba acceleration is available:

```powershell
python -c "from knit_grid_catalog_delivery_v14.analysis.numba_accel import NUMBA_AVAILABLE; print(NUMBA_AVAILABLE)"
```

Compare against the fallback path:

```powershell
$env:KNIT_GRID_DISABLE_NUMBA = "1"
python -m knit_grid_catalog_delivery_v14.production.launcher --run-v13 ...
Remove-Item Env:KNIT_GRID_DISABLE_NUMBA
```

## Publication Notes

Before pushing:

1. Review sample images for ownership/privacy.
2. Add a license file if this repository will be public.
3. Use Git LFS if many large `.png`, `.tif`, or `.tiff` samples will be
   versioned long term.
4. Keep diagnostics, generated outputs, archives, zips, and executable build
   folders out of the main commit.
5. Check `git status --short` and confirm only current source, docs, metadata,
   and selected samples are staged.
