"""Application configuration and on-disk paths."""
from __future__ import annotations

import os
from pathlib import Path


def _default_data_dir() -> Path:
    override = os.environ.get("EAP_DATA_DIR")
    if override:
        return Path(override)
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        return Path(local_app) / "EasyAstroPhotos"
    return Path.home() / ".easy-astro-photos"


DATA_DIR: Path = _default_data_dir()
PROJECTS_DIR: Path = DATA_DIR / "projects"
DB_PATH: Path = DATA_DIR / "easy-astro-photos.db"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def project_subdir(project_id: str, name: str) -> Path:
    p = project_dir(project_id) / name
    p.mkdir(parents=True, exist_ok=True)
    return p
