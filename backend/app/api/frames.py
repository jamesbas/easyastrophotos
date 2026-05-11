"""Frame import / management API."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..schemas import FrameOut
from ..services import frame_service, project_service

router = APIRouter(prefix="/api/projects/{project_id}/frames", tags=["frames"])


@router.post("", response_model=List[FrameOut])
async def upload_frames(
    project_id: str,
    files: List[UploadFile] = File(...),
    frame_type: str = Form("light"),
) -> List[FrameOut]:
    try:
        project_service.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

    out: List[FrameOut] = []
    for upload in files:
        suffix = Path(upload.filename or "frame").suffix or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            data = await upload.read()
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            frame = frame_service.import_frame(
                project_id, tmp_path, upload.filename or "frame", frame_type=frame_type
            )
            out.append(frame)
        except ValueError as exc:
            # Skip unsupported files but report the rest.
            continue
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
    return out


@router.get("", response_model=List[FrameOut])
def list_frames(project_id: str, frame_type: Optional[str] = None) -> List[FrameOut]:
    return frame_service.list_frames(project_id, frame_type)


@router.delete("/{frame_id}")
def delete_frame(project_id: str, frame_id: str) -> dict:
    frame_service.delete_frame(project_id, frame_id)
    return {"ok": True}


@router.patch("/{frame_id}", response_model=FrameOut)
def update_frame(project_id: str, frame_id: str, included: bool) -> FrameOut:
    return frame_service.set_included(project_id, frame_id, included)


@router.get("/{frame_id}/thumbnail")
def get_thumbnail(project_id: str, frame_id: str):
    thumb = project_service.subdir(project_id, "thumbnails") / f"{frame_id}.png"
    if not thumb.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not available")
    return FileResponse(thumb, media_type="image/png")
