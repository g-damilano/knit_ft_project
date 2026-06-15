# Knit spacing analysis

## Input
- Image: SWA004_TITANWOOL04.png
- FFT size: 512 × 512
- DPI used: 599.999
- DPI source: metadata:dpi=(599.9988, 599.9988)

## Processing pipeline
- FFT: ImageJ-equivalent FHT power spectrum
- FD Math: conjugate multiply (self-correlation)
- Maxima detection: ImageJ-style MaximumFinder point-selection logic
- Prominence mode: auto:rapid:range
- Prominence value: 31.638

## Peak detection
- Number of maxima: 19
- FFT centre: (256, 256)
- Strongest peak: (256, 256), value=254.0

## Lattice fit assessment
- Harmonics sufficient: True
- Reciprocal basis g1: [1.127, 33.002] px, angle=88.043°
- Reciprocal basis g2: [-37.594, 2.663] px, angle=175.949°
- Coverage: 14 / 14 (1.000)
- Mean residual: 0.7026 px
- Multiple support: g1=2, g2=2, mixed=8

## Derived spacings
- T1 ≈ |(5.555, 78.443)| ≈ 78.64 px
- T2 ≈ |(-68.859, 2.352)| ≈ 68.90 px
- These are the real-space basis magnitudes from the 2D FFT lattice inversion, not axis-only N/Δ estimates.

## Global spacing
- Basis spacing 1: 78.64 px = 3.329 mm
- Basis spacing 2: 68.90 px = 2.917 mm
- Basis repeats 1 per 10 cm: 30.04
- Basis repeats 2 per 10 cm: 34.28

## Picks used
- Final assessor basis g1: [1.127, 33.002]
- Final assessor basis g2: [-37.594, 2.663]

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
- Optional analysis resizing was used: FFT/maxima ran on a smaller image, and real-space spacings were scaled back to source-image pixels.

## Analysis scale

- Source size: [2595, 1930]
- Analysis size: [512, 381]
- Resized for analysis: True
- Spacing scale to source px: 5.068359375

## Base yarn colour estimate

- Median hex: #DCD6D6
- Median Lab: [85.9932, 2.1964, 0.5009]
- Median sRGB: [220, 214, 214]
- Used pixels: 514499 / sampled 556484
- ROI: {'type': 'full_image'}

## Visual lattice artifacts

- lattice_overlay: `C:\Users\giaco\Documents\GitHub\KnitProj\workstation\swatch\SWA004_TITANWOOL04_lattice_overlay.png`
- fft_lattice_overlay: `C:\Users\giaco\Documents\GitHub\KnitProj\workstation\swatch\SWA004_TITANWOOL04_fft_lattice_overlay.png`
- lattice_rectified: `C:\Users\giaco\Documents\GitHub\KnitProj\workstation\swatch\SWA004_TITANWOOL04_lattice_rectified.png`
