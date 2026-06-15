# Knit spacing analysis

## Input
- Image: SWA004_TITANWOOL02.png
- FFT size: 2048 × 2048
- DPI used: 599.999
- DPI source: metadata:dpi=(599.9988, 599.9988)

## Processing pipeline
- FFT: ImageJ-equivalent FHT power spectrum
- FD Math: conjugate multiply (self-correlation)
- Maxima detection: ImageJ-style MaximumFinder point-selection logic
- Prominence mode: lattice-detect:target_peak_count
- Prominence value: 7.664

## Peak detection
- Number of maxima: 10104
- FFT centre: (1024, 1024)
- Strongest peak: (999, 1062), value=190.0

## Lattice fit assessment
- Harmonics sufficient: False
- Reciprocal basis g1: [17.0, -7.0] px, angle=-22.38°
- Reciprocal basis g2: [4.0, 22.0] px, angle=79.695°
- Coverage: 18 / 157 (0.115)
- Mean residual: 1.0429 px
- Multiple support: g1=1, g2=1, mixed=16

## Derived spacings
- T1 ≈ |(112.08, -20.378)| ≈ 113.92 px
- T2 ≈ |(35.662, 86.607)| ≈ 93.66 px
- These are the real-space basis magnitudes from the 2D FFT lattice inversion, not axis-only N/Δ estimates.

## Global spacing
- Basis spacing 1: 113.92 px = 4.823 mm
- Basis spacing 2: 93.66 px = 3.965 mm
- Basis repeats 1 per 10 cm: 20.74
- Basis repeats 2 per 10 cm: 25.22
- Legacy axis-derived Tx reference: 49.95 px = 2.115 mm
- Legacy axis-derived Ty reference: 11.98 px = 0.507 mm

## Picks used
- Final assessor basis g1: [17.0, -7.0]
- Final assessor basis g2: [4.0, 22.0]
- Axis reference from FFT peak (983, 1024) with Δx=41
- Axis reference from FFT peak (1024, 853) with Δy=171
- Autocorrelation-space direct offsets retained for reference:
  - x shift: 41.00 px
  - y shift: 171.00 px

## Validity
- Overall valid: False
- Flags: none

## Notes
- The analysis path in this alternate entrypoint is delegated to the lattice-detect pipeline rather than the original in-file FFT/maxima/lattice implementation.
- Packaging, Markdown reporting, metadata embedding, and catalog TIFF bundling are retained from swatch_tester.
- The detector is hard-restricted to rectangular and oblique classes; square, centered-rectangular, and hexagonal fits are excluded.
- The preview uses a standardized square page and the detected grid is rendered with the same displayed-image scale as the original image panel.

