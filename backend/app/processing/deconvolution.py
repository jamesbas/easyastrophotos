"""Deconvolution / sharpening with PSF auto-estimation.

Pipeline (Richardson-Lucy, default):
1. Auto-detect bright unsaturated stars in the image.
2. Stack small windows around each, recentered to sub-pixel accuracy by
   centroiding, and average them to build an empirical PSF.
3. Optionally fall back to a fitted 2D Gaussian when too few stars exist.
4. Run regularized Richardson-Lucy with mild total-variation damping to
   suppress ringing around bright stars.

Other methods kept for compatibility: ``wiener``, ``unsharp``, ``ai``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple

import numpy as np

from .image_io import to_mono


@dataclass
class DeconvolutionOptions:
    method: Literal["richardson_lucy", "wiener", "unsharp", "ai"] = "richardson_lucy"
    strength: float = 0.5  # 0..1, blend amount
    fwhm: float = 0.0  # px, 0 = auto-estimate from stars
    iterations: int = 20
    star_mode: bool = False  # use a tight PSF and more iterations on star regions
    protect_ringing: bool = True
    tv_lambda: float = 0.002  # total-variation regularization weight (RL only)
    model_name: Optional[str] = None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def deconvolve(image: np.ndarray, options: DeconvolutionOptions) -> np.ndarray:
    if options.method == "ai":
        from . import ai as ai_mod

        out = ai_mod.run_ai_decon(image, options.model_name, options.strength)
        if out is not None:
            return np.clip(out, 0.0, 1.0).astype(np.float32)
        options = DeconvolutionOptions(
            method="richardson_lucy",
            strength=options.strength,
            fwhm=options.fwhm,
            iterations=options.iterations,
            star_mode=options.star_mode,
            tv_lambda=options.tv_lambda,
            protect_ringing=options.protect_ringing,
        )

    fwhm = options.fwhm
    psf: np.ndarray
    if fwhm and fwhm > 0:
        psf = _gaussian_psf(fwhm)
        est_fwhm = fwhm
    else:
        psf, est_fwhm = estimate_psf(image)

    if options.star_mode:
        # Slightly tighter PSF + more iterations for star tightening.
        psf = _gaussian_psf(max(1.2, est_fwhm * 0.85))
        iters = max(options.iterations, 30)
    else:
        iters = max(5, options.iterations)

    if options.method == "wiener":
        out = _wiener(image, psf)
    elif options.method == "unsharp":
        out = _unsharp(image, options.strength, est_fwhm)
    else:
        out = _richardson_lucy_tv(image, psf, iterations=iters, tv_lambda=options.tv_lambda)

    blended = (1.0 - options.strength) * image + options.strength * out
    if options.protect_ringing:
        blended = _suppress_ringing(image, blended)
    return np.clip(blended, 0.0, 1.0).astype(np.float32)


# --------------------------------------------------------------------------- #
# PSF estimation
# --------------------------------------------------------------------------- #

def estimate_psf(
    image: np.ndarray, max_stars: int = 60, half_size: int = 8
) -> Tuple[np.ndarray, float]:
    """Build an empirical PSF by stacking centered windows around bright stars.

    Returns ``(psf, fwhm_px)``. Falls back to a fitted Gaussian if too few
    stars are usable.
    """
    from .stars import detect_stars

    mono = to_mono(image).astype(np.float32)
    h, w = mono.shape

    stars = detect_stars(image)
    # Sort brightest-first and skip likely-saturated ones (top 1%).
    if not stars:
        return _gaussian_psf(3.0), 3.0

    stars = sorted(stars, key=lambda s: -s[2])
    sat_cut = float(np.percentile(mono, 99.8))
    stack = []
    for (cy, cx, _b) in stars:
        if len(stack) >= max_stars:
            break
        y0 = cy - half_size
        x0 = cx - half_size
        y1 = cy + half_size + 1
        x1 = cx + half_size + 1
        if y0 < 0 or x0 < 0 or y1 > h or x1 > w:
            continue
        patch = mono[y0:y1, x0:x1]
        if float(patch.max()) >= sat_cut:
            continue
        sub = _recenter_subpixel(patch)
        if sub is None:
            continue
        # Normalize each star to its sum so faint stars contribute equally.
        s = float(sub.sum())
        if s <= 0:
            continue
        stack.append(sub / s)

    if len(stack) < 5:
        # Fit a 2D Gaussian to the brightest unsaturated star as a fallback.
        return _gaussian_psf(3.0), 3.0

    psf = np.median(np.stack(stack, axis=0), axis=0).astype(np.float32)
    # Background subtract and renormalize.
    psf = np.clip(psf - float(np.median(psf)), 0.0, None)
    if psf.sum() <= 0:
        return _gaussian_psf(3.0), 3.0
    psf = psf / psf.sum()
    fwhm = _estimate_fwhm_from_psf(psf)
    return psf, fwhm


def _recenter_subpixel(patch: np.ndarray) -> Optional[np.ndarray]:
    """Shift the patch so its centroid sits on the central pixel."""
    p = patch.astype(np.float32)
    bg = float(np.median(p))
    q = np.clip(p - bg, 0.0, None)
    total = float(q.sum())
    if total <= 0:
        return None
    yy, xx = np.mgrid[: p.shape[0], : p.shape[1]].astype(np.float32)
    cy = float((yy * q).sum() / total)
    cx = float((xx * q).sum() / total)
    sy = (p.shape[0] - 1) / 2.0 - cy
    sx = (p.shape[1] - 1) / 2.0 - cx
    try:
        from scipy.ndimage import shift

        return shift(p, (sy, sx), order=3, mode="reflect").astype(np.float32)
    except Exception:
        return p


def _estimate_fwhm_from_psf(psf: np.ndarray) -> float:
    """Estimate FWHM (in pixels) of the empirical PSF."""
    h, w = psf.shape
    cy, cx = h // 2, w // 2
    peak = float(psf[cy, cx])
    if peak <= 0:
        return 3.0
    half = peak / 2.0
    # Sample radii out to the edge and find the radius where the radial
    # average drops below half-max.
    r_vals = np.arange(min(cy, cx))
    yy, xx = np.indices(psf.shape)
    rr = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    radial = np.array([psf[(rr >= r) & (rr < r + 1)].mean() for r in r_vals])
    below = np.where(radial < half)[0]
    if below.size == 0:
        return 3.0
    r_half = float(below[0])
    return float(max(1.5, 2.0 * r_half))


def _gaussian_psf(fwhm: float) -> np.ndarray:
    sigma = max(0.5, fwhm) / 2.3548
    radius = max(3, int(3 * sigma))
    y, x = np.mgrid[-radius : radius + 1, -radius : radius + 1]
    psf = np.exp(-(x * x + y * y) / (2 * sigma * sigma))
    psf /= psf.sum()
    return psf.astype(np.float32)


# --------------------------------------------------------------------------- #
# Regularized Richardson-Lucy
# --------------------------------------------------------------------------- #

def _richardson_lucy_tv(
    image: np.ndarray, psf: np.ndarray, iterations: int, tv_lambda: float
) -> np.ndarray:
    """RL with mild total-variation regularization (TV-RL).

    See Dey et al. 2006 — adds a TV prior term that suppresses oscillations
    around bright features without blurring real edges.
    """
    if image.ndim == 3:
        chans = [
            _rl_tv_2d(image[..., c], psf, iterations, tv_lambda)
            for c in range(image.shape[2])
        ]
        return np.stack(chans, axis=-1).astype(np.float32)
    return _rl_tv_2d(image, psf, iterations, tv_lambda).astype(np.float32)


def _rl_tv_2d(image: np.ndarray, psf: np.ndarray, iterations: int, tv_lambda: float) -> np.ndarray:
    from scipy.signal import fftconvolve

    eps = 1e-7
    psf_mirror = psf[::-1, ::-1]
    est = image.astype(np.float32, copy=True).clip(eps, None)
    obs = image.astype(np.float32).clip(0, None)

    for _ in range(int(iterations)):
        denom = fftconvolve(est, psf, mode="same") + eps
        ratio = obs / denom
        correction = fftconvolve(ratio, psf_mirror, mode="same")
        if tv_lambda > 0:
            div_g = _tv_divergence(est)
            tv_factor = 1.0 / (1.0 - tv_lambda * div_g + eps)
            est = est * correction * tv_factor
        else:
            est = est * correction
        est = np.clip(est, 0.0, 1.0)
    return est


def _tv_divergence(img: np.ndarray) -> np.ndarray:
    """div( grad(u) / |grad(u)| ) — the standard TV regularizer."""
    eps = 1e-6
    gy = np.diff(img, axis=0, prepend=img[:1])
    gx = np.diff(img, axis=1, prepend=img[:, :1])
    mag = np.sqrt(gy * gy + gx * gx + eps)
    ny = gy / mag
    nx = gx / mag
    dyy = np.diff(ny, axis=0, append=ny[-1:])
    dxx = np.diff(nx, axis=1, append=nx[:, -1:])
    return (dyy + dxx).astype(np.float32)


# --------------------------------------------------------------------------- #
# Wiener / unsharp
# --------------------------------------------------------------------------- #

def _wiener(image: np.ndarray, psf: np.ndarray) -> np.ndarray:
    try:
        from skimage.restoration import wiener

        if image.ndim == 3:
            chans = [wiener(image[..., c], psf, balance=0.05) for c in range(image.shape[2])]
            return np.stack(chans, axis=-1).astype(np.float32)
        return wiener(image, psf, balance=0.05).astype(np.float32)
    except Exception:
        return _unsharp(image, 0.7, fwhm=psf.shape[0] / 3.0)


def _unsharp(image: np.ndarray, strength: float, fwhm: float) -> np.ndarray:
    try:
        import cv2

        sigma = max(0.5, fwhm) / 2.3548
        if image.ndim == 3:
            chans = []
            for c in range(image.shape[2]):
                blur = cv2.GaussianBlur(image[..., c], (0, 0), sigmaX=sigma)
                chans.append(image[..., c] + strength * (image[..., c] - blur))
            return np.stack(chans, axis=-1).astype(np.float32)
        blur = cv2.GaussianBlur(image, (0, 0), sigmaX=sigma)
        return (image + strength * (image - blur)).astype(np.float32)
    except Exception:
        return image.astype(np.float32)


def _suppress_ringing(original: np.ndarray, sharpened: np.ndarray) -> np.ndarray:
    diff = sharpened - original
    cap = float(np.std(diff)) * 3.0 + 1e-6
    return original + np.clip(diff, -cap, cap)
