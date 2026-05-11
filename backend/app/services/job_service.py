"""Synchronous processing job orchestrator for all phases.

Phase 1: stack + stretch + export
Phase 2: master calibration frames + calibrated stacking + recipe persistence
Phase 3: background extraction, denoise, deconvolution
Phase 4: color calibration / palette mapping
Phase 5: AI hooks (delegated through processing.ai)
Phase 6: star processing, pixel math, recipe replay

Every processed step appends to the recipe so it can be replayed against the
master stack later.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .. import schemas
from ..processing import (
    background as bg_mod,
    calibration as cal_mod,
    color as color_mod,
    deconvolution as decon_mod,
    denoise as denoise_mod,
    pixel_math,
    registration,
    stacking,
    stars as stars_mod,
    stretch as stretch_mod,
)
from ..processing.image_io import (
    load_image,
    save_fits,
    save_png,
    save_tiff,
)
from ..processing.preview import make_preview
from . import frame_service, project_service, recipe_service


# --------------------------------------------------------------------------- #
# Path helpers
# --------------------------------------------------------------------------- #

def _stack_dir(project_id: str) -> Path:
    return project_service.subdir(project_id, "stack")


def _preview_dir(project_id: str) -> Path:
    return project_service.subdir(project_id, "previews")


def _master_path(project_id: str) -> Path:
    return _stack_dir(project_id) / "master_stack.npy"


def _current_path(project_id: str) -> Path:
    return _stack_dir(project_id) / "current.npy"


def _load_master(project_id: str) -> np.ndarray:
    p = _master_path(project_id)
    if not p.exists():
        raise ValueError("Project has not been stacked yet.")
    return np.load(p)


def _load_current(project_id: str) -> np.ndarray:
    p = _current_path(project_id)
    if p.exists():
        return np.load(p)
    return _load_master(project_id)


def _save_current(project_id: str, image: np.ndarray) -> None:
    np.save(_current_path(project_id), image)
    save_png(_preview_dir(project_id) / "current.png", image)
    project_service.touch(project_id)


# --------------------------------------------------------------------------- #
# Phase 2: calibration frame builders
# --------------------------------------------------------------------------- #

def build_master_frames(project_id: str, options: schemas.CalibrateOptions) -> Dict[str, str]:
    sdir = _stack_dir(project_id)
    out: Dict[str, str] = {}
    for kind in ("dark", "flat", "bias", "flat_dark"):
        frames = [f for f in frame_service.list_frames(project_id, kind) if f.included]
        if not frames:
            continue
        paths = [frame_service.get_frame_path(project_id, f.frame_id) for f in frames]
        master = cal_mod.make_master_frame(paths, method=options.master_method)
        if master is None:
            continue
        np.save(sdir / f"master_{kind}.npy", master)
        out[kind] = str(sdir / f"master_{kind}.npy")
    return out


def _load_master_frame(project_id: str, kind: str) -> Optional[np.ndarray]:
    p = _stack_dir(project_id) / f"master_{kind}.npy"
    if p.exists():
        return np.load(p)
    return None


# --------------------------------------------------------------------------- #
# Stack pipeline (Phase 1 + 2)
# --------------------------------------------------------------------------- #

def stack_project(project_id: str, options: schemas.StackOptions) -> dict:
    light_frames = [f for f in frame_service.list_frames(project_id, "light") if f.included]
    if not light_frames:
        raise ValueError("No included light frames to stack.")

    light_frames.sort(key=lambda f: (f.quality_score or 0.0), reverse=True)

    # Build master calibration frames if requested.
    masters: Dict[str, Optional[np.ndarray]] = {
        "dark": None, "flat": None, "bias": None, "flat_dark": None
    }
    if options.calibrate:
        build_master_frames(project_id, options.calibration)
        for kind in masters.keys():
            masters[kind] = _load_master_frame(project_id, kind)

    paths = [frame_service.get_frame_path(project_id, f.frame_id) for f in light_frames]
    loaded = [load_image(p) for p in paths]

    if options.calibrate:
        cal_opts = cal_mod.CalibrationOptions(
            use_darks=options.calibration.use_darks,
            use_flats=options.calibration.use_flats,
            use_bias=options.calibration.use_bias,
            cosmetic_correction=options.calibration.cosmetic_correction,
            dark_optimization=options.calibration.dark_optimization,
            flat_normalization=options.calibration.flat_normalization,
        )
        loaded = [
            cal_mod.calibrate_light(
                img,
                master_dark=masters["dark"],
                master_flat=masters["flat"],
                master_bias=masters["bias"] if masters["bias"] is not None else masters["flat_dark"],
                options=cal_opts,
            )
            for img in loaded
        ]

    reference = loaded[0]
    aligned: List[np.ndarray] = [reference]
    failed: List[str] = []

    for f, img in zip(light_frames[1:], loaded[1:]):
        if options.align:
            warped = registration.align_to_reference(img, reference)
            if warped is None:
                failed.append(f.original_name)
                continue
            aligned.append(warped)
        else:
            aligned.append(img)

    if len(aligned) == 1 and options.align and failed:
        aligned = loaded
        failed = []

    weights = _frame_weights(light_frames[: len(aligned)], options.weighting)
    master = stacking.stack(
        aligned,
        method=options.method,
        weights=weights,
        sigma_low=options.sigma_low,
        sigma_high=options.sigma_high,
    )

    sdir = _stack_dir(project_id)
    np.save(sdir / "master_stack.npy", master)
    save_fits(sdir / "master_stack.fit", master)

    pdir = _preview_dir(project_id)
    make_preview(reference, pdir / "original.png")
    make_preview(master, pdir / "stack_linear.png")
    stretched = stretch_mod.auto_stretch(master, method="asinh")
    save_png(pdir / "current.png", stretched)
    np.save(_current_path(project_id), stretched)

    # Reset recipe; record initial auto-stretch.
    recipe_service.clear_steps(project_id)
    recipe_service.append_step(
        project_id,
        "stretch",
        {"method": "asinh", "black_point": 0.001, "midtone": 0.25},
    )

    project_service.touch(project_id)
    return {
        "stacked_frames": len(aligned),
        "rejected_frames": len(failed),
        "rejected_names": failed,
        "method": options.method,
        "weighting": options.weighting,
        "calibrated": options.calibrate,
        "reference_frame": light_frames[0].original_name,
    }


def _frame_weights(frames, weighting: str) -> Optional[List[float]]:
    if weighting == "equal":
        return None
    if weighting == "quality":
        ws = [max(0.01, float(f.quality_score or 0.5)) for f in frames]
    elif weighting == "stars":
        ws = [max(1.0, float(f.star_count or 1)) for f in frames]
    elif weighting == "noise":
        # Higher score = lower noise; reuse as weight.
        ws = [max(0.01, float(f.quality_score or 0.5)) for f in frames]
    else:
        return None
    return ws


# --------------------------------------------------------------------------- #
# Single-step processing operations (apply to current preview)
# --------------------------------------------------------------------------- #

def stretch_current(project_id: str, options: schemas.StretchOptions) -> dict:
    """Re-runs stretching from the master stack so it remains non-destructive."""
    master = _load_master(project_id)
    opts = stretch_mod.StretchOptions(
        method=options.method,
        black_point=options.black_point,
        midtone=options.midtone,
        white_point=options.white_point,
        protect_highlights=options.protect_highlights,
        protect_shadows=options.protect_shadows,
        stretch_factor=options.stretch_factor,
        local_intensity=options.local_intensity,
        curve_points=options.curve_points,
    )
    out = stretch_mod.auto_stretch(master, options=opts)
    _save_current(project_id, out)
    # Replace any prior stretch in the recipe with the new one.
    recipe = recipe_service.load_recipe(project_id)
    recipe["steps"] = [s for s in recipe.get("steps", []) if s.get("operation") != "stretch"]
    recipe_service.save_recipe(project_id, recipe)
    recipe_service.append_step(project_id, "stretch", options.model_dump())
    return {"method": options.method}


def background_extraction(project_id: str, options: schemas.BackgroundOptions) -> dict:
    img = _load_current(project_id)
    opts = bg_mod.BackgroundOptions(
        method=options.method,
        degree=options.degree,
        smoothing=options.smoothing,
        correction=options.correction,
        strength=options.strength,
        protect_objects=options.protect_objects,
        samples=options.samples,
        sample_percentile=options.sample_percentile,
        sigma_high=options.sigma_high,
        rejection_iters=options.rejection_iters,
    )
    out, model = bg_mod.remove_background(img, opts)
    _save_current(project_id, out)
    save_png(_preview_dir(project_id) / "background_model.png", _normalize(model))
    recipe_service.append_step(project_id, "background_extraction", options.model_dump())
    return {"saved_model": True}


def denoise_current(project_id: str, options: schemas.DenoiseOptions) -> dict:
    img = _load_current(project_id)
    opts = denoise_mod.DenoiseOptions(
        method=options.method,
        strength=options.strength,
        protect_stars=options.protect_stars,
        scales=options.scales,
        preserve_coarse=options.preserve_coarse,
        model_name=options.model_name,
    )
    out = denoise_mod.denoise(img, opts)
    _save_current(project_id, out)
    recipe_service.append_step(project_id, "denoise", options.model_dump())
    return {"method": options.method}


def deconvolve_current(project_id: str, options: schemas.DeconvolutionOptions) -> dict:
    img = _load_current(project_id)
    opts = decon_mod.DeconvolutionOptions(
        method=options.method,
        strength=options.strength,
        fwhm=options.fwhm,
        iterations=options.iterations,
        star_mode=options.star_mode,
        protect_ringing=options.protect_ringing,
        tv_lambda=options.tv_lambda,
        model_name=options.model_name,
    )
    out = decon_mod.deconvolve(img, opts)
    _save_current(project_id, out)
    recipe_service.append_step(project_id, "deconvolution", options.model_dump())
    return {"method": options.method}


def color_current(project_id: str, options: schemas.ColorOptions) -> dict:
    img = _load_current(project_id)
    opts = color_mod.ColorOptions(
        mode=options.mode,
        saturation=options.saturation,
        green_reduction=options.green_reduction,
        background_neutralization=options.background_neutralization,
        preserve_star_color=options.preserve_star_color,
        channel_map=options.channel_map,
    )
    out = color_mod.apply_color(img, opts)
    _save_current(project_id, out)
    recipe_service.append_step(project_id, "color", options.model_dump())
    return {"mode": options.mode}


def reduce_stars(project_id: str, options: schemas.StarReductionOptions) -> dict:
    img = _load_current(project_id)
    out = stars_mod.reduce_stars(img, amount=options.amount)
    _save_current(project_id, out)
    recipe_service.append_step(project_id, "star_reduction", options.model_dump())
    return {"amount": options.amount}


def starless_preview(project_id: str) -> dict:
    img = _load_current(project_id)
    out = stars_mod.starless_preview(img)
    pdir = _preview_dir(project_id)
    save_png(pdir / "starless.png", out)
    return {"path": str(pdir / "starless.png")}


def star_mask_preview(project_id: str) -> dict:
    img = _load_current(project_id)
    mask = stars_mod.detect_star_mask(img)
    pdir = _preview_dir(project_id)
    save_png(pdir / "star_mask.png", mask)
    return {"path": str(pdir / "star_mask.png")}


def pixel_math_op(project_id: str, expression: str, persist: bool = True) -> dict:
    img = _load_current(project_id)
    out = pixel_math.evaluate(expression, img)
    _save_current(project_id, out)
    if persist:
        recipe_service.append_step(project_id, "pixel_math", {"expression": expression})
    return {"expression": expression}


# --------------------------------------------------------------------------- #
# Replay & export
# --------------------------------------------------------------------------- #

def replay_recipe(project_id: str) -> dict:
    master = _load_master(project_id)
    out = recipe_service.replay(project_id, master)
    _save_current(project_id, out)
    return {"steps": len(recipe_service.load_recipe(project_id).get("steps", []))}


def export_image(project_id: str, fmt: str) -> Path:
    sdir = _stack_dir(project_id)
    edir = project_service.subdir(project_id, "exports")
    current = sdir / "current.npy"
    if not current.exists():
        master = sdir / "master_stack.npy"
        if not master.exists():
            raise ValueError("Nothing to export. Stack the project first.")
        data = np.load(master)
    else:
        data = np.load(current)

    fmt = fmt.lower()
    if fmt == "png":
        out = edir / "easy-astro-export.png"
        save_png(out, data)
    elif fmt in ("tif", "tiff"):
        out = edir / "easy-astro-export.tif"
        save_tiff(out, data, bits=16)
    elif fmt in ("fit", "fits"):
        out = edir / "easy-astro-export.fit"
        save_fits(out, data)
    elif fmt == "jpeg" or fmt == "jpg":
        out = edir / "easy-astro-export.jpg"
        from PIL import Image as _Im
        d = (np.clip(data, 0, 1) * 255 + 0.5).astype(np.uint8)
        if d.ndim == 2:
            _Im.fromarray(d, mode="L").save(out, quality=92)
        else:
            _Im.fromarray(d[..., :3], mode="RGB").save(out, quality=92)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")
    return out


def histogram(project_id: str) -> dict:
    sdir = _stack_dir(project_id)
    current = sdir / "current.npy"
    if current.exists():
        data = np.load(current)
    else:
        master = sdir / "master_stack.npy"
        if not master.exists():
            raise ValueError("No stack available.")
        data = np.load(master)
    return stretch_mod.histogram(data)


def _normalize(arr: np.ndarray) -> np.ndarray:
    a = arr.astype(np.float32)
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-6:
        return np.zeros_like(a)
    return ((a - lo) / (hi - lo)).astype(np.float32)
