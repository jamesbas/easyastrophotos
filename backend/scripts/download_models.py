"""Helper script that *describes* where to get ONNX models for Easy Astro Photos.

Astrophotography-specific ONNX models that are both high quality and free to
redistribute do not really exist as of writing. This script does **not**
download anything by default — it prints the curated list of starting points
so you can fetch the right thing manually.

Usage::

    python scripts/download_models.py            # list options
    python scripts/download_models.py --where    # show where models will be loaded from
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.processing.ai import models_dir  # noqa: E402


SOURCES = [
    (
        "SCUNet (general image denoiser, MIT)",
        "https://github.com/cszn/SCUNet",
        "Convert the PyTorch checkpoint to ONNX with torch.onnx.export, save as "
        "denoise_scunet.onnx.",
    ),
    (
        "DRUNet (general image denoiser, MIT)",
        "https://github.com/cszn/KAIR",
        "Same approach as SCUNet. Save as denoise_drunet.onnx.",
    ),
    (
        "Real-ESRGAN (super-resolution, BSD-3)",
        "https://github.com/xinntao/Real-ESRGAN",
        "Pretrained ONNX exports exist in the community. Useful for upscaling, "
        "not directly used by this app's AI hooks.",
    ),
    (
        "RC-Astro NoiseXTerminator / StarXTerminator / BlurXTerminator",
        "https://www.rc-astro.com",
        "Commercial. Not ONNX. Buy & use inside PixInsight; cannot be loaded here.",
    ),
]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--where", action="store_true", help="Print the resolved models directory and exit.")
    args = p.parse_args()

    target = models_dir()
    print(f"Models directory: {target}")

    if args.where:
        return 0

    print("\nCurated starting points (no auto-download):\n")
    for i, (name, url, note) in enumerate(SOURCES, start=1):
        print(f"  {i}. {name}")
        print(f"     {url}")
        print(f"     {note}\n")

    print("Naming convention picked up by the backend:")
    print("  denoise*.onnx     -> AI denoise")
    print("  background*.onnx  -> AI background extraction")
    print("  decon*.onnx       -> AI deconvolution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
