"""Processing recipe: persist and replay step history.

A recipe is a list of operations applied to the master stack to produce the
current preview. Each step is a JSON-serializable dict like:

    {"id": "step-001", "operation": "stretch", "params": {...}}

Recipes are stored as ``recipe.json`` inside the project folder.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from ..processing import (
    background,
    color,
    deconvolution,
    denoise,
    pixel_math,
    stars,
    stretch,
)
from .project_service import project_path, touch


def _recipe_path(project_id: str) -> Path:
    return project_path(project_id) / "recipe.json"


def load_recipe(project_id: str) -> Dict[str, Any]:
    p = _recipe_path(project_id)
    if not p.exists():
        return {"project_id": project_id, "steps": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"project_id": project_id, "steps": []}


def save_recipe(project_id: str, recipe: Dict[str, Any]) -> None:
    p = _recipe_path(project_id)
    p.write_text(json.dumps(recipe, indent=2), encoding="utf-8")
    touch(project_id)


def append_step(project_id: str, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
    recipe = load_recipe(project_id)
    step = {
        "id": f"step-{uuid.uuid4().hex[:8]}",
        "operation": operation,
        "params": params,
        "ts": int(time.time()),
    }
    recipe.setdefault("steps", []).append(step)
    save_recipe(project_id, recipe)
    return step


def remove_step(project_id: str, step_id: str) -> None:
    recipe = load_recipe(project_id)
    recipe["steps"] = [s for s in recipe.get("steps", []) if s.get("id") != step_id]
    save_recipe(project_id, recipe)


def clear_steps(project_id: str) -> None:
    recipe = load_recipe(project_id)
    recipe["steps"] = []
    save_recipe(project_id, recipe)


def apply_step(image: np.ndarray, operation: str, params: Dict[str, Any]) -> np.ndarray:
    op = operation.lower()
    p = params or {}
    if op == "stretch":
        opts = stretch.StretchOptions(**_filter(p, stretch.StretchOptions))
        return stretch.auto_stretch(image, options=opts)
    if op == "background_extraction":
        opts = background.BackgroundOptions(**_filter(p, background.BackgroundOptions))
        out, _ = background.remove_background(image, opts)
        return out
    if op == "denoise":
        opts = denoise.DenoiseOptions(**_filter(p, denoise.DenoiseOptions))
        return denoise.denoise(image, opts)
    if op == "deconvolution":
        opts = deconvolution.DeconvolutionOptions(**_filter(p, deconvolution.DeconvolutionOptions))
        return deconvolution.deconvolve(image, opts)
    if op == "color":
        opts = color.ColorOptions(**_filter(p, color.ColorOptions))
        return color.apply_color(image, opts)
    if op == "star_reduction":
        return stars.reduce_stars(image, amount=float(p.get("amount", 0.5)))
    if op == "starless":
        return stars.starless_preview(image)
    if op == "pixel_math":
        return pixel_math.evaluate(str(p.get("expression", "image")), image)
    raise ValueError(f"Unknown recipe operation: {operation}")


def _filter(params: Dict[str, Any], cls) -> Dict[str, Any]:
    """Keep only fields that the dataclass actually accepts."""
    valid = set(getattr(cls, "__dataclass_fields__", {}).keys())
    return {k: v for k, v in (params or {}).items() if k in valid}


def replay(project_id: str, master: np.ndarray) -> np.ndarray:
    recipe = load_recipe(project_id)
    out = master.astype(np.float32).copy()
    for step in recipe.get("steps", []):
        if not step.get("enabled", True):
            continue
        out = apply_step(out, step["operation"], step.get("params", {}))
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def set_step_enabled(project_id: str, step_id: str, enabled: bool) -> None:
    recipe = load_recipe(project_id)
    for s in recipe.get("steps", []):
        if s.get("id") == step_id:
            s["enabled"] = bool(enabled)
    save_recipe(project_id, recipe)
