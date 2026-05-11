"""Frame management: import, list, remove, analyze."""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..db import transaction
from ..processing import frame_analysis
from ..processing.image_io import image_shape, is_supported, load_image
from ..processing.preview import make_thumbnail
from ..schemas import FrameOut
from . import project_service


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_frame(row) -> FrameOut:
    return FrameOut(
        frame_id=row["frame_id"],
        project_id=row["project_id"],
        original_name=row["original_name"],
        frame_type=row["frame_type"],
        width=row["width"],
        height=row["height"],
        bit_depth=row["bit_depth"],
        quality_score=row["quality_score"],
        star_count=row["star_count"],
        included=bool(row["included"]),
        created_at=row["created_at"],
    )


_FRAME_DIRS = {
    "light": "lights",
    "dark": "darks",
    "flat": "flats",
    "bias": "biases",
    "flat_dark": "biases",
}


def import_frame(
    project_id: str,
    src_path: Path,
    original_name: str,
    frame_type: str = "light",
) -> FrameOut:
    if not is_supported(src_path):
        raise ValueError(f"Unsupported file type: {original_name}")

    sub = _FRAME_DIRS.get(frame_type, "lights")
    target_dir = project_service.subdir(project_id, sub)
    frame_id = str(uuid.uuid4())
    suffix = src_path.suffix.lower()
    dest = target_dir / f"{frame_id}{suffix}"
    shutil.copyfile(src_path, dest)

    width = height = bit_depth = None
    quality = None
    stars = None
    try:
        img = load_image(dest)
        h, w, c = image_shape(img)
        width, height = w, h
        bit_depth = 32  # internal float
        if frame_type == "light":
            stats = frame_analysis.analyze(img)
            quality = stats.score
            stars = stats.star_count
        # thumbnail
        thumbs = project_service.subdir(project_id, "thumbnails")
        make_thumbnail(img, thumbs / f"{frame_id}.png")
    except Exception:
        # Keep the file but skip analysis if it failed.
        pass

    with transaction() as conn:
        conn.execute(
            """INSERT INTO frames (
                frame_id, project_id, file_path, original_name, frame_type,
                width, height, bit_depth, quality_score, star_count, included, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                frame_id,
                project_id,
                str(dest),
                original_name,
                frame_type,
                width,
                height,
                bit_depth,
                quality,
                stars,
                1,
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM frames WHERE frame_id = ?", (frame_id,)
        ).fetchone()

    project_service.touch(project_id)
    return _row_to_frame(row)


def list_frames(project_id: str, frame_type: Optional[str] = None) -> List[FrameOut]:
    with transaction() as conn:
        if frame_type:
            rows = conn.execute(
                "SELECT * FROM frames WHERE project_id = ? AND frame_type = ? ORDER BY created_at",
                (project_id, frame_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM frames WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ).fetchall()
    return [_row_to_frame(r) for r in rows]


def get_frame(project_id: str, frame_id: str) -> FrameOut:
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM frames WHERE project_id = ? AND frame_id = ?",
            (project_id, frame_id),
        ).fetchone()
    if row is None:
        raise KeyError(frame_id)
    return _row_to_frame(row)


def get_frame_path(project_id: str, frame_id: str) -> Path:
    with transaction() as conn:
        row = conn.execute(
            "SELECT file_path FROM frames WHERE project_id = ? AND frame_id = ?",
            (project_id, frame_id),
        ).fetchone()
    if row is None:
        raise KeyError(frame_id)
    return Path(row["file_path"])


def delete_frame(project_id: str, frame_id: str) -> None:
    path = get_frame_path(project_id, frame_id)
    with transaction() as conn:
        conn.execute(
            "DELETE FROM frames WHERE project_id = ? AND frame_id = ?",
            (project_id, frame_id),
        )
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
    thumb = project_service.subdir(project_id, "thumbnails") / f"{frame_id}.png"
    try:
        thumb.unlink(missing_ok=True)
    except Exception:
        pass
    project_service.touch(project_id)


def set_included(project_id: str, frame_id: str, included: bool) -> FrameOut:
    with transaction() as conn:
        conn.execute(
            "UPDATE frames SET included = ? WHERE project_id = ? AND frame_id = ?",
            (1 if included else 0, project_id, frame_id),
        )
    project_service.touch(project_id)
    return get_frame(project_id, frame_id)
