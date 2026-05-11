"""Restricted pixel-math expression evaluator.

Allows expressions like:
    "(R - B) / max(R + B, 0.001)"
    "0.5 * A + 0.5 * B"
    "clip(image * 1.2 - 0.05, 0, 1)"

Variables available:
- ``image`` (the current processed image)
- ``r``, ``g``, ``b`` (channels of the current image, if RGB)
- Any user-supplied named arrays via the ``vars`` mapping.

Only a small whitelist of names is callable.
"""
from __future__ import annotations

import ast
from typing import Any, Dict, Optional

import numpy as np


_ALLOWED_FUNCS: Dict[str, Any] = {
    "abs": np.abs,
    "min": np.minimum,
    "max": np.maximum,
    "clip": np.clip,
    "sqrt": np.sqrt,
    "log": np.log,
    "log1p": np.log1p,
    "exp": np.exp,
    "sin": np.sin,
    "cos": np.cos,
    "asinh": np.arcsinh,
    "tanh": np.tanh,
    "where": np.where,
    "median": np.median,
    "mean": np.mean,
    "percentile": np.percentile,
}

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Call,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.FloorDiv,
    ast.Compare,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Eq,
    ast.NotEq,
    ast.IfExp,
    ast.Tuple,
)


class _Validator(ast.NodeVisitor):
    def generic_visit(self, node: ast.AST) -> None:  # type: ignore[override]
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"Disallowed expression: {type(node).__name__}")
        super().generic_visit(node)


def evaluate(expression: str, image: np.ndarray, vars: Optional[Dict[str, np.ndarray]] = None) -> np.ndarray:
    if not expression or len(expression) > 4000:
        raise ValueError("Expression empty or too long")
    tree = ast.parse(expression, mode="eval")
    _Validator().visit(tree)

    env: Dict[str, Any] = dict(_ALLOWED_FUNCS)
    env["image"] = image
    if image.ndim == 3 and image.shape[-1] >= 3:
        env["r"] = image[..., 0]
        env["g"] = image[..., 1]
        env["b"] = image[..., 2]
    if vars:
        env.update(vars)

    code = compile(tree, "<pixel_math>", "eval")
    out = eval(code, {"__builtins__": {}}, env)  # noqa: S307 - controlled env
    if not isinstance(out, np.ndarray):
        out = np.asarray(out, dtype=np.float32)
    return np.clip(out.astype(np.float32), 0.0, 1.0)
