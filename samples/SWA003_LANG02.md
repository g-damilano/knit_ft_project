# Knit spacing analysis

## Input
- Image: SWA003_LANG02.png
- FFT size: 8192 × 8192
- DPI used: 599.999
- DPI source: metadata:dpi=(599.9988, 599.9988)

## Processing pipeline
- FFT: ImageJ-equivalent FHT power spectrum
- FD Math: conjugate multiply (self-correlation)
- Maxima detection: ImageJ-style MaximumFinder point-selection logic
- Prominence mode: auto:rapid:range
- Prominence value: 34.272

## Peak detection
- Number of maxima: 15
- FFT centre: (4096, 4096)
- Strongest peak: (4096, 4096), value=254.0

## Lattice fit assessment
- Harmonics sufficient: False
- Coverage: 0 / 0 (0.000)
- Multiple support: g1=0, g2=0, mixed=0

## Derived spacings
- Tx ≈ 8192 / 1136 ≈ 7.21 px
- Ty: n/a

## Global spacing
- Wale spacing: 7.21 px = 0.305 mm
- Course spacing: n/a px
- Wales per 10 cm: 327.57

## Picks used
- Axis reference from FFT peak (2960, 4096) with Δx=1136
- Autocorrelation-space direct offsets retained for reference:
  - x shift: 1136.00 px

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

