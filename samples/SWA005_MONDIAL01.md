# Knit spacing analysis

## Input
- Image: SWA005_MONDIAL01.png
- FFT size: 4096 × 4096
- DPI used: 599.999
- DPI source: metadata:dpi=(599.9988, 599.9988)

## Processing pipeline
- FFT: ImageJ-equivalent FHT power spectrum
- FD Math: conjugate multiply (self-correlation)
- Maxima detection: ImageJ-style MaximumFinder point-selection logic
- Prominence mode: lattice-detect:target_peak_count
- Prominence value: 14.176

## Peak detection
- Number of maxima: 601
- FFT centre: (2048, 2048)
- Strongest peak: (1928, 2053), value=185.0

## Lattice fit assessment
- Harmonics sufficient: True
- Reciprocal basis g1: [1.0, 46.0] px, angle=88.755°
- Reciprocal basis g2: [-60.019, 1.305] px, angle=178.755°
- Coverage: 6 / 10 (0.600)
- Mean residual: 0.9437 px
- Multiple support: g1=2, g2=1, mixed=3

## Derived spacings
- T1 ≈ |(1.935, 89.001)| ≈ 89.02 px
- T2 ≈ |(-68.213, 1.483)| ≈ 68.23 px
- These are the real-space basis magnitudes from the 2D FFT lattice inversion, not axis-only N/Δ estimates.

## Global spacing
- Basis spacing 1: 89.02 px = 3.769 mm
- Basis spacing 2: 68.23 px = 2.888 mm
- Basis repeats 1 per 10 cm: 26.54
- Basis repeats 2 per 10 cm: 34.62
- Legacy axis-derived Tx reference: 7.21 px = 0.305 mm

## Picks used
- Final assessor basis g1: [1.0, 46.0]
- Final assessor basis g2: [-60.019, 1.305]
- Axis reference from FFT peak (2616, 2048) with Δx=568
- Autocorrelation-space direct offsets retained for reference:
  - x shift: 568.00 px

## Validity
- Overall valid: True
- Flags: none

## Notes
- The analysis path in this alternate entrypoint is delegated to the lattice-detect pipeline rather than the original in-file FFT/maxima/lattice implementation.
- Packaging, Markdown reporting, metadata embedding, and catalog TIFF bundling are retained from swatch_tester.
- The detector is hard-restricted to rectangular and oblique classes; square, centered-rectangular, and hexagonal fits are excluded.
- The preview uses a standardized square page and the detected grid is rendered with the same displayed-image scale as the original image panel.

