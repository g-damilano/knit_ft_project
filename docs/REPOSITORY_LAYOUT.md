# Repository Layout

This repository now has one publishable identity: the Knit Grid Catalog
Delivery application.

- `src/knit_grid_catalog_delivery_v14/` - current maintained Python package.
- `samples/` - retained sample/product swatch images, notes, and YAML sidecars.
- `docs/` - architecture notes, audit notes, and design handoff material.
- `dist/` - generated executable output, ignored by Git.
- `build/` and `build_specs/` - PyInstaller working folders, ignored by Git.
- `outputs/` - local analysis/delivery runs, ignored by Git.

The old `swatch/` nesting, repository-level archives, diagnostic outputs, zip
bundles, and the separate detector strand are not part of the publication tree.

The package is internally split into:

- `analysis/`
- `adapter/`
- `delivery/`
- `interface/`
- `production/`
- `common/`

Root-level compatibility wrappers remain inside the package so older import
paths still resolve.
