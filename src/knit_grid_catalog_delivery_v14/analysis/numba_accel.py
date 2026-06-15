from __future__ import annotations

import os
from typing import Tuple

import numpy as np


NUMBA_AVAILABLE = False

if os.environ.get("KNIT_GRID_DISABLE_NUMBA", "").strip().lower() not in {"1", "true", "yes"}:
    try:
        from numba import njit, prange

        NUMBA_AVAILABLE = True
    except Exception:  # pragma: no cover - optional acceleration
        NUMBA_AVAILABLE = False

if NUMBA_AVAILABLE:

    @njit(cache=False, fastmath=True, nogil=True, parallel=True)
    def _limited_autocorr_lags_numba(x: np.ndarray, min_lag: int, max_lag: int) -> np.ndarray:
        n = x.shape[0]
        count = max_lag - min_lag + 1
        out = np.zeros(count, dtype=np.float64)
        for k in prange(count):
            lag = min_lag + k
            total = 0.0
            stop = n - lag
            for i in range(stop):
                total += float(x[i]) * float(x[i + lag])
            out[k] = total
        return out

    @njit(cache=False, fastmath=True, nogil=True)
    def _peak_pair_histogram_numba(peaks_yx: np.ndarray, axis_is_a: bool, lo: float, hi: float) -> np.ndarray:
        n = peaks_yx.shape[0]
        nbins = int(np.ceil(hi - lo))
        hist = np.zeros(nbins, dtype=np.float64)
        cross_limit = 0.35 * hi
        for i in range(n):
            yi = float(peaks_yx[i, 0])
            xi = float(peaks_yx[i, 1])
            for j in range(i + 1, n):
                dy = abs(float(peaks_yx[j, 0]) - yi)
                dx = abs(float(peaks_yx[j, 1]) - xi)
                value = dx if axis_is_a else dy
                cross = dy if axis_is_a else dx
                if cross < cross_limit and value >= lo and value <= hi:
                    b = int(value - lo)
                    if b >= nbins:
                        b = nbins - 1
                    if b >= 0:
                        hist[b] += 1.0
        return hist

    @njit(cache=False, fastmath=True, nogil=True)
    def _nms_keep_indices_numba(pts_yx: np.ndarray, order: np.ndarray, min_sep2: float) -> np.ndarray:
        n = order.shape[0]
        keep = np.empty(n, dtype=np.int64)
        nkeep = 0
        for oi in range(n):
            idx = int(order[oi])
            y = float(pts_yx[idx, 0])
            x = float(pts_yx[idx, 1])
            ok = True
            for ki in range(nkeep):
                kept_idx = keep[ki]
                ky = float(pts_yx[kept_idx, 0])
                kx = float(pts_yx[kept_idx, 1])
                dy = y - ky
                dx = x - kx
                if dx * dx + dy * dy <= min_sep2:
                    ok = False
                    break
            if ok:
                keep[nkeep] = idx
                nkeep += 1
        return keep[:nkeep]

    @njit(cache=False, fastmath=True, nogil=True)
    def _best_periodic_offset_numba(coords: np.ndarray, period: float) -> float:
        n = coords.shape[0]
        if n == 0:
            return 0.0

        residues = np.empty(n, dtype=np.float64)
        for i in range(n):
            residues[i] = float(coords[i]) % period

        sigma = max(1.5, period * 0.10)
        denom = 2.0 * sigma * sigma
        best_score = -1.0
        best_offset = 0.0

        for gi in range(300):
            off = period * float(gi) / 300.0
            score = 0.0
            for i in range(n):
                d = abs(residues[i] - off)
                d = min(d, period - d)
                score += np.exp(-(d * d) / denom)
            if score > best_score:
                best_score = score
                best_offset = off

        weighted_sum = 0.0
        weight_total = 0.0
        half = period / 2.0
        for i in range(n):
            d = residues[i] - best_offset
            d = (d + half) % period - half
            weight = np.exp(-(d * d) / denom)
            weighted_sum += weight * (best_offset + d)
            weight_total += weight

        if weight_total > 1e-6:
            best_offset = (weighted_sum / weight_total) % period

        return best_offset

    @njit(cache=False, fastmath=True, nogil=True)
    def _nearest_grid_deviation_numba(peaks_yx: np.ndarray, a: float, b: float, x0: float, y0: float) -> Tuple[float, np.ndarray]:
        n = peaks_yx.shape[0]
        deviations = np.empty((n, 3), dtype=np.float64)
        if n == 0:
            return 999.0, deviations[:0]

        total = 0.0
        for i in range(n):
            y = float(peaks_yx[i, 0])
            x = float(peaks_yx[i, 1])
            ix = round((x - x0) / a)
            iy = round((y - y0) / b)
            gx = x0 + ix * a
            gy = y0 + iy * b
            dx = x - gx
            dy = y - gy
            d = np.sqrt(dx * dx + dy * dy)
            deviations[i, 0] = y
            deviations[i, 1] = x
            deviations[i, 2] = d
            total += d * d

        return np.sqrt(total / n), deviations


