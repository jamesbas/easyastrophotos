"""Processing job and preview API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import schemas
from ..services import job_service, project_service, recipe_service

router = APIRouter(prefix="/api/projects/{project_id}", tags=["processing"])


def _ensure(project_id: str) -> None:
    try:
        project_service.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


# --------------------------------------------------------------------------- #
# Stack / calibration
# --------------------------------------------------------------------------- #

@router.post("/jobs/calibrate", response_model=schemas.JobResult)
def calibrate(project_id: str, options: schemas.CalibrateOptions = schemas.CalibrateOptions()):
    _ensure(project_id)
    masters = job_service.build_master_frames(project_id, options)
    return schemas.JobResult(ok=True, message="Master frames built.", details={"masters": list(masters.keys())})


@router.post("/jobs/stack", response_model=schemas.JobResult)
def stack(project_id: str, options: schemas.StackOptions = schemas.StackOptions()):
    _ensure(project_id)
    try:
        details = job_service.stack_project(project_id, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.JobResult(ok=True, message="Stacked.", details=details)


# --------------------------------------------------------------------------- #
# Processing operations (Phases 3 + 4 + 6)
# --------------------------------------------------------------------------- #

@router.post("/jobs/stretch", response_model=schemas.JobResult)
def stretch(project_id: str, options: schemas.StretchOptions = schemas.StretchOptions()):
    _ensure(project_id)
    try:
        details = job_service.stretch_current(project_id, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.JobResult(ok=True, message="Stretched.", details=details)


@router.post("/jobs/background-extraction", response_model=schemas.JobResult)
def background(project_id: str, options: schemas.BackgroundOptions = schemas.BackgroundOptions()):
    _ensure(project_id)
    try:
        details = job_service.background_extraction(project_id, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.JobResult(ok=True, message="Background removed.", details=details)


@router.post("/jobs/denoise", response_model=schemas.JobResult)
def denoise(project_id: str, options: schemas.DenoiseOptions = schemas.DenoiseOptions()):
    _ensure(project_id)
    try:
        details = job_service.denoise_current(project_id, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.JobResult(ok=True, message="Denoised.", details=details)


@router.post("/jobs/deconvolution", response_model=schemas.JobResult)
def deconvolution(project_id: str, options: schemas.DeconvolutionOptions = schemas.DeconvolutionOptions()):
    _ensure(project_id)
    try:
        details = job_service.deconvolve_current(project_id, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.JobResult(ok=True, message="Sharpened.", details=details)


@router.post("/jobs/colorize", response_model=schemas.JobResult)
def colorize(project_id: str, options: schemas.ColorOptions = schemas.ColorOptions()):
    _ensure(project_id)
    try:
        details = job_service.color_current(project_id, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.JobResult(ok=True, message="Color applied.", details=details)


@router.post("/jobs/star-reduction", response_model=schemas.JobResult)
def star_reduction(project_id: str, options: schemas.StarReductionOptions = schemas.StarReductionOptions()):
    _ensure(project_id)
    details = job_service.reduce_stars(project_id, options)
    return schemas.JobResult(ok=True, message="Stars reduced.", details=details)


@router.post("/jobs/star-mask", response_model=schemas.JobResult)
def star_mask(project_id: str):
    _ensure(project_id)
    details = job_service.star_mask_preview(project_id)
    return schemas.JobResult(ok=True, message="Star mask generated.", details=details)


@router.post("/jobs/starless", response_model=schemas.JobResult)
def starless(project_id: str):
    _ensure(project_id)
    details = job_service.starless_preview(project_id)
    return schemas.JobResult(ok=True, message="Starless preview generated.", details=details)


@router.post("/jobs/pixel-math", response_model=schemas.JobResult)
def pixel_math(project_id: str, payload: schemas.PixelMathRequest):
    _ensure(project_id)
    try:
        details = job_service.pixel_math_op(project_id, payload.expression, payload.persist)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.JobResult(ok=True, message="Pixel math applied.", details=details)


@router.post("/jobs/export", response_model=schemas.JobResult)
def export(project_id: str, fmt: str = "png"):
    _ensure(project_id)
    try:
        path = job_service.export_image(project_id, fmt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.JobResult(ok=True, message="Exported.", details={"path": str(path)})


# --------------------------------------------------------------------------- #
# Recipes (Phase 6)
# --------------------------------------------------------------------------- #

@router.get("/recipe")
def get_recipe(project_id: str):
    _ensure(project_id)
    return recipe_service.load_recipe(project_id)


@router.post("/recipe/replay", response_model=schemas.JobResult)
def replay(project_id: str):
    _ensure(project_id)
    try:
        details = job_service.replay_recipe(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.JobResult(ok=True, message="Recipe replayed.", details=details)


@router.delete("/recipe/steps/{step_id}")
def remove_recipe_step(project_id: str, step_id: str):
    _ensure(project_id)
    recipe_service.remove_step(project_id, step_id)
    return {"ok": True}


@router.patch("/recipe/steps/{step_id}")
def patch_recipe_step(project_id: str, step_id: str, payload: schemas.RecipeStepUpdate):
    _ensure(project_id)
    recipe_service.set_step_enabled(project_id, step_id, payload.enabled)
    return {"ok": True}


@router.post("/recipe/import", response_model=schemas.JobResult)
def import_recipe(project_id: str, payload: schemas.RecipeApplyRequest):
    _ensure(project_id)
    recipe_service.save_recipe(project_id, {"project_id": project_id, "steps": payload.steps})
    try:
        job_service.replay_recipe(project_id)
    except ValueError:
        pass
    return schemas.JobResult(ok=True, message="Recipe imported.", details={"steps": len(payload.steps)})


# --------------------------------------------------------------------------- #
# Previews
# --------------------------------------------------------------------------- #

@router.get("/preview/original")
def preview_original(project_id: str):
    p = project_service.subdir(project_id, "previews") / "original.png"
    if not p.exists():
        raise HTTPException(status_code=404, detail="No original preview yet.")
    return FileResponse(p, media_type="image/png")


@router.get("/preview/current")
def preview_current(project_id: str):
    p = project_service.subdir(project_id, "previews") / "current.png"
    if not p.exists():
        raise HTTPException(status_code=404, detail="No processed preview yet.")
    return FileResponse(p, media_type="image/png")


@router.get("/preview/stack-linear")
def preview_stack_linear(project_id: str):
    p = project_service.subdir(project_id, "previews") / "stack_linear.png"
    if not p.exists():
        raise HTTPException(status_code=404, detail="No linear preview yet.")
    return FileResponse(p, media_type="image/png")


@router.get("/preview/star-mask")
def preview_star_mask(project_id: str):
    p = project_service.subdir(project_id, "previews") / "star_mask.png"
    if not p.exists():
        raise HTTPException(status_code=404, detail="No star mask preview yet.")
    return FileResponse(p, media_type="image/png")


@router.get("/preview/starless")
def preview_starless(project_id: str):
    p = project_service.subdir(project_id, "previews") / "starless.png"
    if not p.exists():
        raise HTTPException(status_code=404, detail="No starless preview yet.")
    return FileResponse(p, media_type="image/png")


@router.get("/preview/background-model")
def preview_background_model(project_id: str):
    p = project_service.subdir(project_id, "previews") / "background_model.png"
    if not p.exists():
        raise HTTPException(status_code=404, detail="No background model yet.")
    return FileResponse(p, media_type="image/png")


@router.get("/histogram")
def histogram(project_id: str):
    try:
        return job_service.histogram(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/export/file")
def export_file(project_id: str, fmt: str = "png"):
    edir = project_service.subdir(project_id, "exports")
    suffix = {
        "png": "png", "jpg": "jpg", "jpeg": "jpg",
        "tif": "tif", "tiff": "tif",
        "fit": "fit", "fits": "fit",
    }.get(fmt.lower())
    if suffix is None:
        raise HTTPException(status_code=400, detail="Unsupported format")
    path = edir / f"easy-astro-export.{suffix}"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export not found. Run export first.")
    media = {
        "png": "image/png", "jpg": "image/jpeg",
        "tif": "image/tiff", "fit": "application/fits"
    }[suffix]
    return FileResponse(path, media_type=media, filename=path.name)
