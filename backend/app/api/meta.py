"""Static metadata for the client + an admin metrics endpoint."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import FeedImpression, Match, MediaItem, SwipeEvent, SwipeSession, User, utcnow
from ..recs.moods import moods_meta
from ..services.catalog import CERT_LABELS, FLAG_LABELS, LANG_NAMES, all_media, media_card
from ..services.watch_links import DISCLAIMER, PROVIDERS_IN

router = APIRouter(tags=["meta"])


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    items = all_media(db)
    langs = sorted({m.language for m in items}, key=lambda c: -sum(1 for m in items if m.language == c))
    genres = sorted({g for m in items for g in m.genres})
    return {
        "providers": PROVIDERS_IN,
        "moods": moods_meta(),
        "genres": genres,
        "languages": [{"code": c, "name": LANG_NAMES.get(c, c.upper())} for c in langs],
        "content_flags": [{"key": k, "label": v} for k, v in FLAG_LABELS.items()],
        "certifications": [{"key": k, "label": v} for k, v in CERT_LABELS.items()],
        "catalog_size": len(items),
        "tmdb_enabled": settings.tmdb_enabled,
        "disclaimers": [
            DISCLAIMER,
            "sai does not host video content.",
            "TV artwork from TVmaze (tvmaze.com); film posters from English Wikipedia articles (non-free images used "
            "there under fair use). Images are cached on your server for personal use.",
            "Title metadata from the bundled sai catalog"
            + (" and The Movie Database (TMDB). This product uses the TMDB API but is not endorsed or certified by TMDB."
               if settings.tmdb_enabled else "."),
        ],
    }


@router.get("/public/showcase")
def showcase(db: Session = Depends(get_db)):
    """Popular titles with real posters for the public landing page (no sign-in needed)."""
    items = [m for m in all_media(db) if m.poster_url]
    items.sort(key=lambda m: -m.popularity)
    tv = [m for m in items if m.type == "tv"][:12]
    films = [m for m in items if m.type == "movie"][:12]
    mixed = [m for pair in zip(tv, films) for m in pair]
    langs = {m.language for m in all_media(db)}
    return {
        "posters": [media_card(m) for m in mixed],
        "catalog_size": len(all_media(db)),
        "language_count": len(langs),
    }


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/admin/metrics")
def admin_metrics(x_admin_token: str = Header(default=""), db: Session = Depends(get_db)):
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(404, "Not found")
    now = utcnow()
    day = now - dt.timedelta(days=1)
    swipes_24h = db.scalar(select(func.count()).select_from(SwipeEvent).where(SwipeEvent.created_at >= day)) or 0
    positives_24h = db.scalar(
        select(func.count()).select_from(SwipeEvent).where(
            SwipeEvent.created_at >= day, SwipeEvent.action.in_(("watchlist", "must_visit"))
        )
    ) or 0
    impressions_24h = db.scalar(
        select(func.count()).select_from(FeedImpression).where(FeedImpression.shown_at >= day)
    ) or 0
    sessions_total = db.scalar(select(func.count()).select_from(SwipeSession)) or 0
    sessions_with_match = db.scalar(select(func.count(func.distinct(Match.session_id)))) or 0
    intents = db.scalar(
        select(func.count()).select_from(SwipeEvent).where(SwipeEvent.created_at >= day,
                                                           SwipeEvent.action == "watch_intent")
    ) or 0
    return {
        "users_total": db.scalar(select(func.count()).select_from(User).where(User.is_bot.is_(False))),
        "dau": db.scalar(select(func.count(func.distinct(SwipeEvent.user_id))).where(SwipeEvent.created_at >= day)),
        "swipes_24h": swipes_24h,
        "accept_rate_24h": round(positives_24h / impressions_24h, 3) if impressions_24h else None,
        "watch_link_ctr_24h": round(intents / impressions_24h, 3) if impressions_24h else None,
        "sessions_total": sessions_total,
        "session_match_rate": round(sessions_with_match / sessions_total, 3) if sessions_total else None,
        "catalog_size": db.scalar(select(func.count()).select_from(MediaItem)),
        "tmdb_enabled": settings.tmdb_enabled,
    }
