"""Denoising algorithms tuned for astrophotography.

Methods:
- ``starlet``  : à trous (B3-spline) multiscale wavelet denoiser with per-scale
                MAD-estimated noise and soft thresholding. This is the standard
                astrophotography multiscale denoiser (a.k.a. starlet transform,
                Starck et al.). Preserves large-scale nebulosity while killing
                fine grain.
- ``wavelet``  : alias for ``starlet`` (kept for backward compatibility).
- ``nlm``      : non-local means (scikit-image).
- ``bilateral``: bilateral filter (OpenCV).
- ``ai``       : ONNX model via ``processing.ai`` (falls back to ``starlet``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np


@dataclass
class DenoiseOptions:
    method: Literal["nlm", "wavelet", "starlet", "bilateral", "ai"] = "starlet"
    strength: float = 0.45  # 0..1
    protect_stars: bool = True
    model_name: Optional[str] = None  # for AI
    scales: int = 5  # for starlet
    preserve_coarse: bool = True  # do not threshold the coarsest residual


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def denoise(image: np.ndarray, options: DenoiseOptions) -> np.ndarray:
    if options.method == "ai":
        from . import ai as ai_mod

        out = ai_mod.run_ai_denoise(image, options.model_name, options.strength)
        if out is not None:
            return _finish(image, out, options)
        # Fall back to starlet.
        options = DenoiseOptions(
            method="starlet",
            strength=options.strength,
            protect_stars=options.protect_stars,
            scales=options.scales,
            preserve_coarse=options.preserve_coarse,
        )

    if options.method in ("starlet", "wavelet"):
        out = _starlet_denoise(image, options.strength, options.scales, options.preserve_coarse)
    elif options.method == "bilateral":
        out = _bilateral(image, options.strength)
    elif options.method == "nlm":
        out = _nlm(image, options.strength)
    else:
        out = _starlet_denoise(image, options.strength, options.scales, options.preserve_coarse)
    return _finish(image, out, options)


def _finish(original: np.ndarray, denoised: np.ndarray, options: DenoiseOptions) -> np.ndarray:
    if options.protect_stars:
        denoised = _protect_stars(original, denoised)
    return np.clip(denoised, 0.0, 1.0).astype(np.float32)


# --------------------------------------------------------------------------- #
# Starlet (à trous, B3-spline) multiscale denoise
# --------------------------------------------------------------------------- #

_B3 = np.array([1, 4, 6, 4, 1], dtype=np.float32) / 16.0


def _starlet_decompose(image: np.ndarray, scales: int) -> list:
    """Return ``scales + 1`` planes: ``scales`` wavelet planes + 1 residual."""
    from scipy.ndimage import convolve1d

    planes = []
    cur = image.astype(np.float32, copy=True)
    for j in range(scales):
        step = 1 << j  # 1, 2, 4, 8, ...
        kernel = _atrous_kernel(step)
        smoothed = convolve1d(cur, kernel, axis=0, mode="reflect")
        smoothed = convolve1d(smoothed, kernel, axis=1, mode="reflect")
        planes.append(cur - smoothed)
        cur = smoothed
    planes.append(cur)  # coarsest residual
    return planes


def _atrous_kernel(step: int) -> np.ndarray:
    """B3 spline filter with ``step - 1`` zero holes between taps."""
    if step <= 1:
        return _B3
    n = (_B3.size - 1) * step + 1
    out = np.zeros(n, dtype=np.float32)
    out[::step] = _B3
    return out


def _mad_sigma(plane: np.ndarray) -> float:
    return float(np.median(np.abs(plane - np.median(plane)))) * 1.4826 + 1e-12


def _soft_threshold(x: np.ndarray, thr: float) -> np.ndarray:
    return np.sign(x) * np.maximum(np.abs(x) - thr, 0.0)


def _starlet_denoise_2d(
    image: np.ndarray, strength: float, scales: int, preserve_coarse: bool
) -> np.ndarray:
    planes = _starlet_decompose(image, scales=int(max(1, scales)))
    coarse = planes[-1]
    out_planes = []
    # Stronger threshold on fine scales, much lighter on coarse ones.
    for j, p in enumerate(planes[:-1]):
        sigma = _mad_sigma(p)
        # Standard astrophotography choice: 3..5 sigma soft threshold on fine
        # scales, ramping down with scale; modulated by user strength.
        base_k = 3.5 + 1.5 * float(np.clip(strength, 0.0, 1.0))
        k = base_k * (0.5 ** j)  # halve each scale
        thr = k * sigma
        out_planes.append(_soft_threshold(p, thr))
    if not preserve_coarse:
        sigma = _mad_sigma(coarse)
        coarse = _soft_threshold(coarse, 1.0 * sigma * float(np.clip(strength, 0.0, 1.0)))
    return np.sum(np.stack(out_planes, axis=0), axis=0) + coarse


def _starlet_denoise(
    image: np.ndarray, strength: float, scales: int, preserve_coarse: bool
) -> np.ndarray:
    if image.ndim == 3:
        chans = [
            _starlet_denoise_2d(image[..., c], strength, scales, preserve_coarse)
            for c in range(image.shape[2])
        ]
        return np.stack(chans, axis=-1).astype(np.float32)
    return _starlet_denoise_2d(image, strength, scales, preserve_coarse).astype(np.float32)


# --------------------------------------------------------------------------- #
# Legacy methods kept for the UI
# --------------------------------------------------------------------------- #

def _nlm(image: np.ndarray, strength: float) -> np.ndarray:
    h_param = float(np.clip(strength, 0.0, 1.0)) * 0.15 + 0.01
    try:
        from skimage.restoration import denoise_nl_means, estimate_sigma

        if image.ndim == 3:
            sigma = float(np.mean(estimate_sigma(image, channel_axis=-1)))
            return denoise_nl_means(
                image, h=h_param, sigma=sigma, fast_mode=True,
                patch_size=5, patch_distance=6, channel_axis=-1,
            ).astype(np.float32)
        sigma = float(estimate_sigma(image))
        return denoise_nl_means(
            image, h=h_param, sigma=sigma, fast_mode=True,
            patch_size=5, patch_distance=6,
        ).astype(np.float32)
    except Exception:
        return _bilateral(image, strength)


def _bilateral(image: np.ndarray, strength: float) -> np.ndarray:
    try:
        import cv2

        d = max(3, int(5 + strength * 8))
        sigma_color = float(np.clip(strength, 0.0, 1.0)) * 0.5 + 0.05
        sigma_space = float(np.clip(strength, 0.0, 1.0)) * 30 + 5
        if image.ndim == 3:
            chans = [
                cv2.bilateralFilter(image[..., c].astype(np.float32), d, sigma_color, sigma_space)
                for c in range(image.shape[2])
            ]
            return np.stack(chans, axis=-1).astype(np.float32)
        return cv2.bilateralFilter(
            image.astype(np.float32), d, sigma_color, sigma_space
        ).astype(np.float32)
    except Exception:
        from scipy.ndimage import gaussian_filter

        sigma = 0.5 + strength * 1.5
        return gaussian_filter(image.astype(np.float32), sigma=sigma).astype(np.float32)


def _protect_stars(original: np.ndarray, denoised: np.ndarray) -> np.ndarray:
    """Blend back high-frequency star detail using a soft mask of bright peaks."""
    from .stars import detect_star_mask

    mask = detect_star_mask(original)
    if original.ndim == 3 and mask.ndim == 2:
        mask = mask[..., None]
    return denoised * (1.0 - mask) + original * mask
