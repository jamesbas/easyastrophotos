"""ONNX-based AI enhancements (denoise, background extraction, deconvolution).

The actual model files are not bundled. The AI module:
- Detects whether ``onnxruntime`` is installed.
- Detects available execution providers (CUDA/DirectML/CPU).
- Lists ``.onnx`` files in the user's model directory.
- Runs inference with a generic single-input/single-output convention:
    input:  float32 NCHW or NHWC, range [0, 1]
    output: same shape, range [0, 1]

If a model is missing or fails, callers fall back to classical algorithms.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from ..config import DATA_DIR


def _register_nvidia_dll_dirs() -> None:
    """Make the bundled NVIDIA pip-package ``bin`` folders discoverable so
    onnxruntime's CUDA / cuDNN providers can locate their sublibraries
    (e.g. ``cudnn_engines_tensor_ir64_9.dll``).

    Uses both ``os.add_dll_directory`` (for ORT's own LoadLibraryEx calls)
    and a PATH prepend (for cuDNN's internal ``LoadLibraryA`` calls, which
    ignore the user-directory list).
    """
    if os.name != "nt":
        return
    try:
        import nvidia  # type: ignore
    except Exception:
        return
    base = Path(nvidia.__file__).parent
    extra: list[str] = []
    for sub in ("cublas", "cuda_runtime", "cuda_nvrtc", "cudnn", "cufft",
                "curand", "cusolver", "cusparse", "nvjitlink"):
        bin_dir = base / sub / "bin"
        if bin_dir.is_dir():
            sp = str(bin_dir)
            extra.append(sp)
            try:
                os.add_dll_directory(sp)
            except (OSError, AttributeError):
                pass
    if extra:
        os.environ["PATH"] = os.pathsep.join(extra) + os.pathsep + os.environ.get("PATH", "")


_register_nvidia_dll_dirs()

# Resolve the in-repo `models/` folder (sibling of `backend/`) once at import.
_REPO_MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


def models_dir() -> Path:
    """Resolve the directory that holds .onnx model files.

    Resolution order:
      1. ``EAP_MODELS_DIR`` env var, if set.
      2. ``<repo>/models`` if it exists (preferred for local dev / portable installs).
      3. ``<DATA_DIR>/models`` (per-user AppData fallback).
    """
    env = os.environ.get("EAP_MODELS_DIR")
    if env:
        p = Path(env)
    elif _REPO_MODELS_DIR.exists():
        p = _REPO_MODELS_DIR
    else:
        p = DATA_DIR / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_models() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for f in sorted(models_dir().glob("*.onnx")):
        out.append(
            {
                "name": f.stem,
                "filename": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
            }
        )
    return out


def runtime_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {"onnxruntime_available": False, "providers": [], "gpu": False}
    try:
        import onnxruntime as ort  # type: ignore

        info["onnxruntime_available"] = True
        providers = list(ort.get_available_providers())
        info["providers"] = providers
        info["gpu"] = any("CUDA" in p or "DML" in p or "Tensorrt" in p for p in providers)
        info["version"] = ort.__version__
    except Exception as exc:
        info["error"] = str(exc)
    return info


_session_cache: Dict[str, Any] = {}


def _get_session(model_name: str, prefer_gpu: bool = True):
    if not model_name:
        return None
    try:
        import onnxruntime as ort  # type: ignore
    except Exception:
        return None
    # Newer ORT-gpu builds ship a helper that loads the bundled CUDA/cuDNN
    # DLLs from the ``nvidia-*-cu12`` pip packages.  Safe to call repeatedly.
    try:
        preload = getattr(ort, "preload_dlls", None)
        if preload is not None:
            preload()
    except Exception:
        pass
    if model_name in _session_cache:
        return _session_cache[model_name]
    path = models_dir() / (model_name if model_name.endswith(".onnx") else f"{model_name}.onnx")
    if not path.exists():
        return None
    avail = list(ort.get_available_providers())
    providers: List[str] = []
    if prefer_gpu:
        # Order matters: prefer CUDA / DML for normal inference. TensorRT
        # is skipped unless ``EAP_ENABLE_TRT=1`` is set, because it requires
        # a separate TensorRT install (``nvinfer_10.dll``) that most users
        # don't have. Listing it without the runtime triggers a noisy
        # provider-load error on every session creation.
        for p in ("CUDAExecutionProvider", "DmlExecutionProvider"):
            if p in avail:
                providers.append(p)
        if os.environ.get("EAP_ENABLE_TRT") == "1" and "TensorrtExecutionProvider" in avail:
            providers.insert(0, "TensorrtExecutionProvider")
    providers.append("CPUExecutionProvider")
    sess = ort.InferenceSession(str(path), providers=providers)
    _session_cache[model_name] = sess
    return sess


def _run(model_name: str, image: np.ndarray, prefer_gpu: bool = True) -> Optional[np.ndarray]:
    sess = _get_session(model_name, prefer_gpu=prefer_gpu)
    if sess is None:
        return None
    inp = sess.get_inputs()[0]
    out_name = sess.get_outputs()[0].name
    arr = image.astype(np.float32)
    if arr.ndim == 2:
        arr = arr[..., None]
    h, w, c = arr.shape

    shape = list(inp.shape)
    nchw = len(shape) == 4 and (shape[1] in (1, 3, 4) or shape[1] is None)

    # Decide whether to tile. Tile if the image is larger than ~1.5 MP, or
    # if the model declares a fixed spatial size.
    max_side = max(h, w)
    fixed_h = isinstance(shape[2], int) if nchw and len(shape) == 4 else False
    fixed_w = isinstance(shape[3], int) if nchw and len(shape) == 4 else False
    if max_side > 1024 or fixed_h or fixed_w:
        tile = 256
        if nchw and fixed_h and isinstance(shape[2], int):
            tile = int(shape[2])
        return _run_tiled(sess, inp.name, out_name, arr, nchw, tile=tile, overlap=32)

    # Whole-image inference for small frames.
    if nchw:
        x = np.transpose(arr, (2, 0, 1))[None, ...]
    else:
        x = arr[None, ...]
    try:
        out = sess.run([out_name], {inp.name: x})[0]
    except Exception:
        return None
    out = np.squeeze(out)
    if out.ndim == 3 and out.shape[0] in (1, 3, 4):
        out = np.transpose(out, (1, 2, 0))
    if out.ndim == 2 and arr.shape[2] == 1:
        out = out[..., None]
    if out.ndim == 3 and arr.shape[2] == 3 and out.shape[2] == 1:
        out = np.repeat(out, 3, axis=2)
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def _run_tiled(
    sess,
    in_name: str,
    out_name: str,
    arr: np.ndarray,
    nchw: bool,
    tile: int = 256,
    overlap: int = 32,
) -> Optional[np.ndarray]:
    """Run inference on overlapping tiles, blended with a Hann window.

    Handles very large astrophotography frames without OOM on GPUs by
    keeping each forward pass bounded.
    """
    h, w, c = arr.shape
    step = max(1, tile - overlap)
    out = np.zeros_like(arr, dtype=np.float32)
    wsum = np.zeros((h, w), dtype=np.float32)

    # Hann window for smooth blending across tile borders.
    win1d = 0.5 - 0.5 * np.cos(np.linspace(0, 2 * np.pi, tile, endpoint=False, dtype=np.float32))
    window = (win1d[:, None] * win1d[None, :]).astype(np.float32)

    ys = list(range(0, max(1, h - tile + 1), step))
    xs = list(range(0, max(1, w - tile + 1), step))
    if not ys or ys[-1] + tile < h:
        ys.append(max(0, h - tile))
    if not xs or xs[-1] + tile < w:
        xs.append(max(0, w - tile))

    for y0 in ys:
        for x0 in xs:
            y1 = min(h, y0 + tile)
            x1 = min(w, x0 + tile)
            patch = arr[y0:y1, x0:x1, :]
            ph, pw, _ = patch.shape
            # Pad to (tile, tile) by reflecting.
            if ph < tile or pw < tile:
                pad_y = tile - ph
                pad_x = tile - pw
                patch = np.pad(patch, ((0, pad_y), (0, pad_x), (0, 0)), mode="reflect")
            if nchw:
                x_in = np.transpose(patch, (2, 0, 1))[None, ...]
            else:
                x_in = patch[None, ...]
            try:
                y_out = sess.run([out_name], {in_name: x_in})[0]
            except Exception:
                return None
            y_out = np.squeeze(y_out)
            if y_out.ndim == 3 and y_out.shape[0] in (1, 3, 4):
                y_out = np.transpose(y_out, (1, 2, 0))
            if y_out.ndim == 2:
                y_out = y_out[..., None]
            # Crop the padding back off.
            y_out = y_out[:ph, :pw, : arr.shape[2]]
            if y_out.shape[2] == 1 and arr.shape[2] == 3:
                y_out = np.repeat(y_out, 3, axis=2)
            win = window[:ph, :pw]
            out[y0:y1, x0:x1, :] += y_out * win[..., None]
            wsum[y0:y1, x0:x1] += win
    wsum = np.maximum(wsum, 1e-6)
    out = out / wsum[..., None]
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def run_ai_denoise(image: np.ndarray, model_name: Optional[str], strength: float) -> Optional[np.ndarray]:
    if not model_name:
        models = [m["name"] for m in list_models() if "denoise" in m["name"].lower()]
        if not models:
            return None
        model_name = models[0]
    out = _run(model_name, image)
    if out is None:
        return None
    a = float(np.clip(strength, 0.0, 1.0))
    return ((1 - a) * image.astype(np.float32) + a * out).astype(np.float32)


def run_ai_background(image: np.ndarray, model_name: Optional[str]) -> Optional[np.ndarray]:
    if not model_name:
        models = [m["name"] for m in list_models() if "background" in m["name"].lower() or "bg" in m["name"].lower()]
        if not models:
            return None
        model_name = models[0]
    return _run(model_name, image)


def run_ai_decon(image: np.ndarray, model_name: Optional[str], strength: float) -> Optional[np.ndarray]:
    if not model_name:
        models = [m["name"] for m in list_models() if "decon" in m["name"].lower() or "sharp" in m["name"].lower()]
        if not models:
            return None
        model_name = models[0]
    out = _run(model_name, image)
    if out is None:
        return None
    a = float(np.clip(strength, 0.0, 1.0))
    return ((1 - a) * image.astype(np.float32) + a * out).astype(np.float32)
