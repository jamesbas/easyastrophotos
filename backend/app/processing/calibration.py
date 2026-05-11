"""Calibration: master darks, flats, biases, flat-darks; calibrate light frames.

Supports:
- Master frame creation (median or sigma-clipped average)
- Light frame calibration with optional bias subtraction, dark subtraction,
  and flat-field division
- Cosmetic correction for hot/cold pixels
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np

from .image_io import load_image
from .stacking import _common_shape, _fit_to_shape  # internal helpers


@dataclass
class CalibrationOptions:
    use_darks: bool = True
    use_flats: bool = True
    use_bias: bool = True
    cosmetic_correction: bool = True
    dark_optimization: bool = False
    flat_normalization: str = "mean"  # "mean" | "median"


def make_master_frame(paths: Iterable[Path], method: str = "median") -> Optional[np.ndarray]:
    arrs = [load_image(Path(p)) for p in paths]
    arrs = [a for a in arrs if a is not None]
    if not arrs:
        return None
    target = _common_shape(arrs)
    aligned = [_fit_to_shape(a, target) for a in arrs]
    cube = np.stack(aligned, axis=0).astype(np.float32)
    if method == "average":
        return cube.mean(axis=0).astype(np.float32)
    if method == "sigma_clip":
        return _sigma_clip_mean(cube, sigma=3.0).astype(np.float32)
    return np.median(cube, axis=0).astype(np.float32)


def _sigma_clip_mean(cube: np.ndarray, sigma: float = 3.0, iters: int = 3) -> np.ndarray:
    data = cube.astype(np.float32)
    mask = np.ones_like(data, dtype=bool)
    for _ in range(iters):
        mean = np.where(mask, data, np.nan)
        mu = np.nanmean(mean, axis=0)
        sd = np.nanstd(mean, axis=0)
        diff = np.abs(data - mu)
        mask = diff <= sigma * np.maximum(sd, 1e-6)
    masked = np.where(mask, data, np.nan)
    out = np.nanmean(masked, axis=0)
    return np.nan_to_num(out, nan=float(np.nanmedian(masked)))


def normalize_flat(flat: np.ndarray, method: str = "mean") -> np.ndarray:
    f = flat.astype(np.float32)
    if method == "median":
        denom = float(np.median(f))
    else:
        denom = float(np.mean(f))
    denom = max(denom, 1e-6)
    return f / denom


def calibrate_light(
    light: np.ndarray,
    master_dark: Optional[np.ndarray] = None,
    master_flat: Optional[np.ndarray] = None,
    master_bias: Optional[np.ndarray] = None,
    options: Optional[CalibrationOptions] = None,
) -> np.ndarray:
    options = options or CalibrationOptions()
    img = light.astype(np.float32)

    if options.use_bias and master_bias is not None:
        img = img - _fit(master_bias, img)
    if options.use_darks and master_dark is not None:
        dark = _fit(master_dark, img)
        if options.dark_optimization:
            scale = _optimize_dark_scale(img, dark)
            img = img - scale * dark
        else:
            img = img - dark
    if options.use_flats and master_flat is not None:
        flat = normalize_flat(_fit(master_flat, img), method=options.flat_normalization)
        flat = np.where(flat < 1e-3, 1.0, flat)
        img = img / flat

    if options.cosmetic_correction:
        img = cosmetic_correct(img)

    return np.clip(img, 0.0, 1.0).astype(np.float32)


def _fit(arr: np.ndarray, like: np.ndarray) -> np.ndarray:
    if arr.shape == like.shape:
        return arr
    h = min(arr.shape[0], like.shape[0])
    w = min(arr.shape[1], like.shape[1])
    if arr.ndim == like.ndim:
        return arr[:h, :w] if arr.ndim == 2 else arr[:h, :w, : like.shape[2]]
    if arr.ndim == 2 and like.ndim == 3:
        return np.stack([arr[:h, :w]] * like.shape[2], axis=-1)
    return arr[:h, :w]


def _optimize_dark_scale(light: np.ndarray, dark: np.ndarray) -> float:
    l = light.flatten().astype(np.float32)
    d = dark.flatten().astype(np.float32)
    denom = float(np.dot(d, d))
    if denom < 1e-6:
        return 1.0
    return float(np.clip(np.dot(l, d) / denom, 0.5, 1.5))


def cosmetic_correct(img: np.ndarray, sigma: float = 5.0) -> np.ndarray:
    """Replace hot/cold pixels with a local median."""
    try:
        import cv2
    except Exception:
        return img
    if img.ndim == 3:
        chans = [cosmetic_correct(img[..., c], sigma=sigma) for c in range(img.shape[2])]
        return np.stack(chans, axis=-1)
    med = cv2.medianBlur(img.astype(np.float32), 3)
    diff = img - med
    sd = float(np.median(np.abs(diff))) * 1.4826 + 1e-6
    mask = np.abs(diff) > sigma * sd
    out = np.where(mask, med, img)
    return out.astype(np.float32)
