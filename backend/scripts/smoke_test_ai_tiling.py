"""Verify the tiled AI inference path with a tiny synthetic ONNX model.

Builds a 1-layer identity-ish ONNX model (3x3 average blur), drops it into
the models/ folder, then calls processing.ai.run_ai_denoise on a 2000x1500
image to ensure tiling + Hann blending produce a sensible result.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from app.processing import ai as ai_mod


def build_blur_onnx(out_path: Path):
    try:
        import onnx
        from onnx import helper, TensorProto
        import numpy as _np
    except Exception as e:
        print(f"onnx package missing: {e}")
        raise

    # Conv with a fixed 3x3 averaging kernel applied per channel (groups=3).
    k = _np.ones((3, 1, 3, 3), dtype=_np.float32) / 9.0
    weight = helper.make_tensor("W", TensorProto.FLOAT, k.shape, k.flatten().tolist())
    inp = helper.make_tensor_value_info("input", TensorProto.FLOAT, [None, 3, None, None])
    out = helper.make_tensor_value_info("output", TensorProto.FLOAT, [None, 3, None, None])
    node = helper.make_node(
        "Conv", inputs=["input", "W"], outputs=["output"],
        pads=[1, 1, 1, 1], strides=[1, 1], group=3,
    )
    graph = helper.make_graph([node], "denoise_blur_test", [inp], [out], initializer=[weight])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 9
    onnx.save(model, str(out_path))


def main():
    model_path = ai_mod.models_dir() / "denoise_blurtest.onnx"
    build_blur_onnx(model_path)
    print(f"[ok ] wrote {model_path}")

    rng = np.random.default_rng(0)
    img = rng.random((1500, 2000, 3), dtype=np.float32) * 0.3 + 0.2
    # Add a few "stars" to confirm the result is smoothed.
    for _ in range(50):
        y, x = rng.integers(10, 1490), rng.integers(10, 1990)
        img[y, x] = 0.95
    print(f"input: {img.shape} mean={img.mean():.4f} std={img.std():.4f}")

    out = ai_mod.run_ai_denoise(img, model_name="denoise_blurtest", strength=1.0)
    if out is None:
        print("FAIL: run_ai_denoise returned None (onnxruntime missing?)")
        return 1
    print(f"output: {out.shape} mean={out.mean():.4f} std={out.std():.4f}")
    assert out.shape == img.shape
    assert np.isfinite(out).all()
    # A 3x3 blur reduces std and brings stars closer to the local mean.
    assert out.std() < img.std()
    print("[ok ] tiled AI path produced sensible output")
    # cleanup
    try:
        model_path.unlink()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
