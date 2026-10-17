"""Serve cached artwork: GET /api/img?url=<https://upload.wikimedia.org/...>"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..services.images import fetch, is_allowed, media_type_for

router = APIRouter(tags=["images"])


@router.get("/img")
def image(url: str = Query(..., max_length=1000)):
    if not is_allowed(url):
        raise HTTPException(400, "Image host not allowed")
    path = fetch(url)
    if path is None:
        raise HTTPException(502, "Image unavailable right now")
    return FileResponse(
        path,
        media_type=media_type_for(path),
        headers={"Cache-Control": "public, max-age=2592000, immutable"},
    )
