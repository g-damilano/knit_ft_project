# Knit spacing analysis

## Input
- Image: SWA001_LANG01.tif
- FFT size: 2048 × 2048
- DPI used: 599.999
- DPI source: embedded_payload:dpi_exact

## Processing pipeline
- FFT: ImageJ-equivalent FHT power spectrum
- FD Math: conjugate multiply (self-correlation)
- Maxima detection: ImageJ-style MaximumFinder point-selection logic
- Prominence mode: auto:rapid:range
- Prominence value: 21.100

## Peak detection
- Number of maxima: 15
- FFT centre: (1024, 1024)
- Strongest peak: (1024, 1024), value=254.0

## Lattice fit assessment
- Harmonics sufficient: True
- Reciprocal basis g1: [31.024, 0.195] px, angle=0.36°
- Reciprocal basis g2: [0.61, 40.405] px, angle=89.135°
- Coverage: 12 / 12 (1.000)
- Mean residual: 0.4344 px
- Multiple support: g1=2, g2=0, mixed=6

## Derived spacings
- T1 ≈ |(66.019, -0.997)| ≈ 66.03 px
- T2 ≈ |(-0.319, 50.692)| ≈ 50.69 px
- These are the real-space basis magnitudes from the 2D FFT lattice inversion, not axis-only N/Δ estimates.

## Global spacing
- Basis spacing 1: 66.03 px = 2.795 mm
- Basis spacing 2: 50.69 px = 2.146 mm
- Basis repeats 1 per 10 cm: 35.78
- Basis repeats 2 per 10 cm: 46.60
- Legacy axis-derived Tx reference: 66.06 px = 2.797 mm
- Legacy axis-derived Ty reference: 51.20 px = 2.167 mm

## Picks used
- Final assessor basis g1: [31.024, 0.195]
- Final assessor basis g2: [0.61, 40.405]
- Axis reference from FFT peak (993, 1024) with Δx=31
- Axis reference from FFT peak (1024, 984) with Δy=40
- Autocorrelation-space direct offsets retained for reference:
  - x shift: 31.00 px
  - y shift: 40.00 px

## Validity
- Overall valid: True
- Flags: none

## Notes
- FFT input follows ImageJ FFT.newFHT(): RGB uses HSB brightness, grayscale passes through.
- Padding follows ImageJ FFT.pad(): top-left insert into square next power-of-two canvas filled with image mean.
- Power spectrum follows FHT.getPowerSpectrum() log scaling and quadrant swap.
- Correlate follows FFTMath -> FHT.conjugateMultiply() -> inverseTransform() -> swapQuadrants().
- Maxima detection now follows ImageJ MaximumFinder logic for POINT_SELECTION much more closely: local-max prepass, value-sorted traversal, tolerance flood, equal-height center selection, strict and edge handling.
- Only the safe part of maxima detection is accelerated: the initial 8-neighbor local-max scan is vectorized. The order-dependent flood/merge step remains serial to preserve ImageJ behavior.
- Cross-image batching can still be parallelized with --workers without changing single-image results.
- Peak-geometry analysis is appended after maxima detection, retaining axis-aligned FFT/autocorrelation interpretations for reference.
- The final validity and spacing report are driven by the 2-vector lattice assessor when a stable lattice fit is available.

