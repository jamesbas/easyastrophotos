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


def _estimate_star_radius(image: np.ndarray) -> float:
    """Estimate a representative star radius (px) from the brightest few stars.

    Falls back to ``3.0`` if star detection finds nothing usable.
    """
    try:
        stars = detect_stars(image)
    except Exception:
        return 3.0
    if not stars:
        return 3.0
    mono = to_mono(image).astype(np.float32)
    bg = float(np.median(mono))
    sd = float(np.median(np.abs(mono - bg))) * 1.4826 + 1e-6
    half_max_targets = []
    # Use the top ~30 brightest detections.
    for y, x, _b in sorted(stars, key=lambda s: -s[2])[:30]:
        peak = mono[y, x]
        half = bg + (peak - bg) * 0.5
        # Walk outward in 4 directions until we drop below half-max.
        r_est = []
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            r = 0
            for k in range(1, 12):
                yy, xx = y + dy * k, x + dx * k
                if yy < 0 or xx < 0 or yy >= mono.shape[0] or xx >= mono.shape[1]:
                    break
                if mono[yy, xx] < half:
                    r = k
                    break
            if r:
                r_est.append(r)
        if r_est:
            half_max_targets.append(float(np.mean(r_est)))
    if not half_max_targets:
        return 3.0
    # 75th percentile catches bloomed stars without being dragged down by tight ones.
    return float(np.clip(np.percentile(half_max_targets, 75), 2.0, 12.0))


def reduce_stars(image: np.ndarray, amount: float = 0.5) -> np.ndarray:
    """Reduce star prominence without erasing nebula / galaxy structure.

    Strategy:
      1. Detect a soft star mask.
      2. Estimate the star half-width radius from the brightest stars and
         build a background estimate by Gaussian-blurring at ~2x that
         radius. This captures the whole PSF (peak + halo wings), not just
         the tight peak.
      3. Subtract ``amount * (image - bg)`` inside the mask.
      4. At ``amount >= 0.7`` apply an additional ``amount``-scaled
         multiplicative pull-down on the masked region to flatten bright
         saturated cores that the subtraction alone can't reach.
    """
    mask = detect_star_mask(image)
    if image.ndim == 3:
        mask3 = mask[..., None]
    else:
        mask3 = mask

    # Background = the image with stars smoothed away.
    radius_px = _estimate_star_radius(image)
    sigma = max(3.0, radius_px * 2.0)
    try:
        import cv2

        bg = cv2.GaussianBlur(image.astype(np.float32), (0, 0), sigmaX=sigma)
    except Exception:
        bg = image.astype(np.float32)

    star_excess = np.maximum(image.astype(np.float32) - bg, 0.0)
    out = image.astype(np.float32) - amount * star_excess * mask3

    # Saturated cores can't be reached by simple subtraction; gently pull
    # them down once amount goes above ~0.7. At amount=1 this removes ~20%
    # of the remaining intensity inside the star mask.
    if amount > 0.7:
        pull = (amount - 0.7) / 0.3  # 0..1
        out = out * (1.0 - 0.2 * pull * mask3)

    return np.clip(out, 0.0, 1.0).astype(np.float32)


def starless_preview(image: np.ndarray) -> np.ndarray:
    """Cheap starless approximation: very strong star reduction + median fill."""
    base = reduce_stars(image, amount=1.0)
    try:
        import cv2

        if base.ndim == 3:
            chans = [cv2.medianBlur(base[..., c].astype(np.float32), 5) for c in range(base.shape[2])]
            return np.clip(np.stack(chans, axis=-1), 0, 1).astype(np.float32)
        return np.clip(cv2.medianBlur(base.astype(np.float32), 5), 0, 1).astype(np.float32)
    except Exception:
        return base
