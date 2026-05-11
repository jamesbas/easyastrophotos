"""Background / gradient extraction with Abe-style automatic sample selection.

Algorithm:
1. Divide the image into a regular grid of cells (default 32x32).
2. Each cell contributes a candidate sample chosen as a low percentile of its
   pixel values (default 20%) — this picks the local background, not stars or
   nebula peaks.
3. Iteratively sigma-clip the candidate set: fit a smooth surface, reject any
   sample more than ``sigma_high`` MAD-sigmas above the fit, refit. Repeat a
   few times. This is the same idea PixInsight's ABE uses.
4. Fit the final surface with thin-plate-spline RBF (default) or a low-degree
   polynomial. Optionally Gaussian-smooth the result.
5. Subtract (with a constant baseline preserved) or divide.

Color images are processed per channel — gradients usually differ in R/G/B
because of light pollution color casts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

import numpy as np

from .image_io import to_mono


@dataclass
class BackgroundOptions:
    method: Literal["polynomial", "rbf", "ai"] = "rbf"
    degree: int = 4
    smoothing: float = 0.5  # 0..1
    correction: Literal["subtraction", "division"] = "subtraction"
    strength: float = 1.0  # 0..1
    protect_objects: bool = True
    samples: int = 32  # grid divisions per side
    sample_percentile: float = 20.0  # 0..50 — percentile within each cell
    sigma_high: float = 2.5  # MAD-sigma rejection threshold
    rejection_iters: int = 3
    sample_points: Optional[List[Tuple[int, int]]] = None  # legacy override


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def estimate_background(image: np.ndarray, options: BackgroundOptions) -> np.ndarray:
    if image.ndim == 3:
        models = [estimate_background(image[..., c], options) for c in range(image.shape[2])]
        return np.stack(models, axis=-1)

    h, w = image.shape
    samples = _collect_samples(image, options)
    if not samples:
        return np.full_like(image, float(np.median(image)))

    ys, xs, vs = _split(samples)
    if options.method == "rbf":
        model = _rbf_surface(h, w, ys, xs, vs, smoothing=options.smoothing)
    else:
        model = _poly_surface(h, w, ys, xs, vs, degree=options.degree)
    if options.smoothing > 0:
        model = _smooth(model, options.smoothing)
    return model.astype(np.float32)


def remove_background(
    image: np.ndarray, options: BackgroundOptions
) -> Tuple[np.ndarray, np.ndarray]:
    bg = estimate_background(image, options)
    if options.correction == "division":
        denom = np.maximum(bg, 1e-6)
        target_mean = float(np.mean(bg))
        corrected = image * (target_mean / denom)
        out = options.strength * corrected + (1.0 - options.strength) * image
    else:
        baseline = float(np.percentile(bg, 5))
        out = image - options.strength * (bg - baseline)
    return np.clip(out, 0.0, 1.0).astype(np.float32), bg


# --------------------------------------------------------------------------- #
# Sample collection (Abe-style)
# --------------------------------------------------------------------------- #

def _collect_samples(
    image: np.ndarray, options: BackgroundOptions
) -> List[Tuple[float, float, float]]:
    """Return a list of ``(y, x, value)`` background samples."""
    h, w = image.shape

    if options.sample_points:
        return [
            (float(y), float(x), float(image[int(y), int(x)]))
            for (y, x) in options.sample_points
        ]

    grid = max(8, int(options.samples))
    pct = float(np.clip(options.sample_percentile, 1.0, 50.0))
    cell_h = max(2, h // grid)
    cell_w = max(2, w // grid)

    raw: List[Tuple[float, float, float]] = []
    for gy in range(grid):
        y0 = gy * cell_h
        y1 = min(h, y0 + cell_h)
        if y1 - y0 < 2:
            continue
        for gx in range(grid):
            x0 = gx * cell_w
            x1 = min(w, x0 + cell_w)
            if x1 - x0 < 2:
                continue
            cell = image[y0:y1, x0:x1]
            val = float(np.percentile(cell, pct))
            # Choose the in-cell pixel closest to that percentile so the
            # sample carries a real (y, x) coordinate.
            diff = np.abs(cell - val)
            iy, ix = np.unravel_index(int(np.argmin(diff)), cell.shape)
            raw.append((float(y0 + iy), float(x0 + ix), float(cell[iy, ix])))

    if not options.protect_objects or len(raw) < 8:
        return raw

    # Iterative sigma-clip rejection against a low-degree polynomial fit.
    survivors = raw
    for _ in range(int(max(0, options.rejection_iters))):
        ys, xs, vs = _split(survivors)
        fit = _poly_surface(h, w, ys, xs, vs, degree=min(3, options.degree))
        preds = np.array([fit[int(round(y)), int(round(x))] for (y, x, _v) in survivors])
        vals = np.array([v for (_y, _x, v) in survivors])
        residuals = vals - preds
        mad = float(np.median(np.abs(residuals - np.median(residuals)))) * 1.4826 + 1e-8
        keep = residuals < options.sigma_high * mad
        new = [survivors[i] for i in range(len(survivors)) if keep[i]]
        if len(new) < 8 or len(new) == len(survivors):
            survivors = new or survivors
            break
        survivors = new
    return survivors


def _split(samples):
    ys = np.array([s[0] for s in samples], dtype=np.float32)
    xs = np.array([s[1] for s in samples], dtype=np.float32)
    vs = np.array([s[2] for s in samples], dtype=np.float32)
    return ys, xs, vs


# --------------------------------------------------------------------------- #
# Surfaces
# --------------------------------------------------------------------------- #

def _poly_surface(
    h: int, w: int, ys: np.ndarray, xs: np.ndarray, vs: np.ndarray, degree: int
) -> np.ndarray:
    degree = max(1, min(int(degree), 5))
    yn = ys / max(1.0, h - 1)
    xn = xs / max(1.0, w - 1)
    terms = []
    for d in range(degree + 1):
        for i in range(d + 1):
            terms.append((yn ** (d - i)) * (xn ** i))
    A = np.stack(terms, axis=-1)
    coef, *_ = np.linalg.lstsq(A, vs, rcond=None)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    yy = yy / max(1.0, h - 1)
    xx = xx / max(1.0, w - 1)
    surface = np.zeros((h, w), dtype=np.float32)
    k = 0
    for d in range(degree + 1):
        for i in range(d + 1):
            surface += coef[k] * (yy ** (d - i)) * (xx ** i)
            k += 1
    return surface


def _rbf_surface(
    h: int, w: int, ys: np.ndarray, xs: np.ndarray, vs: np.ndarray, smoothing: float
) -> np.ndarray:
    try:
        from scipy.interpolate import RBFInterpolator

        pts = np.stack([ys, xs], axis=-1)
        # Thin-plate spline; smoothing scales with user setting.
        smooth = float(smoothing) * (1.0 + len(vs) * 0.02)
        rbf = RBFInterpolator(pts, vs, kernel="thin_plate_spline", smoothing=smooth)
        # Evaluate on a coarse grid and upscale (TPS is O(N^3) in samples).
        gh = max(16, h // 16)
        gw = max(16, w // 16)
        gy = np.linspace(0, h - 1, gh)
        gx = np.linspace(0, w - 1, gw)
        Y, X = np.meshgrid(gy, gx, indexing="ij")
        flat = np.stack([Y.ravel(), X.ravel()], axis=-1)
        small = rbf(flat).reshape(gh, gw).astype(np.float32)
        return _resize(small, (h, w))
    except Exception:
        return _poly_surface(h, w, ys, xs, vs, degree=3)


def _resize(arr: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    try:
        import cv2

        return cv2.resize(arr, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC)
    except Exception:
        zy = shape[0] / arr.shape[0]
        zx = shape[1] / arr.shape[1]
        from scipy.ndimage import zoom

        return zoom(arr, (zy, zx), order=2)


def _smooth(arr: np.ndarray, amount: float) -> np.ndarray:
    sigma = 2.0 + amount * 30.0
    try:
        import cv2

        return cv2.GaussianBlur(arr.astype(np.float32), (0, 0), sigmaX=sigma)
    except Exception:
        from scipy.ndimage import gaussian_filter

        return gaussian_filter(arr.astype(np.float32), sigma=sigma)
