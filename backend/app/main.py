"""FastAPI entrypoint. All JSON routes live under /api; the built frontend (if present) is served at /."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import auth, feed, images, lists, media, meta, parties, profile, sessions, social
from .config import PROJECT_DIR, settings
from .db import SessionLocal
from .migrate import upgrade_db
from .services.catalog import apply_artwork, seed_catalog

FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"


def init_db() -> None:
    upgrade_db()
    with SessionLocal() as db:
        seed_catalog(db)
        apply_artwork(db)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="sai API",
    version="0.1.0",
    description="Tinder-style discovery for movies and TV, with duo/group matching.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, feed, lists, media, sessions, social, parties, profile, meta, images):
    app.include_router(r.router, prefix="/api")
app.include_router(sessions.ws_router, prefix="/api")


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and FRONTEND_DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(Path(FRONTEND_DIST / "index.html"))
