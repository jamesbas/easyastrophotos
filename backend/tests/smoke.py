"""Quick smoke test of the processing pipeline using synthetic star fields.

Run from the backend folder:
    python -m tests.smoke
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from app.processing import registration, stacking, stretch
from app.processing.image_io import save_png


def synthetic_frame(seed: int, dx: int = 0, dy: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    h, w = 256, 256
    img = rng.normal(0.05, 0.01, (h, w)).astype(np.float32)
    # Plant a fixed star pattern, shifted by (dx, dy).
    stars = rng.integers(0, [h, w], size=(40, 2))
    for sy, sx in stars:
        ny, nx = sy + dy, sx + dx
        if 0 <= ny < h and 0 <= nx < w:
            img[ny, nx] += 0.9
    # Blur to make stars round-ish.
    try:
        import cv2

        img = cv2.GaussianBlur(img, (0, 0), 1.4)
    except Exception:
        pass
    return np.clip(img, 0.0, 1.0)


def main() -> None:
    ref = synthetic_frame(seed=1)
    frames = [ref]
    for i in range(2, 8):
        frames.append(synthetic_frame(seed=1, dx=(i - 4) * 2, dy=(i - 4) * 1))

    aligned = [ref]
    for f in frames[1:]:
        warped = registration.align_to_reference(f, ref)
        aligned.append(warped if warped is not None else f)

    stacked = stacking.stack(aligned, method="average")
    stretched = stretch.auto_stretch(stacked, method="asinh")

    out = Path(tempfile.gettempdir()) / "eap-smoke-stretched.png"
    save_png(out, stretched)
    print(f"OK: stacked {len(aligned)} synthetic frames, wrote {out}")


if __name__ == "__main__":
    main()
