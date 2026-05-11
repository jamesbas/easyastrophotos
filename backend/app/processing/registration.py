"""Image registration / alignment.

Uses astroalign for star-based asterism matching. Falls back to OpenCV ECC if
astroalign cannot find a transform.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from .image_io import to_mono


def align_to_reference(
    source: np.ndarray, reference: np.ndarray
) -> Optional[np.ndarray]:
    """Align ``source`` onto ``reference``. Returns aligned image or None on failure."""
    src_mono = to_mono(source).astype(np.float32)
    ref_mono = to_mono(reference).astype(np.float32)

    transform = _estimate_transform(src_mono, ref_mono)
    if transform is None:
        return None

    return _warp(source, transform, ref_mono.shape)


def _estimate_transform(src: np.ndarray, ref: np.ndarray):
    try:
        import astroalign as aa

        transform, _ = aa.find_transform(src, ref, max_control_points=50)
        return ("affine", np.asarray(transform.params, dtype=np.float64))
    except Exception:
        pass
    # ECC fallback (translation only).
    try:
        import cv2

        warp = np.eye(2, 3, dtype=np.float32)
        criteria = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            200,
            1e-5,
        )
        _, warp = cv2.findTransformECC(
            ref.astype(np.float32),
            src.astype(np.float32),
            warp,
            cv2.MOTION_TRANSLATION,
            criteria,
            None,
            5,
        )
        affine = np.eye(3, dtype=np.float64)
        affine[:2, :] = warp
        return ("affine", affine)
    except Exception:
        return None


def _warp(image: np.ndarray, transform, out_shape):
    import cv2

    kind, matrix = transform
    h, w = out_shape
    affine = matrix[:2, :].astype(np.float32)
    flags = cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP * 0  # forward map
    if image.ndim == 2:
        return cv2.warpAffine(image, affine, (w, h), flags=cv2.INTER_LINEAR)
    channels = [
        cv2.warpAffine(image[..., c], affine, (w, h), flags=cv2.INTER_LINEAR)
        for c in range(image.shape[-1])
    ]
    return np.stack(channels, axis=-1)
