"""Title detail (card flip Q&A), similar titles, search and 'where to watch in India'."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User
from ..recs.rank import build_ctx, explain, personal_score, score_pool, similar_items
from ..security import get_current_user
from ..services.actions import apply_action, current_action
from ..services import tmdb
from ..services.catalog import (
    CERT_LABELS,
    FLAG_LABELS,
    all_media,
    get_media,
    invalidate_cache,
    media_card,
    rebuild_embeddings,
)
from ..services.importers import norm_title
from ..services.watch_links import trailer_links, watch_info

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/search")
def search(q: str = Query(..., min_length=1, max_length=100), limit: int = Query(12, ge=1, le=40),
           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    needle = norm_title(q)
    raw = q.lower().strip()

    def rank(m):
        t = norm_title(m.title)
        if t == needle:
            return 0
        if t.startswith(needle):
            return 1
        if needle in t:
            return 2
        if any(raw in c.lower() for c in m.cast) or (m.creator and raw in m.creator.lower()):
            return 3
        if any(raw == k.lower() for k in m.keywords):
            return 4
        return None

    hits = [(r, -m.popularity, m) for m in all_media(db) if (r := rank(m)) is not None]
    hits.sort(key=lambda t: (t[0], t[1]))
    imported = 0
    if settings.tmdb_enabled and len(hits) < 5 and len(q) >= 3:
        try:
            client = tmdb.TMDB(timeout=5)
            refs = [(r["media_type"], r["id"]) for r in client.search(q)[:5]]
            rows = tmdb.import_titles(db, client, refs)
            if rows:
                rebuild_embeddings(db)
                imported = len(rows)
                hits = [(r, -m.popularity, m) for m in all_media(db) if (r := rank(m)) is not None]
                hits.sort(key=lambda t: (t[0], t[1]))
        except httpx.HTTPError:
            invalidate_cache()
    return {"results": [media_card(m) for _r, _p, m in hits[:limit]], "imported_from_tmdb": imported}


@router.get("/{media_id}")
def detail(media_id: str, log: bool = True, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = get_media(db, media_id)
    if m is None:
        raise HTTPException(404, "Unknown title")
    if settings.tmdb_enabled and m.tmdb_id:
        tmdb.refresh_providers(db, media_id)
        m = get_media(db, media_id) or m
    ctx = build_ctx(db, user)
    if log:
        apply_action(db, user, media_id, "impression_detail")
        db.commit()

    match = None
    if ctx.alpha > 0:
        scored = score_pool(db, ctx, pool=[m], respect_history=False)
        # Calibrate against the full catalog so the percent matches what the deck shows.
        raw, sim = personal_score(m, ctx)
        all_raw = sorted(personal_score(x, ctx)[0] for x in all_media(db))
        pct = sum(1 for v in all_raw if v <= raw) / len(all_raw)
        closeness = min(1.0, max(0.0, sim) / 0.5)
        because, because_id, reasons = explain(m, ctx, lambda mid: get_media(db, mid))
        match = {
            "match_percent": int(round(50 + 49 * (0.55 * pct + 0.45 * closeness))),
            "because": because,
            "because_media_id": because_id,
            "reasons": reasons,
            "availability": scored[0].availability if scored else None,
        }

    row = current_action(db, user.id, media_id)
    card = media_card(m)
    card.update(
        {
            "qa": {
                "about": m.overview,
                "format": ("Movie · " if m.type == "movie" else "Series · ") + card["runtime_label"],
                "cast": m.cast,
                "creator": m.creator,
                "creator_label": "Directed by" if m.type == "movie" else "Created by",
                "trailer": trailer_links(m),
                "content_notes": [{"flag": f, "label": FLAG_LABELS.get(f, f)} for f in m.content_flags],
                "certification_label": CERT_LABELS.get(m.certification or "", None),
                "where_to_watch": watch_info(m, set(user.subscription_providers or [])),
                "match": match,
            },
            "your_action": {"action": row.action, "rating": row.rating} if row else None,
            "friends_saved": ctx.friend_likes.get(m.id, []),
            "similar": similar_items(db, m, limit=8, ctx=ctx),
        }
    )
    return card


@router.get("/{media_id}/similar")
def similar(media_id: str, limit: int = Query(12, ge=1, le=40), user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    m = get_media(db, media_id)
    if m is None:
        raise HTTPException(404, "Unknown title")
    return {"items": similar_items(db, m, limit=limit, ctx=build_ctx(db, user, with_social=False))}


@router.get("/{media_id}/watch-in-india")
def watch_in_india(media_id: str, log: bool = True, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    m = get_media(db, media_id)
    if m is None:
        raise HTTPException(404, "Unknown title")
    if log:
        apply_action(db, user, media_id, "watch_intent")
        db.commit()
    return {"media_id": m.id, "title": m.title, **watch_info(m, set(user.subscription_providers or []))}
