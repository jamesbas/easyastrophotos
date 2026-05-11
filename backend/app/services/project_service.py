"""Project CRUD and on-disk layout management."""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from ..config import project_dir, project_subdir
from ..db import transaction
from ..schemas import ProjectOut


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_project(row) -> ProjectOut:
    pdir = project_dir(row["project_id"])
    has_stack = (pdir / "stack" / "master_stack.npy").exists()
    has_preview = (pdir / "previews" / "current.png").exists()
    return ProjectOut(
        project_id=row["project_id"],
        name=row["name"],
        target_type=row["target_type"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        status=row["status"],
        has_stack=has_stack,
        has_preview=has_preview,
    )


def create_project(name: str, target_type: str) -> ProjectOut:
    project_id = str(uuid.uuid4())
    now = _now()
    pdir = project_dir(project_id)
    pdir.mkdir(parents=True, exist_ok=True)
    for sub in ("lights", "darks", "flats", "biases", "thumbnails", "previews", "stack", "exports"):
        (pdir / sub).mkdir(exist_ok=True)
    (pdir / "recipe.json").write_text(json.dumps({"project_id": project_id, "steps": []}, indent=2))

    with transaction() as conn:
        conn.execute(
            """INSERT INTO projects (project_id, name, target_type, created_at, updated_at, status, recipe_json)
               VALUES (?,?,?,?,?,?,?)""",
            (project_id, name, target_type, now, now, "active", "{}"),
        )
        row = conn.execute(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
    return _row_to_project(row)


def list_projects() -> List[ProjectOut]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC"
        ).fetchall()
    return [_row_to_project(r) for r in rows]


def get_project(project_id: str) -> ProjectOut:
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
    if row is None:
        raise KeyError(project_id)
    return _row_to_project(row)


def delete_project(project_id: str) -> None:
    with transaction() as conn:
        conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
    pdir = project_dir(project_id)
    if pdir.exists():
        shutil.rmtree(pdir, ignore_errors=True)


def touch(project_id: str) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE projects SET updated_at = ? WHERE project_id = ?",
            (_now(), project_id),
        )


def project_path(project_id: str) -> Path:
    get_project(project_id)  # ensures exists
    return project_dir(project_id)


def subdir(project_id: str, name: str) -> Path:
    get_project(project_id)
    return project_subdir(project_id, name)
