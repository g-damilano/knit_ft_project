# Knit spacing analysis

## Input
- Image: SWA002_MONDIAL01.tif
- FFT size: 2048 × 2048
- DPI used: 599.999
- DPI source: embedded_payload:dpi_exact

## Processing pipeline
- FFT: ImageJ-equivalent FHT power spectrum
- FD Math: conjugate multiply (self-correlation)
- Maxima detection: ImageJ-style MaximumFinder point-selection logic
- Prominence mode: auto:rapid:range
- Prominence value: 27.309

## Peak detection
- Number of maxima: 17
- FFT centre: (1024, 1024)
- Strongest peak: (1024, 1024), value=254.0

## Lattice fit assessment
- Harmonics sufficient: True
- Reciprocal basis g1: [33.518, 1.147] px, angle=1.96°
- Reciprocal basis g2: [4.518, 49.07] px, angle=84.739°
- Coverage: 14 / 14 (1.000)
- Mean residual: 0.3670 px
- Multiple support: g1=4, g2=0, mixed=6

## Derived spacings
- T1 ≈ |(61.295, -5.644)| ≈ 61.55 px
- T2 ≈ |(-1.433, 41.868)| ≈ 41.89 px
- These are the real-space basis magnitudes from the 2D FFT lattice inversion, not axis-only N/Δ estimates.

## Global spacing
- Basis spacing 1: 61.55 px = 2.606 mm
- Basis spacing 2: 41.89 px = 1.773 mm
- Basis repeats 1 per 10 cm: 38.38
- Basis repeats 2 per 10 cm: 56.39
- Legacy axis-derived Ty reference: 2.64 px = 0.112 mm

## Picks used
- Final assessor basis g1: [33.518, 1.147]
- Final assessor basis g2: [4.518, 49.07]
- Axis reference from FFT peak (1024, 248) with Δy=776
- Autocorrelation-space direct offsets retained for reference:
  - y shift: 776.00 px

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

