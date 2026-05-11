"""AI / ONNX model management API (Phase 5)."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..processing import ai

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/runtime")
def runtime():
    return ai.runtime_info()


@router.get("/models")
def list_models():
    return {"models_dir": str(ai.models_dir()), "models": ai.list_models()}


@router.post("/models")
async def upload_model(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".onnx"):
        raise HTTPException(status_code=400, detail="Model must be an .onnx file")
    dest = ai.models_dir() / file.filename
    data = await file.read()
    dest.write_bytes(data)
    return {"ok": True, "path": str(dest)}


@router.delete("/models/{name}")
def delete_model(name: str):
    p = ai.models_dir() / (name if name.endswith(".onnx") else f"{name}.onnx")
    if p.exists():
        p.unlink()
    return {"ok": True}
