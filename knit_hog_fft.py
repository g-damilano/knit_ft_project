from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import cv2
import matplotlib.pyplot as plt
import numpy as np


# ============================================================
# Basic conversions
# ============================================================

def px_to_mm(px: float, dpi: float) -> float:
    return px * 25.4 / dpi


def mm_to_count_per_10cm(spacing_mm: float) -> float:
    if spacing_mm <= 0:
        return float("nan")
    return 100.0 / spacing_mm


# ============================================================
# Image I/O and preprocessing
# ============================================================

def load_grayscale(image_path: str) -> np.ndarray:
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    return img.astype(np.float32)


def normalize_image(img: np.ndarray) -> np.ndarray:
    out = img.astype(np.float32).copy()
    out -= out.mean()
    std = out.std()
    if std > 0:
        out /= std
    return out


def rotate_image_keep_bounds(img: np.ndarray, angle_deg: float) -> np.ndarray:
    """
    Rotate image by angle_deg (positive = CCW), expanding the canvas so the image is not cropped.
    """
    h, w = img.shape[:2]
    center = (w / 2.0, h / 2.0)

    M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    cos = abs(M[0, 0])
    sin = abs(M[0, 1])

    new_w = int(np.ceil((h * sin) + (w * cos)))
    new_h = int(np.ceil((h * cos) + (w * sin)))

    M[0, 2] += (new_w / 2.0) - center[0]
    M[1, 2] += (new_h / 2.0) - center[1]

    rotated = cv2.warpAffine(
        img,
        M,
        (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT,
    )
    return rotated


def center_crop_fraction(img: np.ndarray, frac: float = 0.8) -> np.ndarray:
    """
    Crop the central region to reduce edge artefacts introduced by rotation.
    """
    if not (0.1 <= frac <= 1.0):
        raise ValueError("frac must be between 0.1 and 1.0")

    h, w = img.shape
    ch = int(round(h * frac))
    cw = int(round(w * frac))
    y0 = (h - ch) // 2
    x0 = (w - cw) // 2
    return img[y0:y0 + ch, x0:x0 + cw]


# ============================================================
# HOG-style orientation estimation
# ============================================================

def compute_gradients(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns gx, gy, magnitude, orientation_deg.
    orientation_deg is the undirected gradient orientation in [0, 180).
    """
    gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    theta = np.rad2deg(np.arctan2(gy, gx))
    theta = np.mod(theta, 180.0)
    return gx, gy, mag, theta


def smooth_circular_hist(hist: np.ndarray, k: int = 9) -> np.ndarray:
    if k < 3:
        return hist.copy()
    if k % 2 == 0:
        k += 1

    kernel = np.ones(k, dtype=np.float32) / k
    pad = k // 2
    extended = np.concatenate([hist[-pad:], hist, hist[:pad]])
    smoothed = np.convolve(extended, kernel, mode="same")
    return smoothed[pad:-pad]


def estimate_knit_orientation_hog(
    img: np.ndarray,
    num_bins: int = 180,
    grad_percentile_thresh: float = 60.0,
) -> dict[str, Any]:
    """
    Estimate dominant structural direction using a HOG-style histogram of gradient orientations.

    Gradient directions are perpendicular to ridge directions. The returned ridge orientation is
    therefore grad_peak + 90 deg (wrapped to [0, 180)).
    """
    gx, gy, mag, theta = compute_gradients(img)

    mag_flat = mag.ravel()
    theta_flat = theta.ravel()

    thresh = np.percentile(mag_flat, grad_percentile_thresh)
    keep = mag_flat >= thresh

    mag_sel = mag_flat[keep]
    theta_sel = theta_flat[keep]

    if mag_sel.size < 100:
        raise RuntimeError("Too few strong-gradient pixels for reliable orientation estimation")

    bin_edges = np.linspace(0.0, 180.0, num_bins + 1)
    hist, _ = np.histogram(theta_sel, bins=bin_edges, weights=mag_sel)
    hist = hist.astype(np.float32)
    hist_smooth = smooth_circular_hist(hist, k=11)

    peak_idx = int(np.argmax(hist_smooth))
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    grad_peak_deg = float(bin_centers[peak_idx])
    ridge_peak_deg = (grad_peak_deg + 90.0) % 180.0

    return {
        "gx": gx,
        "gy": gy,
        "mag": mag,
        "theta_deg": theta,
        "hist": hist,
        "hist_smooth": hist_smooth,
        "bin_centers_deg": bin_centers,
        "grad_peak_deg": grad_peak_deg,
        "ridge_peak_deg": ridge_peak_deg,
        "threshold": float(thresh),
    }


def choose_rotation_to_vertical(ridge_angle_deg: float) -> float:
    """
    Choose the smallest rotation that makes the supplied ridge direction vertical (90 deg).
    """
    target = 90.0
    delta = target - ridge_angle_deg
    delta = (delta + 90.0) % 180.0 - 90.0
    return float(delta)


def dominant_hist_peaks(hist_smooth: np.ndarray, bin_centers_deg: np.ndarray, top_k: int = 4) -> list[float]:
    order = np.argsort(hist_smooth)[::-1]
    peaks: list[float] = []
    min_sep = 12.0
    for idx in order:
        angle = float(bin_centers_deg[idx])
        if all(min(abs(angle - p), 180.0 - abs(angle - p)) >= min_sep for p in peaks):
            peaks.append(angle)
        if len(peaks) >= top_k:
            break
    return peaks


def fft_axis_energy_score(mag: np.ndarray, axis_halfwidth_px: int = 6, suppress_dc_px: int = 12) -> float:
    """
    Score how strongly the FFT energy concentrates along the central horizontal and vertical axes.
    Higher is better for an already aligned grid.
    """
    h, w = mag.shape
    cy, cx = h // 2, w // 2

    band_x = mag[max(0, cy - axis_halfwidth_px):min(h, cy + axis_halfwidth_px + 1), :].copy()
    band_y = mag[:, max(0, cx - axis_halfwidth_px):min(w, cx + axis_halfwidth_px + 1)].copy()

    band_x[:, max(0, cx - suppress_dc_px):min(w, cx + suppress_dc_px + 1)] = 0
    band_y[max(0, cy - suppress_dc_px):min(h, cy + suppress_dc_px + 1), :] = 0

    total = float(np.sum(mag))
    if total <= 0:
        return float("-inf")
    return float((np.sum(band_x) + np.sum(band_y)) / total)


def choose_best_rotation_from_hog(
    img_raw: np.ndarray,
    orient: dict[str, Any],
    crop_frac: float,
) -> tuple[float, list[dict[str, float]]]:
    """
    Use HOG to propose candidate orientations, then choose the rotation that produces the most
    axis-aligned FFT energy concentration.
    """
    grad_peaks = dominant_hist_peaks(orient["hist_smooth"], orient["bin_centers_deg"], top_k=4)
    ridge_peaks = [((g + 90.0) % 180.0) for g in grad_peaks]

    candidates = []
    for ridge in ridge_peaks:
        for structural_angle in (ridge, (ridge + 90.0) % 180.0):
            rot = choose_rotation_to_vertical(structural_angle)
            img_rot = rotate_image_keep_bounds(img_raw, rot)
            img_rot_crop = center_crop_fraction(img_rot, frac=crop_frac)
            _, mag = compute_fft_magnitude(normalize_image(img_rot_crop))
            score = fft_axis_energy_score(mag)
            candidates.append({
                "rotation_deg": float(rot),
                "structural_angle_deg": float(structural_angle),
                "score": float(score),
            })

    best = max(candidates, key=lambda d: d["score"])
    return float(best["rotation_deg"]), candidates


# ============================================================
# FFT analysis
# ============================================================

def compute_fft_magnitude(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    f = np.fft.fft2(img)
    fshift = np.fft.fftshift(f)
    mag = np.log1p(np.abs(fshift))
    return fshift, mag


def smooth_1d(signal: np.ndarray, k: int = 9) -> np.ndarray:
    k = max(3, int(k))
    if k % 2 == 0:
        k += 1
    kernel = np.ones(k, dtype=np.float32) / k
    return np.convolve(signal, kernel, mode="same")


def estimate_period_from_fft_axis(
    mag: np.ndarray,
    axis: str,
    min_spacing_px: float = 8.0,
    max_spacing_px: float | None = None,
    band_halfwidth_px: int = 30,
    suppress_dc_px: int = 10,
) -> dict[str, Any]:
    """
    axis='x' -> repetition across x -> suitable for wale spacing after alignment
    axis='y' -> repetition across y -> suitable for course spacing after alignment
    """
    h, w = mag.shape
    cy, cx = h // 2, w // 2

    if axis == "x":
        y0 = max(0, cy - band_halfwidth_px)
        y1 = min(h, cy + band_halfwidth_px + 1)
        profile = mag[y0:y1, :].mean(axis=0)
        center = cx
        n = w
    elif axis == "y":
        x0 = max(0, cx - band_halfwidth_px)
        x1 = min(w, cx + band_halfwidth_px + 1)
        profile = mag[:, x0:x1].mean(axis=1)
        center = cy
        n = h
    else:
        raise ValueError("axis must be 'x' or 'y'")

    profile = smooth_1d(profile, k=11)

    lo_dc = max(0, center - suppress_dc_px)
    hi_dc = min(n, center + suppress_dc_px + 1)
    profile[lo_dc:hi_dc] = profile.min()

    if max_spacing_px is None:
        max_spacing_px = n / 2.0

    min_k = max(1, int(np.floor(n / max_spacing_px)))
    max_k = max(1, int(np.ceil(n / min_spacing_px)))

    start = center + min_k
    stop = min(n, center + max_k + 1)
    if start >= stop:
        raise ValueError("Invalid spacing bounds for FFT search")

    segment = profile[start:stop]
    peak_rel = int(np.argmax(segment))
    peak_idx = start + peak_rel

    k = abs(peak_idx - center)
    if k == 0:
        raise RuntimeError("FFT peak collapsed into the DC component unexpectedly")

    period_px = n / k

    return {
        "axis": axis,
        "profile": profile,
        "center": center,
        "peak_idx": peak_idx,
        "freq_offset_px": int(k),
        "period_px": float(period_px),
        "n": int(n),
    }


# ============================================================
# Autocorrelation refinement
# ============================================================

def autocorrelation_1d(signal: np.ndarray) -> np.ndarray:
    signal = signal.astype(np.float32)
    signal -= signal.mean()
    corr = np.correlate(signal, signal, mode="full")
    corr = corr[corr.size // 2 :]
    if corr[0] != 0:
        corr = corr / corr[0]
    return corr


def refine_period_with_autocorr(
    img: np.ndarray,
    initial_period_px: float,
    direction: str,
    search_halfwidth_px: int = 12,
) -> dict[str, Any]:
    """
    direction='x': average rows and autocorrelate along x
    direction='y': average cols and autocorrelate along y
    """
    h, w = img.shape

    if direction == "x":
        profile = img.mean(axis=0)
        n = w
    elif direction == "y":
        profile = img.mean(axis=1)
        n = h
    else:
        raise ValueError("direction must be 'x' or 'y'")

    profile = smooth_1d(profile, k=5)
    ac = autocorrelation_1d(profile)

    guess = int(round(initial_period_px))
    lo = max(1, guess - search_halfwidth_px)
    hi = min(n - 1, guess + search_halfwidth_px + 1)

    if lo >= hi:
        peak_idx = guess
        refined = float(initial_period_px)
    else:
        peak_idx = lo + int(np.argmax(ac[lo:hi]))
        refined = float(peak_idx)

    return {
        "direction": direction,
        "profile": profile,
        "autocorr": ac,
        "peak_idx": int(peak_idx),
        "period_px": refined,
    }


# ============================================================
# Local-window statistics for variance reporting
# ============================================================

def summarize_values(values: list[float]) -> dict[str, Any]:
    arr = np.asarray(values, dtype=np.float32)
    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return {
            "n": 0,
            "mean": float("nan"),
            "median": float("nan"),
            "std": float("nan"),
            "cv": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
        }

    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0

    return {
        "n": int(arr.size),
        "mean": mean,
        "median": float(np.median(arr)),
        "std": std,
        "cv": float(std / mean) if mean > 0 else float("nan"),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def analyze_windows(
    img_aligned: np.ndarray,
    min_spacing_px: float,
    max_spacing_px: float,
    window_frac: float = 0.35,
    stride_frac: float = 0.5,
) -> dict[str, Any]:
    """
    Compute local spacing estimates across overlapping windows to quantify variance.
    """
    h, w = img_aligned.shape
    wh = max(128, int(h * window_frac))
    ww = max(128, int(w * window_frac))
    sy = max(32, int(wh * stride_frac))
    sx = max(32, int(ww * stride_frac))

    wale_vals: list[float] = []
    course_vals: list[float] = []

    y_positions = list(range(0, max(1, h - wh + 1), sy))
    x_positions = list(range(0, max(1, w - ww + 1), sx))
    if (h - wh) not in y_positions:
        y_positions.append(max(0, h - wh))
    if (w - ww) not in x_positions:
        x_positions.append(max(0, w - ww))

    for y0 in y_positions:
        for x0 in x_positions:
            patch = img_aligned[y0:y0 + wh, x0:x0 + ww]
            if patch.shape[0] < 64 or patch.shape[1] < 64:
                continue

            try:
                patch_norm = normalize_image(patch)
                _, mag = compute_fft_magnitude(patch_norm)

                wale_fft = estimate_period_from_fft_axis(
                    mag,
                    axis="x",
                    min_spacing_px=min_spacing_px,
                    max_spacing_px=max_spacing_px,
                )
                course_fft = estimate_period_from_fft_axis(
                    mag,
                    axis="y",
                    min_spacing_px=min_spacing_px,
                    max_spacing_px=max_spacing_px,
                )

                wale_ref = refine_period_with_autocorr(
                    patch,
                    initial_period_px=wale_fft["period_px"],
                    direction="x",
                    search_halfwidth_px=10,
                )
                course_ref = refine_period_with_autocorr(
                    patch,
                    initial_period_px=course_fft["period_px"],
                    direction="y",
                    search_halfwidth_px=10,
                )

                wale_vals.append(float(wale_ref["period_px"]))
                course_vals.append(float(course_ref["period_px"]))
            except Exception:
                continue

    return {
        "wale_px": summarize_values(wale_vals),
        "course_px": summarize_values(course_vals),
    }


# ============================================================
# Reporting
# ============================================================

def save_diagnostic_figure(result: dict[str, Any], out_prefix: str) -> Path:
    img_raw = result["img_raw"]
    img_rot_crop = result["img_rot_crop"]
    mag = result["fft_mag"]
    orient = result["orientation"]
    fft_wale = result["fft_wale"]
    fft_course = result["fft_course"]
    ac_wale = result["ac_wale"]
    ac_course = result["ac_course"]

    h, w = mag.shape
    cy, cx = h // 2, w // 2

    fig = plt.figure(figsize=(16, 12))

    ax1 = plt.subplot(2, 3, 1)
    ax1.imshow(img_raw, cmap="gray")
    ax1.set_title("Original image")
    ax1.axis("off")

    ax2 = plt.subplot(2, 3, 2)
    bins = orient["bin_centers_deg"]
    ax2.plot(bins, orient["hist"], alpha=0.4, label="Raw histogram")
    ax2.plot(bins, orient["hist_smooth"], linewidth=2, label="Smoothed histogram")
    ax2.axvline(
        orient["grad_peak_deg"],
        color="r",
        linestyle="--",
        label=f"Gradient peak = {orient['grad_peak_deg']:.1f}°",
    )
    ax2.axvline(
        orient["ridge_peak_deg"],
        color="b",
        linestyle="--",
        label=f"Ridge peak = {orient['ridge_peak_deg']:.1f}°",
    )
    ax2.set_xlim(0, 180)
    ax2.set_xlabel("Orientation (deg, undirected)")
    ax2.set_ylabel("Weighted count")
    ax2.set_title("HOG-style dominant orientation analysis")
    ax2.legend()

    ax3 = plt.subplot(2, 3, 3)
    ax3.imshow(img_rot_crop, cmap="gray")
    ax3.set_title(f"Aligned image (rotation = {result['rotation_deg']:.2f}°)")
    ax3.axis("off")

    ax4 = plt.subplot(2, 3, 4)
    ax4.imshow(mag, cmap="magma")
    ax4.axvline(cx, color="white", linewidth=0.8, alpha=0.6)
    ax4.axhline(cy, color="white", linewidth=0.8, alpha=0.6)

    x_peak = fft_wale["peak_idx"]
    ax4.plot([x_peak], [cy], "co", markersize=8, label="Wale freq peak")
    ax4.plot([2 * cx - x_peak], [cy], "co", markersize=8)

    y_peak = fft_course["peak_idx"]
    ax4.plot([cx], [y_peak], "go", markersize=8, label="Course freq peak")
    ax4.plot([cx], [2 * cy - y_peak], "go", markersize=8)

    ax4.set_title("Annotated FFT magnitude")
    ax4.axis("off")
    ax4.legend(loc="lower right")

    ax5 = plt.subplot(2, 3, 5)
    acx = ac_wale["autocorr"]
    px_w = int(round(ac_wale["period_px"]))
    xmax = min(len(acx), max(220, px_w * 4))
    ax5.plot(np.arange(xmax), acx[:xmax])
    ax5.axvline(px_w, color="c", linestyle="--", label=f"Wale ≈ {ac_wale['period_px']:.1f} px")
    ax5.set_title("Autocorrelation along x (wale spacing)")
    ax5.set_xlabel("Lag (px)")
    ax5.set_ylabel("Normalized autocorrelation")
    ax5.legend()

    ax6 = plt.subplot(2, 3, 6)
    acy = ac_course["autocorr"]
    px_c = int(round(ac_course["period_px"]))
    ymax = min(len(acy), max(220, px_c * 4))
    ax6.plot(np.arange(ymax), acy[:ymax])
    ax6.axvline(px_c, color="g", linestyle="--", label=f"Course ≈ {ac_course['period_px']:.1f} px")
    ax6.set_title("Autocorrelation along y (course spacing)")
    ax6.set_xlabel("Lag (px)")
    ax6.set_ylabel("Normalized autocorrelation")
    ax6.legend()

    fig.tight_layout()
    out_path = Path(f"{out_prefix}_diagnostic.png")
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


def write_markdown_report(result: dict[str, Any], md_path: str, diagnostic_path: str) -> Path:
    md_path_obj = Path(md_path)
    wale_stats = result.get("wale_stats_px", {})
    course_stats = result.get("course_stats_px", {})

    wale_mean_mm = px_to_mm(wale_stats["mean"], result["dpi"]) if wale_stats.get("n", 0) > 0 else float("nan")
    course_mean_mm = px_to_mm(course_stats["mean"], result["dpi"]) if course_stats.get("n", 0) > 0 else float("nan")

    wale_per_10cm = mm_to_count_per_10cm(wale_mean_mm) if np.isfinite(wale_mean_mm) else float("nan")
    course_per_10cm = mm_to_count_per_10cm(course_mean_mm) if np.isfinite(course_mean_mm) else float("nan")

    lines = [
        f"# Knit spacing analysis",
        "",
        "## Input",
        f"- Image: {Path(result['image_path']).name}",
        f"- DPI: {result['dpi']:.3f}",
        "",
        "## Orientation",
        f"- Dominant gradient orientation: {result['dominant_gradient_deg']:.2f} deg",
        f"- Dominant ridge orientation: {result['dominant_ridge_deg']:.2f} deg",
        f"- Applied rotation: {result['rotation_deg']:.2f} deg",
        "",
        "## Global spacing",
        f"- Wale spacing: {result['wale_spacing_px']:.2f} px = {result['wale_spacing_mm']:.3f} mm",
        f"- Course spacing: {result['course_spacing_px']:.2f} px = {result['course_spacing_mm']:.3f} mm",
        f"- Wales per 10 cm: {result['wales_per_10cm']:.2f}",
        f"- Courses per 10 cm: {result['courses_per_10cm']:.2f}",
        "",
        "## Local-window variance summary",
        "### Wale spacing",
        f"- Valid windows: {wale_stats.get('n', 0)}",
        f"- Mean: {wale_stats.get('mean', float('nan')):.2f} px",
        f"- Median: {wale_stats.get('median', float('nan')):.2f} px",
        f"- Std: {wale_stats.get('std', float('nan')):.2f} px",
        f"- CV: {wale_stats.get('cv', float('nan')):.4f}",
        f"- Range: {wale_stats.get('min', float('nan')):.2f} to {wale_stats.get('max', float('nan')):.2f} px",
        f"- Mean: {wale_mean_mm:.3f} mm",
        f"- Wales per 10 cm from mean: {wale_per_10cm:.2f}",
        "",
        "### Course spacing",
        f"- Valid windows: {course_stats.get('n', 0)}",
        f"- Mean: {course_stats.get('mean', float('nan')):.2f} px",
        f"- Median: {course_stats.get('median', float('nan')):.2f} px",
        f"- Std: {course_stats.get('std', float('nan')):.2f} px",
        f"- CV: {course_stats.get('cv', float('nan')):.4f}",
        f"- Range: {course_stats.get('min', float('nan')):.2f} to {course_stats.get('max', float('nan')):.2f} px",
        f"- Mean: {course_mean_mm:.3f} mm",
        f"- Courses per 10 cm from mean: {course_per_10cm:.2f}",
        "",
        "## Interpretation",
        "- Lower CV indicates more spatially stable spacing across the image.",
        "- Higher CV indicates greater local variability and/or ambiguity in periodic detection.",
        "- Local variance is computed from repeated window-level estimates, not from raw FFT bins.",
        "",
        "## Files",
        f"- Diagnostic image: {Path(diagnostic_path).name}",
    ]

    md_path_obj.write_text("\n".join(lines), encoding="utf-8")
    return md_path_obj


def print_result(result: dict[str, Any], out_prefix: str, md_path: Path, diagnostic_path: Path) -> None:
    print("\n===== KNIT HOG + FFT ANALYSIS RESULT =====")
    print(f"Image: {result['image_path']}")
    print(f"DPI:   {result['dpi']:.3f}")

    print("\nOrientation:")
    print(f"  Dominant gradient orientation: {result['dominant_gradient_deg']:.2f} deg")
    print(f"  Dominant ridge orientation:    {result['dominant_ridge_deg']:.2f} deg")
    print(f"  Applied rotation:              {result['rotation_deg']:.2f} deg")

    print("\nSpacing:")
    print(f"  Wale spacing:   {result['wale_spacing_px']:.2f} px   = {result['wale_spacing_mm']:.3f} mm")
    print(f"  Course spacing: {result['course_spacing_px']:.2f} px   = {result['course_spacing_mm']:.3f} mm")

    print("\nCount per 10 cm:")
    print(f"  Wales per 10 cm:   {result['wales_per_10cm']:.2f}")
    print(f"  Courses per 10 cm: {result['courses_per_10cm']:.2f}")

    wale_stats = result.get("wale_stats_px", {})
    course_stats = result.get("course_stats_px", {})
    print("\nLocal-window variance:")
    print(
        f"  Wale std / CV:    {wale_stats.get('std', float('nan')):.2f} px / {wale_stats.get('cv', float('nan')):.4f}"
    )
    print(
        f"  Course std / CV:  {course_stats.get('std', float('nan')):.2f} px / {course_stats.get('cv', float('nan')):.4f}"
    )

    print("\nSaved output:")
    print(f"  {diagnostic_path}")
    print(f"  {md_path}")


# ============================================================
# Main analysis
# ============================================================

def analyze_knit_image(
    image_path: str,
    dpi: float,
    out_prefix: str = "knit_hog_fft",
    min_spacing_px: float = 8.0,
    max_spacing_px: float = 200.0,
    center_crop_frac_after_rotation: float = 0.8,
) -> dict[str, Any]:
    img_raw = load_grayscale(image_path)
    img_for_hog = cv2.GaussianBlur(img_raw, (0, 0), 1.0)

    orient = estimate_knit_orientation_hog(
        img_for_hog,
        num_bins=180,
        grad_percentile_thresh=60.0,
    )

    rotation_deg, rotation_candidates = choose_best_rotation_from_hog(
        img_raw=img_raw,
        orient=orient,
        crop_frac=center_crop_frac_after_rotation,
    )
    img_rot = rotate_image_keep_bounds(img_raw, rotation_deg)
    img_rot_crop = center_crop_fraction(img_rot, frac=center_crop_frac_after_rotation)
    img_norm = normalize_image(img_rot_crop)
    _, mag = compute_fft_magnitude(img_norm)

    wale_fft = estimate_period_from_fft_axis(
        mag,
        axis="x",
        min_spacing_px=min_spacing_px,
        max_spacing_px=max_spacing_px,
    )
    course_fft = estimate_period_from_fft_axis(
        mag,
        axis="y",
        min_spacing_px=min_spacing_px,
        max_spacing_px=max_spacing_px,
    )

    wale_refined = refine_period_with_autocorr(
        img_rot_crop,
        initial_period_px=wale_fft["period_px"],
        direction="x",
        search_halfwidth_px=12,
    )
    course_refined = refine_period_with_autocorr(
        img_rot_crop,
        initial_period_px=course_fft["period_px"],
        direction="y",
        search_halfwidth_px=12,
    )

    local_stats = analyze_windows(
        img_rot_crop,
        min_spacing_px=min_spacing_px,
        max_spacing_px=max_spacing_px,
        window_frac=0.35,
        stride_frac=0.5,
    )

    wale_px = wale_refined["period_px"]
    course_px = course_refined["period_px"]

    wale_mm = px_to_mm(wale_px, dpi)
    course_mm = px_to_mm(course_px, dpi)

    wales_per_10cm = mm_to_count_per_10cm(wale_mm)
    courses_per_10cm = mm_to_count_per_10cm(course_mm)

    result = {
        "image_path": image_path,
        "dpi": dpi,
        "rotation_deg": rotation_deg,
        "dominant_gradient_deg": orient["grad_peak_deg"],
        "dominant_ridge_deg": orient["ridge_peak_deg"],
        "rotation_candidates": rotation_candidates,
        "wale_spacing_px": wale_px,
        "course_spacing_px": course_px,
        "wale_spacing_mm": wale_mm,
        "course_spacing_mm": course_mm,
        "wales_per_10cm": wales_per_10cm,
        "courses_per_10cm": courses_per_10cm,
        "orientation": orient,
        "img_raw": img_raw,
        "img_rot_crop": img_rot_crop,
        "fft_mag": mag,
        "fft_wale": wale_fft,
        "fft_course": course_fft,
        "ac_wale": wale_refined,
        "ac_course": course_refined,
        "wale_stats_px": local_stats["wale_px"],
        "course_stats_px": local_stats["course_px"],
    }
    return result


# ============================================================
# CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="HOG-guided FFT stitch spacing estimator for knit images"
    )
    parser.add_argument("image", type=str, help="Path to image")
    parser.add_argument("--dpi", type=float, required=True, help="DPI for px->mm conversion")
    parser.add_argument("--out-prefix", type=str, default=None, help="Prefix for output files")
    parser.add_argument("--min-spacing-px", type=float, default=8.0, help="Minimum plausible spacing in pixels")
    parser.add_argument("--max-spacing-px", type=float, default=200.0, help="Maximum plausible spacing in pixels")
    parser.add_argument(
        "--crop-frac",
        type=float,
        default=0.8,
        help="Central crop fraction after rotation, to reduce edge artefacts",
    )

    args = parser.parse_args()
    image_path = Path(args.image)
    out_prefix = args.out_prefix or str(image_path.with_suffix(""))

    result = analyze_knit_image(
        image_path=str(image_path),
        dpi=args.dpi,
        out_prefix=out_prefix,
        min_spacing_px=args.min_spacing_px,
        max_spacing_px=args.max_spacing_px,
        center_crop_frac_after_rotation=args.crop_frac,
    )

    diagnostic_path = save_diagnostic_figure(result, out_prefix)
    md_path = write_markdown_report(
        result=result,
        md_path=str(image_path.with_suffix(".md")),
        diagnostic_path=str(diagnostic_path),
    )
    print_result(result, out_prefix, md_path, diagnostic_path)


if __name__ == "__main__":
    main()
