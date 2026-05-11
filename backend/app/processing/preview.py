"""Thumbnail generation."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .image_io import save_png
from .stretch import auto_stretch


def make_thumbnail(image: np.ndarray, out_path: Path, max_dim: int = 320) -> None:
    h, w = image.shape[:2]
    scale = min(1.0, float(max_dim) / max(h, w))
    if scale < 1.0:
        try:
            import cv2

            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            small = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        except Exception:
            step = max(1, int(1.0 / scale))
            small = image[::step, ::step]
    else:
        small = image
    stretched = auto_stretch(small, method="asinh")
    save_png(out_path, stretched)


def make_preview(image: np.ndarray, out_path: Path, max_dim: int = 1600) -> None:
    h, w = image.shape[:2]
    scale = min(1.0, float(max_dim) / max(h, w))
    if scale < 1.0:
        try:
            import cv2

            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            small = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        except Exception:
            step = max(1, int(1.0 / scale))
            small = image[::step, ::step]
    else:
        small = image
    save_png(out_path, np.clip(small, 0.0, 1.0))
