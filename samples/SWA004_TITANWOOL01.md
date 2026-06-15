# Knit spacing analysis

## Input
- Image: SWA004_TITANWOOL01.png
- FFT size: 4096 × 4096
- DPI used: 599.999
- DPI source: metadata:dpi=(599.9988, 599.9988)

## Processing pipeline
- FFT: ImageJ-equivalent FHT power spectrum
- FD Math: conjugate multiply (self-correlation)
- Maxima detection: ImageJ-style MaximumFinder point-selection logic
- Prominence mode: auto:rapid:range
- Prominence value: 21.100

## Peak detection
- Number of maxima: 31
- FFT centre: (2048, 2048)
- Strongest peak: (2048, 2048), value=254.0

## Lattice fit assessment
- Harmonics sufficient: False
- Reciprocal basis g1: [58.0, 0.0] px, angle=0.0°
- Reciprocal basis g2: [0.0, 58.0] px, angle=90.0°
- Coverage: 2 / 2 (1.000)
- Mean residual: 0.5000 px
- Multiple support: g1=0, g2=0, mixed=0

## Derived spacings
- T1 ≈ |(70.621, -0.0)| ≈ 70.62 px
- T2 ≈ |(0.0, 70.621)| ≈ 70.62 px
- These are the real-space basis magnitudes from the 2D FFT lattice inversion, not axis-only N/Δ estimates.

## Global spacing
- Basis spacing 1: 70.62 px = 2.990 mm
- Basis spacing 2: 70.62 px = 2.990 mm
- Basis repeats 1 per 10 cm: 33.45
- Basis repeats 2 per 10 cm: 33.45
- Legacy axis-derived Tx reference: 70.62 px = 2.990 mm

## Picks used
- Final assessor basis g1: [58.0, 0.0]
- Final assessor basis g2: [0.0, 58.0]
- Axis reference from FFT peak (2106, 2048) with Δx=58
- Autocorrelation-space direct offsets retained for reference:
  - x shift: 58.00 px

## Validity
- Overall valid: False
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

