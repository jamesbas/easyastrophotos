"""Star detection, mask generation, and star reduction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from .image_io import to_mono


@dataclass
class StarOptions:
    threshold_sigma: float = 4.0
    min_radius: int = 2
    max_radius: int = 12
    softness: float = 1.5  # gaussian blur on the mask


def detect_star_mask(image: np.ndarray, options: StarOptions = StarOptions()) -> np.ndarray:
    """Return a soft star mask in [0, 1] at the input image's resolution."""
    mono = to_mono(image).astype(np.float32)
    bg = float(np.median(mono))
    sd = float(np.median(np.abs(mono - bg))) * 1.4826 + 1e-6
    threshold = bg + options.threshold_sigma * sd

    try:
        import cv2

        blur = cv2.GaussianBlur(mono, (0, 0), sigmaX=2.0)
        peaks = (mono - blur) > (threshold - bg) * 0.5
        peaks = peaks & (mono > threshold)
        mask = peaks.astype(np.float32)
        # Dilate to roughly cover star disks.
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.dilate(mask, kernel, iterations=2)
        mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=options.softness)
    except Exception:
        mask = (mono > threshold).astype(np.float32)
    m = float(mask.max())
    if m > 0:
        mask = mask / m
    return mask.astype(np.float32)


def detect_stars(image: np.ndarray, options: StarOptions = StarOptions()) -> List[Tuple[int, int, float]]:
    """Return a list of (y, x, brightness) for detected stars."""
    mono = to_mono(image).astype(np.float32)
    bg = float(np.median(mono))
    sd = float(np.median(np.abs(mono - bg))) * 1.4826 + 1e-6
    thr = bg + options.threshold_sigma * sd
    try:
        import cv2

        mask = (mono > thr).astype(np.uint8)
        num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
        out: List[Tuple[int, int, float]] = []
        for i in range(1, num):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < (options.min_radius ** 2) or area > (options.max_radius ** 2) * 4:
                continue
            cy, cx = centroids[i]
            out.append((int(cy), int(cx), float(mono[int(cy), int(cx)])))
        return out
    except Exception:
        return []


def reduce_stars(image: np.ndarray, amount: float = 0.5) -> np.ndarray:
    """Approximate star reduction: subtract a fraction of the star mask intensity."""
    mask = detect_star_mask(image)
    if image.ndim == 3:
        mask3 = mask[..., None]
    else:
        mask3 = mask
    # Blur the image a little to estimate the local non-star background.
    try:
        import cv2

        bg = cv2.GaussianBlur(image.astype(np.float32), (0, 0), sigmaX=2.5)
    except Exception:
        bg = image.astype(np.float32)
    star_excess = np.maximum(image.astype(np.float32) - bg, 0.0)
    out = image.astype(np.float32) - amount * star_excess * mask3
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def starless_preview(image: np.ndarray) -> np.ndarray:
    """Cheap starless approximation by aggressive star reduction + median fill."""
    base = reduce_stars(image, amount=0.95)
    try:
        import cv2

        if base.ndim == 3:
            chans = [cv2.medianBlur(base[..., c].astype(np.float32), 5) for c in range(base.shape[2])]
            return np.clip(np.stack(chans, axis=-1), 0, 1).astype(np.float32)
        return np.clip(cv2.medianBlur(base.astype(np.float32), 5), 0, 1).astype(np.float32)
    except Exception:
        return base
