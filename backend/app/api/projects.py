"""Project API."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from ..schemas import ProjectCreate, ProjectOut
from ..services import project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate) -> ProjectOut:
    return project_service.create_project(payload.name, payload.target_type)


@router.get("", response_model=List[ProjectOut])
def list_projects() -> List[ProjectOut]:
    return project_service.list_projects()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str) -> ProjectOut:
    try:
        return project_service.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict:
    project_service.delete_project(project_id)
    return {"ok": True}
