"""Frame quality analysis (Phase 1: simple star count + sharpness)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .image_io import to_mono


@dataclass
class FrameStats:
    star_count: int
    sharpness: float
    background: float
    noise: float
    score: float


def analyze(image: np.ndarray) -> FrameStats:
    mono = to_mono(image)
    bg = float(np.median(mono))
    noise = float(np.median(np.abs(mono - bg))) * 1.4826  # MAD -> sigma
    threshold = bg + 5.0 * max(noise, 1e-6)

    # Star count via simple peak detection on a downsampled image (fast).
    star_count = _count_peaks(mono, threshold)

    # Sharpness: variance of Laplacian on the mono image.
    sharpness = _laplacian_variance(mono)

    score = _composite_score(star_count, sharpness, noise, bg)
    return FrameStats(
        star_count=int(star_count),
        sharpness=float(sharpness),
        background=float(bg),
        noise=float(noise),
        score=float(score),
    )


def _count_peaks(mono: np.ndarray, threshold: float) -> int:
    try:
        import cv2
    except Exception:
        return 0
    img = mono.astype(np.float32)
    # Top-hat-ish: subtract a smoothed copy to highlight stars.
    blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=3.0)
    high = img - blurred
    mask = (high > (threshold - np.median(img))).astype(np.uint8)
    if mask.sum() == 0:
        return 0
    num, _ = cv2.connectedComponents(mask)
    return max(0, num - 1)


def _laplacian_variance(mono: np.ndarray) -> float:
    try:
        import cv2

        lap = cv2.Laplacian(mono.astype(np.float32), ddepth=cv2.CV_32F, ksize=3)
        return float(lap.var())
    except Exception:
        gx = np.diff(mono, axis=1)
        gy = np.diff(mono, axis=0)
        return float(gx.var() + gy.var())


def _composite_score(stars: int, sharpness: float, noise: float, bg: float) -> float:
    star_term = np.log1p(stars) / 8.0
    sharp_term = np.tanh(sharpness * 50.0)
    noise_penalty = np.tanh(noise * 5.0)
    bg_penalty = np.tanh(bg * 2.0)
    return float(star_term + sharp_term - 0.5 * noise_penalty - 0.25 * bg_penalty)
