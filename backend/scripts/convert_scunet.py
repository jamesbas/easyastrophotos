"""Convert SCUNet (cszn et al., Apache 2.0) pretrained weights to ONNX.

SCUNet is a strong general-purpose image denoiser. It is **not** trained on
astrophotography data, but on stretched / non-linear data (after stack +
background extraction) it usually outperforms classical NLM and the starlet
filter on noise grain, especially in color images.

Source repos:
  - Network code: https://github.com/cszn/SCUNet
  - Pretrained checkpoints: https://github.com/cszn/KAIR/releases

Usage (run from ``backend/`` with the project venv active)::

    # torch (pick one):
    pip install torch --index-url https://download.pytorch.org/whl/cu130   # RTX 50xx
    pip install torch --index-url https://download.pytorch.org/whl/cu121   # other NVIDIA
    pip install torch                                                       # CPU-only
    # SCUNet network module + new dynamo ONNX exporter:
    pip install einops timm thop onnxscript
    python scripts/convert_scunet.py
    # produces ../models/denoise_scunet_color.onnx

The exported ONNX model has:
  - input  : float32 NCHW, dynamic N/H/W, 3 channels
  - output : same shape, denoised
  - range  : [0, 1]
  - opset 18 (torch's dynamo exporter; ORT 1.26 handles it natively)

If CUDA wheels of torch fail to install, drop the ``--index-url`` flag to get
the CPU build (export still works, only ONNX inference runs on the GPU later).
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Official SCUNet variants (Apache 2.0). Pick the one you want.
VARIANTS = {
    "color_real_psnr": {
        "weights_url": "https://github.com/cszn/KAIR/releases/download/v1.0/scunet_color_real_psnr.pth",
        "in_channels": 3,
        "out_name": "denoise_scunet_color.onnx",
    },
    "color_real_gan": {
        "weights_url": "https://github.com/cszn/KAIR/releases/download/v1.0/scunet_color_real_gan.pth",
        "in_channels": 3,
        "out_name": "denoise_scunet_color_gan.onnx",
    },
    "gray_25": {
        "weights_url": "https://github.com/cszn/KAIR/releases/download/v1.0/scunet_gray_25.pth",
        "in_channels": 1,
        "out_name": "denoise_scunet_gray.onnx",
    },
}

NETWORK_PY_URL = "https://raw.githubusercontent.com/cszn/SCUNet/main/models/network_scunet.py"


def _ensure_torch():
    try:
        import torch  # noqa: F401
        return
    except Exception:
        pass
    print("torch is not installed. Install it first, e.g.:")
    print("    pip install torch --index-url https://download.pytorch.org/whl/cu121")
    print("    # or for CPU-only:")
    print("    pip install torch")
    sys.exit(2)


def _download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[skip] {dest.name} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
        return
    print(f"[ get] {url}")
    print(f"   -> {dest}")
    with urllib.request.urlopen(url) as r:  # noqa: S310 - trusted GitHub
        data = r.read()
    dest.write_bytes(data)
    print(f"   done ({dest.stat().st_size / 1e6:.1f} MB)")


def _load_network_module(cache_dir: Path):
    """Fetch network_scunet.py from the official SCUNet repo and import it."""
    py = cache_dir / "network_scunet.py"
    _download(NETWORK_PY_URL, py)
    spec = importlib.util.spec_from_file_location("network_scunet", py)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load SCUNet network module")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["network_scunet"] = mod
    spec.loader.exec_module(mod)
    return mod


def convert(variant: str, opset: int = 17) -> Path:
    _ensure_torch()
    import torch

    spec = VARIANTS[variant]
    cache = ROOT / "backend" / ".cache" / "scunet"
    cache.mkdir(parents=True, exist_ok=True)

    net_mod = _load_network_module(cache)
    SCUNet = getattr(net_mod, "SCUNet")  # default config is correct
    net = SCUNet(in_nc=spec["in_channels"], config=[4, 4, 4, 4, 4, 4, 4], dim=64)
    net.eval()

    weights = cache / Path(spec["weights_url"]).name
    _download(spec["weights_url"], weights)

    state = torch.load(weights, map_location="cpu")
    # Some checkpoints wrap the state dict.
    if isinstance(state, dict) and "params" in state:
        state = state["params"]
    net.load_state_dict(state, strict=True)

    dummy = torch.randn(1, spec["in_channels"], 128, 128, dtype=torch.float32)
    out_path = MODELS_DIR / spec["out_name"]
    print(f"[onnx] exporting -> {out_path}")
    torch.onnx.export(
        net,
        dummy,
        out_path.as_posix(),
        input_names=["input"],
        output_names=["output"],
        opset_version=opset,
        dynamic_axes={"input": {0: "n", 2: "h", 3: "w"},
                      "output": {0: "n", 2: "h", 3: "w"}},
        do_constant_folding=True,
    )
    print(f"[ok ] wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")
    return out_path


def smoke_test(onnx_path: Path) -> None:
    try:
        import onnxruntime as ort  # type: ignore
    except Exception:
        print("[skip] onnxruntime not installed, skipping smoke test")
        return
    import numpy as np

    sess = ort.InferenceSession(str(onnx_path), providers=ort.get_available_providers())
    print(f"[test] providers: {sess.get_providers()}")
    n_in = sess.get_inputs()[0]
    c = n_in.shape[1] if isinstance(n_in.shape[1], int) else 3
    x = np.random.default_rng(0).random((1, c, 128, 128), dtype=np.float32)
    y = sess.run([sess.get_outputs()[0].name], {n_in.name: x})[0]
    print(f"[test] in {x.shape} -> out {y.shape}  mean={y.mean():.4f}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--variant", choices=list(VARIANTS), default="color_real_psnr",
                   help="Which SCUNet checkpoint to export.")
    p.add_argument("--opset", type=int, default=17)
    p.add_argument("--no-test", action="store_true")
    args = p.parse_args()
    out = convert(args.variant, opset=args.opset)
    if not args.no_test:
        smoke_test(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
