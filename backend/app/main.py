"""FastAPI application entrypoint for Easy Astro Photos."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import ai, frames, processing, projects
from .config import ensure_dirs
from .db import get_conn


def create_app() -> FastAPI:
    ensure_dirs()
    get_conn()  # initialize schema

    app = FastAPI(
        title="Easy Astro Photos",
        version="0.1.0",
        description=(
            "Phase 1 MVP backend for Easy Astro Photos. Handles projects, light "
            "frame import, alignment, stacking, auto-stretch, and export."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(projects.router)
    app.include_router(frames.router)
    app.include_router(processing.router)
    app.include_router(ai.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "app": "Easy Astro Photos", "phase": 1}

    return app


app = create_app()
