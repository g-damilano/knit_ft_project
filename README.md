# Knit HOG + FFT stitch spacing estimator

This project estimates knit spacing from an image of a knitted fabric, including images that are not well aligned. It uses a HOG-style dominant-orientation analysis to align the knit structure before applying FFT and autocorrelation to estimate:

- wale spacing
- course spacing
- wale and course size in mm
- wale and course count per 10 cm
- local-window variance statistics

It also produces:

- an annotated diagnostic PNG
- a homonymous Markdown report next to the input image

## Method summary

1. Read the image in grayscale.
2. Estimate the dominant structural direction using a HOG-style histogram of oriented gradients.
3. Use HOG to propose dominant structural directions, then choose the rotation that maximises axis-aligned FFT energy.
4. Estimate wale and course spacing with FFT.
5. Refine the spacing with 1D autocorrelation.
6. Repeat the measurement on overlapping local windows to quantify variance.
7. Write a Markdown report with the results.

## Files

- `knit_hog_fft.py` — main script
- `requirements.txt` — Python dependencies
- `pyproject.toml` — project metadata
- `myproject/__init__.py` — package marker

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

```bash
python knit_hog_fft.py path/to/image.png --dpi 600
```

Optional arguments:

```bash
python knit_hog_fft.py path/to/image.png \
  --dpi 600 \
  --min-spacing-px 8 \
  --max-spacing-px 200 \
  --crop-frac 0.8
```

You can also override the output prefix for the diagnostic PNG:

```bash
python knit_hog_fft.py path/to/image.png --dpi 600 --out-prefix results/sample01
```

## Outputs

Given an input image:

```text
sample.png
```

the script writes:

```text
sample.md
sample_diagnostic.png
```

The Markdown report is homonymous with the input image.

## Notes and limitations

- The mm conversion depends on the DPI you provide. If the effective image scale is wrong, the mm values will also be wrong.
- The method is robust to rotation, but not fully to strong perspective distortion.
- The variance is computed from repeated local window measurements, not from FFT bins.
- For heavily distorted specimens, perspective correction or local orientation fields would be the next upgrade.

## Example

```bash
python knit_hog_fft.py /mnt/data/34x29.png --dpi 600
```

## License

Use and adapt as needed for your own work.
