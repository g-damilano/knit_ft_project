# Knit spacing analysis

## Input
- Image: SWA004_TITANWOOL03.png
- FFT size: 2048 × 2048
- DPI used: 599.999
- DPI source: metadata:dpi=(599.9988, 599.9988)

## Processing pipeline
- FFT: ImageJ-equivalent FHT power spectrum
- FD Math: conjugate multiply (self-correlation)
- Maxima detection: ImageJ-style MaximumFinder point-selection logic
- Prominence mode: auto:rapid:range
- Prominence value: 24.342

## Peak detection
- Number of maxima: 19
- FFT centre: (1024, 1024)
- Strongest peak: (1024, 1024), value=254.0

## Lattice fit assessment
- Harmonics sufficient: True
- Reciprocal basis g1: [33.0, 3.0] px, angle=5.194°
- Reciprocal basis g2: [26.0, -57.0] px, angle=-65.48°
- Coverage: 8 / 8 (1.000)
- Mean residual: 0.5000 px
- Multiple support: g1=2, g2=0, mixed=2

## Derived spacings
- T1 ≈ |(59.59, 27.181)| ≈ 65.50 px
- T2 ≈ |(3.136, -34.499)| ≈ 34.64 px
- These are the real-space basis magnitudes from the 2D FFT lattice inversion, not axis-only N/Δ estimates.

## Global spacing
- Basis spacing 1: 65.50 px = 2.773 mm
- Basis spacing 2: 34.64 px = 1.466 mm
- Basis repeats 1 per 10 cm: 36.07
- Basis repeats 2 per 10 cm: 68.19

## Picks used
- Final assessor basis g1: [33.0, 3.0]
- Final assessor basis g2: [26.0, -57.0]

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

