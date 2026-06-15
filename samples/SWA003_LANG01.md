# Knit spacing analysis

## Input
- Image: SWA003_LANG01.tif
- FFT size: 4096 × 4096
- DPI used: 599.999
- DPI source: embedded_payload:dpi_exact

## Processing pipeline
- FFT: ImageJ-equivalent FHT power spectrum
- FD Math: conjugate multiply (self-correlation)
- Maxima detection: ImageJ-style MaximumFinder point-selection logic
- Prominence mode: auto:rapid:range
- Prominence value: 21.100

## Peak detection
- Number of maxima: 17
- FFT centre: (2048, 2048)
- Strongest peak: (2048, 2048), value=254.0

## Lattice fit assessment
- Harmonics sufficient: True
- Reciprocal basis g1: [58.852, 0.254] px, angle=0.247°
- Reciprocal basis g2: [-4.925, 80.881] px, angle=93.484°
- Coverage: 14 / 14 (1.000)
- Mean residual: 0.7792 px
- Multiple support: g1=4, g2=0, mixed=6

## Derived spacings
- T1 ≈ |(69.58, 4.237)| ≈ 69.71 px
- T2 ≈ |(-0.218, 50.629)| ≈ 50.63 px
- These are the real-space basis magnitudes from the 2D FFT lattice inversion, not axis-only N/Δ estimates.

## Global spacing
- Basis spacing 1: 69.71 px = 2.951 mm
- Basis spacing 2: 50.63 px = 2.143 mm
- Basis repeats 1 per 10 cm: 33.89
- Basis repeats 2 per 10 cm: 46.66
- Legacy axis-derived Tx reference: 69.42 px = 2.939 mm

## Picks used
- Final assessor basis g1: [58.852, 0.254]
- Final assessor basis g2: [-4.925, 80.881]
- Axis reference from FFT peak (1989, 2048) with Δx=59
- Autocorrelation-space direct offsets retained for reference:
  - x shift: 59.00 px

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