def limited_autocorr_lags(x: np.ndarray, min_lag: int, max_lag: int) -> np.ndarray:
    if NUMBA_AVAILABLE:
        return _limited_autocorr_lags_numba(np.asarray(x, dtype=np.float64), int(min_lag), int(max_lag))

    x = np.asarray(x, dtype=np.float64)
    return np.array([np.dot(x[:-lag], x[lag:]) for lag in range(min_lag, max_lag + 1)], dtype=np.float64)


def peak_pair_histogram(peaks_yx: np.ndarray, axis: str, lo: float, hi: float) -> np.ndarray:
    peaks_yx = np.asarray(peaks_yx[:450], dtype=np.float64)
    if NUMBA_AVAILABLE:
        return _peak_pair_histogram_numba(peaks_yx, axis == "a", float(lo), float(hi))

    nbins = int(np.ceil(hi - lo))
    hist = np.zeros(nbins, dtype=np.float64)
    cross_limit = 0.35 * hi
    n = len(peaks_yx)
    for i in range(n):
        yi, xi = peaks_yx[i]
        for j in range(i + 1, n):
            yj, xj = peaks_yx[j]
            dy = abs(yj - yi)
            dx = abs(xj - xi)
            value = dx if axis == "a" else dy
            cross = dy if axis == "a" else dx
            if cross < cross_limit and lo <= value <= hi:
                b = int(value - lo)
                if b >= nbins:
                    b = nbins - 1
                if b >= 0:
                    hist[b] += 1.0
    return hist


def nms_keep_indices(pts_yx: np.ndarray, order: np.ndarray, min_sep2: float) -> np.ndarray:
    pts_yx = np.asarray(pts_yx, dtype=np.float64)
    order = np.asarray(order, dtype=np.int64)
    if NUMBA_AVAILABLE:
        return _nms_keep_indices_numba(pts_yx, order, float(min_sep2))

    keep = []
    for idx in order:
        y, x = pts_yx[idx]
        if all((x - pts_yx[k, 1]) ** 2 + (y - pts_yx[k, 0]) ** 2 > min_sep2 for k in keep):
            keep.append(int(idx))
    return np.asarray(keep, dtype=np.int64)


def best_periodic_offset_accel(coords: np.ndarray, period: float) -> float:
    coords = np.asarray(coords, dtype=np.float64)
    if NUMBA_AVAILABLE:
        return float(_best_periodic_offset_numba(coords, float(period)))

    if len(coords) == 0:
        return 0.0
    residues = np.mod(coords, period)
    grid = np.linspace(0, period, 300, endpoint=False)
    sigma = max(1.5, period * 0.10)
    best_score = -1.0
    best_offset = 0.0
    for off in grid:
        d = np.abs(residues - off)
        d = np.minimum(d, period - d)
        score = float(np.exp(-(d ** 2) / (2 * sigma ** 2)).sum())
        if score > best_score:
            best_score = score
            best_offset = float(off)
    d = residues - best_offset
    d = (d + period / 2.0) % period - period / 2.0
    weights = np.exp(-(d ** 2) / (2 * sigma ** 2))
    if weights.sum() > 1e-6:
        best_offset = float((weights * (best_offset + d)).sum() / weights.sum()) % period
    return best_offset


def nearest_grid_deviation_accel(peaks_yx: np.ndarray, a: float, b: float, x0: float, y0: float) -> Tuple[float, np.ndarray]:
    peaks_yx = np.asarray(peaks_yx, dtype=np.float64)
    if NUMBA_AVAILABLE:
        return _nearest_grid_deviation_numba(peaks_yx, float(a), float(b), float(x0), float(y0))

    deviations = []
    for y, x in peaks_yx:
        ix = round((x - x0) / a)
        iy = round((y - y0) / b)
        gx = x0 + ix * a
        gy = y0 + iy * b
        d = ((x - gx) ** 2 + (y - gy) ** 2) ** 0.5
        deviations.append((y, x, float(d)))
    if not deviations:
        return 999.0, np.empty((0, 3), dtype=np.float64)
    arr = np.asarray(deviations, dtype=np.float64)
    rms = float(np.sqrt(np.mean(arr[:, 2] ** 2)))
    return rms, arr


def warm_numba_kernels() -> None:
    if not NUMBA_AVAILABLE:
        return
    profile = np.linspace(-1.0, 1.0, 64, dtype=np.float64)
    peaks = np.array([[0.0, 0.0], [10.0, 32.0], [11.0, 64.0]], dtype=np.float64)
    order = np.array([2, 1, 0], dtype=np.int64)
    limited_autocorr_lags(profile, 2, 8)
    peak_pair_histogram(peaks, "a", 5.0, 40.0)
    nms_keep_indices(peaks, order, 16.0)
    best_periodic_offset_accel(profile, 8.0)
    nearest_grid_deviation_accel(peaks, 32.0, 16.0, 0.0, 0.0)
