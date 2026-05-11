"""Image I/O helpers.

Supports FITS, TIFF, PNG, JPEG. Always returns float32 arrays normalized to [0, 1].
For multi-channel data, shape is (H, W, C); for mono data, shape is (H, W).
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np

SUPPORTED_EXTS = {".fit", ".fits", ".fts", ".tif", ".tiff", ".png", ".jpg", ".jpeg"}


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTS


def load_image(path: Path) -> np.ndarray:
    """Load an image file as a float32 array in [0, 1].

    Returns shape (H, W) for mono or (H, W, C) for RGB(A).
    """
    ext = path.suffix.lower()
    if ext in {".fit", ".fits", ".fts"}:
        return _load_fits(path)
    if ext in {".tif", ".tiff"}:
        import tifffile

        arr = tifffile.imread(str(path))
        return _normalize(arr)
    # PNG / JPEG via Pillow
    from PIL import Image

    with Image.open(path) as im:
        im.load()
        if im.mode not in ("L", "I;16", "RGB", "RGBA", "F"):
            im = im.convert("RGB")
        arr = np.asarray(im)
    return _normalize(arr)


def _load_fits(path: Path) -> np.ndarray:
    from astropy.io import fits

    with fits.open(path, memmap=False) as hdul:
        data = None
        for hdu in hdul:
            if hdu.data is not None:
                data = hdu.data
                break
        if data is None:
            raise ValueError(f"No image data found in FITS file: {path}")
    arr = np.asarray(data)
    # FITS may be (C, H, W); reshape to (H, W, C)
    if arr.ndim == 3 and arr.shape[0] in (3, 4) and arr.shape[0] < arr.shape[-1]:
        arr = np.moveaxis(arr, 0, -1)
    return _normalize(arr)


def _normalize(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr)
    if arr.dtype == np.uint8:
        out = arr.astype(np.float32) / 255.0
    elif arr.dtype == np.uint16:
        out = arr.astype(np.float32) / 65535.0
    elif arr.dtype == np.int16:
        out = (arr.astype(np.float32) + 32768.0) / 65535.0
    elif arr.dtype in (np.float32, np.float64):
        out = arr.astype(np.float32)
        m = float(out.max()) if out.size else 1.0
        if m > 1.5:  # likely 0..65535 floats from FITS
            out = out / m
        out = np.clip(out, 0.0, 1.0)
    else:
        out = arr.astype(np.float32)
        m = float(out.max()) if out.size else 1.0
        if m > 0:
            out = out / m
    return out.astype(np.float32, copy=False)


def to_mono(arr: np.ndarray) -> np.ndarray:
    """Convert to single channel using a luminance approximation."""
    if arr.ndim == 2:
        return arr
    if arr.shape[-1] == 1:
        return arr[..., 0]
    rgb = arr[..., :3]
    weights = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    return (rgb * weights).sum(axis=-1)


def image_shape(arr: np.ndarray) -> Tuple[int, int, int]:
    if arr.ndim == 2:
        return arr.shape[0], arr.shape[1], 1
    return arr.shape[0], arr.shape[1], arr.shape[2]


def save_png(path: Path, arr: np.ndarray) -> None:
    from PIL import Image

    data = np.clip(arr, 0.0, 1.0)
    data = (data * 255.0 + 0.5).astype(np.uint8)
    if data.ndim == 2:
        Image.fromarray(data, mode="L").save(path)
    else:
        if data.shape[-1] == 4:
            Image.fromarray(data, mode="RGBA").save(path)
        else:
            Image.fromarray(data[..., :3], mode="RGB").save(path)


def save_tiff(path: Path, arr: np.ndarray, bits: int = 16) -> None:
    import tifffile

    data = np.clip(arr, 0.0, 1.0)
    if bits == 16:
        data = (data * 65535.0 + 0.5).astype(np.uint16)
    else:
        data = (data * 255.0 + 0.5).astype(np.uint8)
    tifffile.imwrite(str(path), data)


def save_fits(path: Path, arr: np.ndarray) -> None:
    from astropy.io import fits

    data = np.clip(arr, 0.0, 1.0).astype(np.float32)
    if data.ndim == 3:
        data = np.moveaxis(data, -1, 0)
    fits.PrimaryHDU(data).writeto(path, overwrite=True)
