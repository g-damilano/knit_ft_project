# Knit spacing analysis

## Input
- Image: SWA001_LANG02.tiff
- FFT size: 4096 × 4096
- DPI used: 600.000
- DPI source: embedded_payload:dpi_exact

## Processing pipeline
- FFT: ImageJ-equivalent FHT power spectrum
- FD Math: conjugate multiply (self-correlation)
- Maxima detection: ImageJ-style MaximumFinder point-selection logic
- Prominence mode: auto:rapid:range
- Prominence value: 24.261

## Peak detection
- Number of maxima: 15
- FFT centre: (2048, 2048)
- Strongest peak: (2048, 2048), value=254.0

## Lattice fit assessment
- Harmonics sufficient: True
- Reciprocal basis g1: [47.849, 2.462] px, angle=2.945°
- Reciprocal basis g2: [-3.136, 84.273] px, angle=92.131°
- Coverage: 8 / 10 (0.800)
- Mean residual: 2.1422 px
- Multiple support: g1=2, g2=0, mixed=2

## Derived spacings
- T1 ≈ |(85.439, 3.18)| ≈ 85.50 px
- T2 ≈ |(-2.496, 48.511)| ≈ 48.58 px
- These are the real-space basis magnitudes from the 2D FFT lattice inversion, not axis-only N/Δ estimates.

## Global spacing
- Basis spacing 1: 85.50 px = 3.619 mm
- Basis spacing 2: 48.58 px = 2.056 mm
- Basis repeats 1 per 10 cm: 27.63
- Basis repeats 2 per 10 cm: 48.63
- Legacy axis-derived Tx reference: 87.15 px = 3.689 mm
- Legacy axis-derived Ty reference: 7.20 px = 0.305 mm

## Picks used
- Final assessor basis g1: [47.849, 2.462]
- Final assessor basis g2: [-3.136, 84.273]
- Axis reference from FFT peak (2001, 2048) with Δx=47
- Axis reference from FFT peak (2048, 1479) with Δy=569
- Autocorrelation-space direct offsets retained for reference:
  - x shift: 47.00 px
  - y shift: 569.00 px

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

