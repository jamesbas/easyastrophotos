"""Color calibration and palette mapping."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Optional

import numpy as np


@dataclass
class ColorOptions:
    mode: Literal["natural_rgb", "sho", "hoo", "custom"] = "natural_rgb"
    saturation: float = 0.0  # -1..1
    green_reduction: float = 0.0  # 0..1, SCNR strength
    background_neutralization: bool = True
    preserve_star_color: bool = True
    # Channel mapping for custom / SHO / HOO. Values are channel indices into a
    # multi-channel input (or named keys when channels dict is provided).
    channel_map: Dict[str, str] = field(default_factory=dict)


def apply_color(
    image: np.ndarray,
    options: ColorOptions,
    channels: Optional[Dict[str, np.ndarray]] = None,
) -> np.ndarray:
    """Apply a color workflow to ``image``.

    If ``channels`` is provided (e.g. {"ha": arr, "sii": arr, "oiii": arr}),
    SHO/HOO/custom modes use those mono channels; otherwise the function
    operates on ``image`` directly.
    """
    if options.mode in ("sho", "hoo", "custom") and channels:
        rgb = _palette_combine(channels, options)
    else:
        rgb = _ensure_rgb(image)

    if options.background_neutralization:
        rgb = neutralize_background(rgb)
    if options.mode == "natural_rgb":
        rgb = white_balance(rgb)
    if options.green_reduction > 0:
        rgb = scnr_green(rgb, amount=float(options.green_reduction))
    if options.saturation != 0.0:
        rgb = adjust_saturation(rgb, amount=float(options.saturation))

    return np.clip(rgb, 0.0, 1.0).astype(np.float32)


def _ensure_rgb(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return np.stack([image, image, image], axis=-1).astype(np.float32)
    if image.shape[-1] == 1:
        c = image[..., 0]
        return np.stack([c, c, c], axis=-1).astype(np.float32)
    if image.shape[-1] >= 3:
        return image[..., :3].astype(np.float32)
    return image.astype(np.float32)


def _palette_combine(channels: Dict[str, np.ndarray], options: ColorOptions) -> np.ndarray:
    if options.mode == "sho":
        mapping = {"r": "sii", "g": "ha", "b": "oiii"}
    elif options.mode == "hoo":
        mapping = {"r": "ha", "g": "oiii", "b": "oiii"}
    else:
        mapping = {k: options.channel_map.get(k, k) for k in ("r", "g", "b")}

    def _ch(name: str) -> np.ndarray:
        arr = channels.get(name)
        if arr is None:
            # Fall back to first available channel
            arr = next(iter(channels.values()))
        if arr.ndim == 3:
            arr = arr.mean(axis=-1)
        return arr.astype(np.float32)

    r = _ch(mapping["r"])
    g = _ch(mapping["g"])
    b = _ch(mapping["b"])
    h = min(r.shape[0], g.shape[0], b.shape[0])
    w = min(r.shape[1], g.shape[1], b.shape[1])
    return np.stack([r[:h, :w], g[:h, :w], b[:h, :w]], axis=-1)


def neutralize_background(rgb: np.ndarray) -> np.ndarray:
    """Subtract the per-channel background median so the sky is gray."""
    out = rgb.astype(np.float32).copy()
    bg = [float(np.median(out[..., c])) for c in range(out.shape[-1])]
    target = float(np.min(bg))
    for c in range(out.shape[-1]):
        out[..., c] = out[..., c] - (bg[c] - target)
    return np.clip(out, 0.0, 1.0)


def white_balance(rgb: np.ndarray) -> np.ndarray:
    """Simple gray-world white balance using the bright (star) population."""
    out = rgb.astype(np.float32).copy()
    # Use the upper percentile pixels (likely stars) for balancing.
    flat = out.reshape(-1, out.shape[-1])
    thr = np.percentile(flat, 99.0, axis=0)
    mask = (flat >= thr).all(axis=-1)
    if not mask.any():
        return out
    means = flat[mask].mean(axis=0)
    target = float(np.mean(means))
    scale = target / np.maximum(means, 1e-6)
    out = out * scale
    return np.clip(out, 0.0, 1.0)


def scnr_green(rgb: np.ndarray, amount: float) -> np.ndarray:
    """Subtractive Chromatic Noise Reduction on the green channel.

    Reduces the green excess that is characteristic of Hubble palettes and
    aggressive saturation boosts.
    """
    out = rgb.astype(np.float32).copy()
    r = out[..., 0]
    g = out[..., 1]
    b = out[..., 2]
    avg_rb = 0.5 * (r + b)
    new_g = np.minimum(g, avg_rb)
    out[..., 1] = (1.0 - amount) * g + amount * new_g
    return np.clip(out, 0.0, 1.0)


def adjust_saturation(rgb: np.ndarray, amount: float) -> np.ndarray:
    """Saturation in [-1, 1]. 0 = no change."""
    out = rgb.astype(np.float32)
    luma = (0.2126 * out[..., 0] + 0.7152 * out[..., 1] + 0.0722 * out[..., 2])[..., None]
    factor = 1.0 + float(amount)
    return np.clip(luma + (out - luma) * factor, 0.0, 1.0)


def photometric_color_calibration_placeholder(image: np.ndarray) -> np.ndarray:
    """Phase 4 stub. Real photometric calibration requires plate-solving.

    For now, performs a robust per-channel histogram match toward the green
    channel (which is closest to luminance for sensors with Bayer arrays). This
    gives a more visually neutral starting point than no calibration at all.
    """
    rgb = _ensure_rgb(image)
    g = rgb[..., 1]
    out = rgb.copy()
    for c in (0, 2):
        chan = out[..., c]
        ratio = float(np.median(g)) / max(float(np.median(chan)), 1e-6)
        out[..., c] = np.clip(chan * ratio, 0.0, 1.0)
    return out
