"""Image stacking / integration.

Phase 1: average / median.
Phase 2+: weighted average, sigma clipping, winsorized sigma clipping, min/max rejection.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

import numpy as np


def stack(
    images: Iterable[np.ndarray],
    method: str = "average",
    weights: Optional[Sequence[float]] = None,
    sigma_low: float = 3.0,
    sigma_high: float = 3.0,
) -> np.ndarray:
    arrs: List[np.ndarray] = [a for a in images if a is not None]
    if not arrs:
        raise ValueError("No frames to stack.")
    target_shape = _common_shape(arrs)
    aligned = [_fit_to_shape(a, target_shape) for a in arrs]
    cube = np.stack(aligned, axis=0).astype(np.float32)

    if method == "median":
        result = np.median(cube, axis=0)
    elif method == "average":
        result = cube.mean(axis=0)
    elif method == "weighted_average":
        w = np.asarray(
            weights if weights is not None else [1.0] * len(aligned), dtype=np.float32
        )
        if w.size != cube.shape[0]:
            raise ValueError("weights length must equal frame count")
        if float(w.sum()) <= 0:
            w = np.ones_like(w)
        w = w / float(w.sum())
        if cube.ndim == 4:
            wb = w[:, None, None, None]
        else:
            wb = w[:, None, None]
        result = (cube * wb).sum(axis=0)
    elif method == "sigma_clip":
        result = _sigma_clip(cube, sigma_low=sigma_low, sigma_high=sigma_high, winsorize=False)
    elif method == "winsorized_sigma_clip":
        result = _sigma_clip(cube, sigma_low=sigma_low, sigma_high=sigma_high, winsorize=True)
    elif method == "minmax_reject":
        result = _minmax(cube)
    else:
        raise ValueError(f"Unknown stacking method: {method}")

    return np.clip(result, 0.0, 1.0).astype(np.float32)


def _sigma_clip(
    cube: np.ndarray,
    sigma_low: float,
    sigma_high: float,
    winsorize: bool,
    iters: int = 3,
) -> np.ndarray:
    data = cube.astype(np.float32).copy()
    mask = np.ones_like(data, dtype=bool)
    for _ in range(iters):
        masked = np.where(mask, data, np.nan)
        mu = np.nanmean(masked, axis=0)
        sd = np.nanstd(masked, axis=0)
        sd_safe = np.maximum(sd, 1e-6)
        diff = data - mu
        new_mask = (diff >= -sigma_low * sd_safe) & (diff <= sigma_high * sd_safe)
        if winsorize:
            lo = mu - sigma_low * sd_safe
            hi = mu + sigma_high * sd_safe
            data = np.where(diff < -sigma_low * sd_safe, lo, data)
            data = np.where(diff > sigma_high * sd_safe, hi, data)
            mask = np.ones_like(data, dtype=bool)
        else:
            mask = new_mask
    masked = np.where(mask, data, np.nan)
    out = np.nanmean(masked, axis=0)
    return np.nan_to_num(out, nan=float(np.nanmedian(masked)))


def _minmax(cube: np.ndarray) -> np.ndarray:
    if cube.shape[0] < 3:
        return cube.mean(axis=0)
    sorted_cube = np.sort(cube, axis=0)
    trimmed = sorted_cube[1:-1]
    return trimmed.mean(axis=0)


def _common_shape(arrs: List[np.ndarray]):
    shapes = [a.shape for a in arrs]
    h = min(s[0] for s in shapes)
    w = min(s[1] for s in shapes)
    is_color = any(a.ndim == 3 for a in arrs)
    if is_color:
        c = max((a.shape[2] if a.ndim == 3 else 1) for a in arrs)
        return (h, w, c)
    return (h, w)


def _fit_to_shape(arr: np.ndarray, shape) -> np.ndarray:
    if len(shape) == 3 and arr.ndim == 2:
        arr = np.stack([arr] * shape[2], axis=-1)
    if len(shape) == 2 and arr.ndim == 3:
        arr = arr.mean(axis=-1)
    h, w = shape[0], shape[1]
    return arr[:h, :w] if arr.ndim == 2 else arr[:h, :w, : shape[2]]
