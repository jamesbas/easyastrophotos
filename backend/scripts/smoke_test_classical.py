"""Smoke tests for the upgraded classical pipeline.

Generates a synthetic frame (faint Gaussian blob + stars + gradient + noise),
runs background extraction, denoise, and deconvolution, and reports basic
sanity metrics (no exceptions, output in [0,1], finite, expected shape).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from app.processing import background as bg_mod
from app.processing import denoise as dn_mod
from app.processing import deconvolution as dc_mod


def synth(h=512, w=512, seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.full((h, w), 0.02, dtype=np.float32)
    # Light pollution gradient
    yy, xx = np.mgrid[0:h, 0:w]
    img += 0.08 * (xx / w) + 0.04 * (yy / h)
    # Nebula blob
    cy, cx = h // 2, w // 2
    sigma_neb = h / 6.0
    neb = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma_neb ** 2))
    img += 0.25 * neb
    # Stars
    for _ in range(120):
        sy, sx = rng.integers(8, h - 8), rng.integers(8, w - 8)
        bright = rng.uniform(0.2, 0.8)
        # blur via additive 3x3 gaussian-ish
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                d2 = dy * dy + dx * dx
                img[sy + dy, sx + dx] += bright * np.exp(-d2 / 2.0)
    img = np.clip(img, 0, 1)
    # Convolve with a small Gaussian to give stars FWHM ~3
    from scipy.ndimage import gaussian_filter
    img = gaussian_filter(img, sigma=1.3)
    # Add noise
    img += rng.normal(0, 0.015, img.shape).astype(np.float32)
    return np.clip(img, 0, 1).astype(np.float32)


def check(name, arr, expected_shape):
    assert arr.shape == expected_shape, f"{name}: shape {arr.shape} != {expected_shape}"
    assert np.isfinite(arr).all(), f"{name}: non-finite values"
    assert arr.min() >= 0 and arr.max() <= 1.0001, f"{name}: out of range [{arr.min()}, {arr.max()}]"
    print(f"  OK  {name}: shape={arr.shape} mean={arr.mean():.4f} std={arr.std():.4f}")


def main():
    img = synth()
    print(f"Input: shape={img.shape} mean={img.mean():.4f} std={img.std():.4f}")

    print("\n[Background] Abe-style RBF")
    out, model = bg_mod.remove_background(img, bg_mod.BackgroundOptions(method="rbf"))
    check("background-removed", out, img.shape)
    check("bg-model", model, img.shape)

    print("\n[Background] Polynomial")
    out2, _ = bg_mod.remove_background(img, bg_mod.BackgroundOptions(method="polynomial", degree=3))
    check("poly-removed", out2, img.shape)

    print("\n[Denoise] Starlet")
    dn = dn_mod.denoise(img, dn_mod.DenoiseOptions(method="starlet", strength=0.5))
    check("starlet", dn, img.shape)

    print("\n[Denoise] NLM (legacy)")
    dn2 = dn_mod.denoise(img, dn_mod.DenoiseOptions(method="nlm", strength=0.4))
    check("nlm", dn2, img.shape)

    print("\n[Deconvolution] Empirical PSF + TV-RL")
    psf, fwhm = dc_mod.estimate_psf(img)
    print(f"  estimated PSF: shape={psf.shape}  FWHM={fwhm:.2f}px  sum={psf.sum():.4f}")
    dc = dc_mod.deconvolve(img, dc_mod.DeconvolutionOptions(method="richardson_lucy", strength=0.5, iterations=12))
    check("rl-tv", dc, img.shape)

    print("\n[Deconvolution] Star tightening mode")
    dc2 = dc_mod.deconvolve(img, dc_mod.DeconvolutionOptions(method="richardson_lucy", strength=0.4, star_mode=True, iterations=20))
    check("rl-star-mode", dc2, img.shape)

    # 3-channel test
    print("\n[3-channel] full chain")
    rgb = np.stack([img, img * 0.95 + 0.01, img * 0.9 + 0.02], axis=-1)
    rgb = np.clip(rgb, 0, 1).astype(np.float32)
    rgb_bg, _ = bg_mod.remove_background(rgb, bg_mod.BackgroundOptions())
    check("rgb-bg", rgb_bg, rgb.shape)
    rgb_dn = dn_mod.denoise(rgb_bg, dn_mod.DenoiseOptions(method="starlet", strength=0.4))
    check("rgb-denoise", rgb_dn, rgb.shape)
    rgb_dc = dc_mod.deconvolve(rgb_dn, dc_mod.DeconvolutionOptions(method="richardson_lucy", strength=0.4, iterations=10))
    check("rgb-decon", rgb_dc, rgb.shape)

    print("\nAll smoke tests passed.")


if __name__ == "__main__":
    main()
