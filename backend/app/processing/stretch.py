"""Histogram stretching for linear stacked images."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

import numpy as np


@dataclass
class StretchOptions:
    method: Literal["asinh", "percentile", "histogram", "ghs", "curves"] = "asinh"
    black_point: float = 0.001
    midtone: float = 0.25
    white_point: float = 1.0
    protect_highlights: bool = True
    protect_shadows: bool = True
    # GHS-style controls
    stretch_factor: float = 4.0  # higher = more aggressive
    local_intensity: float = 0.5  # 0..1
    # Curves: list of (input, output) anchor points in [0,1].
    curve_points: Optional[List[Tuple[float, float]]] = None


def auto_stretch(
    image: np.ndarray,
    method: str = "asinh",
    black_point: float = 0.001,
    midtone: float = 0.25,
    white_point: float = 1.0,
    options: Optional[StretchOptions] = None,
) -> np.ndarray:
    if options is None:
        options = StretchOptions(
            method=method,  # type: ignore[arg-type]
            black_point=black_point,
            midtone=midtone,
            white_point=white_point,
        )
    m = options.method
    if m == "percentile":
        return _percentile_stretch(image, low=0.5, high=99.7)
    if m == "histogram":
        return _histogram_transform(image, options)
    if m == "ghs":
        return _ghs(image, options)
    if m == "curves":
        return _curves(image, options.curve_points or [(0, 0), (0.5, 0.5), (1, 1)])
    return _asinh_stretch(image, options)


def _percentile_stretch(image: np.ndarray, low: float, high: float) -> np.ndarray:
    img = image.astype(np.float32)
    if img.ndim == 3:
        flat = img.reshape(-1, img.shape[-1])
        lo = np.percentile(flat, low, axis=0)
        hi = np.percentile(flat, high, axis=0)
    else:
        lo = np.percentile(img, low)
        hi = np.percentile(img, high)
    span = np.maximum(hi - lo, 1e-6)
    out = (img - lo) / span
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def _asinh_stretch(image: np.ndarray, opts: StretchOptions) -> np.ndarray:
    img = image.astype(np.float32)
    bg = float(np.median(img))
    sigma = float(np.median(np.abs(img - bg))) * 1.4826
    bp = max(0.0, bg - 2.0 * sigma)
    bp = max(bp, opts.black_point)

    shifted = np.maximum(img - bp, 0.0)
    span = max(opts.white_point - bp, 1e-6)
    shifted = shifted / span

    target = max(opts.midtone, 1e-4)
    alpha = max(1.0 / (target * 50.0), 1e-3)
    stretched = np.arcsinh(shifted / alpha) / np.arcsinh(1.0 / alpha)
    if opts.protect_highlights:
        stretched = _soft_highlight(stretched, knee=0.92)
    return np.clip(stretched, 0.0, 1.0).astype(np.float32)


def _histogram_transform(image: np.ndarray, opts: StretchOptions) -> np.ndarray:
    img = image.astype(np.float32)
    bp = max(0.0, opts.black_point)
    wp = min(1.0, max(opts.white_point, bp + 1e-6))
    mid = float(np.clip(opts.midtone, 0.001, 0.999))
    x = np.clip((img - bp) / (wp - bp), 0.0, 1.0)
    # Midtone transfer function (PixInsight style)
    out = ((mid - 1) * x) / (((2 * mid - 1) * x) - mid)
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def _ghs(image: np.ndarray, opts: StretchOptions) -> np.ndarray:
    """Generalized hyperbolic-style stretch (simplified)."""
    img = np.clip(image.astype(np.float32) - opts.black_point, 0.0, 1.0)
    span = max(opts.white_point - opts.black_point, 1e-6)
    img = img / span
    SP = float(np.clip(opts.local_intensity, 0.001, 0.999))
    D = float(max(opts.stretch_factor, 0.01))
    b = D
    # Hyperbolic mapping centered around SP.
    t = (img - SP) * b
    out = SP + np.tanh(t) * (1.0 - SP) * np.where(img >= SP, 1.0, SP / max(1.0 - SP, 1e-6))
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def _curves(image: np.ndarray, points: List[Tuple[float, float]]) -> np.ndarray:
    pts = sorted(points, key=lambda p: p[0])
    if len(pts) < 2:
        return image.astype(np.float32)
    xs = np.array([p[0] for p in pts], dtype=np.float32)
    ys = np.array([p[1] for p in pts], dtype=np.float32)
    if xs[0] > 0:
        xs = np.concatenate(([0.0], xs))
        ys = np.concatenate(([0.0], ys))
    if xs[-1] < 1:
        xs = np.concatenate((xs, [1.0]))
        ys = np.concatenate((ys, [1.0]))
    lut_x = np.linspace(0.0, 1.0, 1024, dtype=np.float32)
    lut_y = np.interp(lut_x, xs, ys).astype(np.float32)

    img = np.clip(image.astype(np.float32), 0.0, 1.0)
    idx = np.clip((img * 1023.0 + 0.5).astype(np.int32), 0, 1023)
    return lut_y[idx]


def _soft_highlight(img: np.ndarray, knee: float = 0.92) -> np.ndarray:
    out = img.copy()
    mask = out > knee
    out[mask] = knee + (1.0 - knee) * np.tanh((out[mask] - knee) / max(1.0 - knee, 1e-6))
    return out


def histogram(image: np.ndarray, bins: int = 256) -> dict:
    img = image.astype(np.float32)
    if img.ndim == 3 and img.shape[-1] >= 3:
        channels = ["r", "g", "b"]
        hist: dict = {}
        for i, name in enumerate(channels):
            h, edges = np.histogram(img[..., i], bins=bins, range=(0.0, 1.0))
            hist[name] = h.tolist()
        hist["edges"] = edges.tolist()
        return hist
    h, edges = np.histogram(img, bins=bins, range=(0.0, 1.0))
    return {"l": h.tolist(), "edges": edges.tolist()}
