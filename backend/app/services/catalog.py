"""In-memory catalog snapshot, seeding and media serialization.

The recommender scores every eligible title on each feed request, so the catalog is kept as
lightweight immutable snapshots in process memory and invalidated whenever titles change.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import MediaItem
from ..recs.embed import build_embeddings
from .images import proxied

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
# Poster / title-card / logo URLs found by scripts/fetch_artwork.py (keyed by "Title|type").
ARTWORK_FILE = DATA_FILE.with_name("artwork.json")

LANG_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ko": "Korean",
    "ja": "Japanese",
    "te": "Telugu",
    "ta": "Tamil",
    "kn": "Kannada",
    "ml": "Malayalam",
    "bn": "Bengali",
    "mr": "Marathi",
    "es": "Spanish",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "zh": "Chinese",
}

CERT_ORDER = {"U": 0, "UA": 1, "A": 2}
CERT_LABELS = {"U": "U · All ages", "UA": "UA · 13+ with guidance", "A": "A · Adults"}
FLAG_LABELS = {
    "violence": "Violence",
    "gore": "Gore",
    "sexual": "Sexual content",
    "substance": "Drug / alcohol use",
    "profanity": "Strong language",
    "disturbing": "Disturbing themes",
}


@dataclass(slots=True)
class Media:
    id: str
    tmdb_id: int | None
    type: str
    title: str
    overview: str
    tagline: str | None
    year: int | None
    genres: list[str]
    keywords: list[str]
    cast: list[str]
    creator: str | None
    runtime_minutes: int | None
    season_count: int | None
    language: str
    certification: str | None
    content_flags: list[str]
    poster_url: str | None
    backdrop_url: str | None
    logo_url: str | None
    image_source: str | None
    trailer_key: str | None
    popularity: float
    vote_average: float | None
    providers_in: list[dict]
    embedding: list[float] = field(default_factory=list)
    source: str = "seed"


def snapshot(m: MediaItem) -> Media:
    return Media(
        id=m.id,
        tmdb_id=m.tmdb_id,
        type=m.type,
        title=m.title,
        overview=m.overview or "",
        tagline=m.tagline,
        year=m.year,
        genres=list(m.genres or []),
        keywords=list(m.keywords or []),
        cast=list(m.cast or []),
        creator=m.creator,
        runtime_minutes=m.runtime_minutes,
        season_count=m.season_count,
        language=m.language or "en",
        certification=m.certification,
        content_flags=list(m.content_flags or []),
        poster_url=m.poster_url,
        backdrop_url=m.backdrop_url,
        logo_url=m.logo_url,
        image_source=m.image_source,
        trailer_key=m.trailer_key,
        popularity=float(m.popularity or 0.0),
        vote_average=m.vote_average,
        providers_in=list(m.providers_in or []),
        embedding=list(m.embedding or []),
        source=m.source,
    )


class _Cache:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.items: list[Media] = []
        self.by_id: dict[str, Media] = {}
        self.loaded = False

    def invalidate(self) -> None:
        with self.lock:
            self.loaded = False

    def ensure(self, db: Session) -> None:
        if self.loaded:
            return
        with self.lock:
            if self.loaded:
                return
            rows = db.scalars(select(MediaItem)).all()
            items = [snapshot(r) for r in rows]
            self.items = items
            self.by_id = {m.id: m for m in items}
            self.loaded = True


_cache = _Cache()


def all_media(db: Session) -> list[Media]:
    _cache.ensure(db)
    return _cache.items


def get_media(db: Session, media_id: str) -> Media | None:
    _cache.ensure(db)
    return _cache.by_id.get(media_id)


def invalidate_cache() -> None:
    _cache.invalidate()


# ---------------------------------------------------------------- seeding


def _seed_row(raw: dict) -> MediaItem:
    year = raw.get("y")
    return MediaItem(
        type=raw["type"],
        title=raw["t"],
        original_title=raw["t"],
        overview=raw.get("o", ""),
        year=year,
        release_date=dt.date(year, 1, 1) if year else None,
        genres=raw.get("g", []),
        keywords=raw.get("k", []),
        cast=raw.get("c", []),
        creator=raw.get("d"),
        runtime_minutes=raw.get("rt"),
        season_count=raw.get("s"),
        language=raw.get("lang", "en"),
        certification=raw.get("cert"),
        content_flags=raw.get("f", []),
        popularity=float(raw.get("pop", 50)),
        vote_average=raw.get("r"),
        providers_in=[{"name": p, "type": "flatrate"} for p in raw.get("prov", [])],
        source="seed",
    )


def rebuild_embeddings(db: Session) -> int:
    rows = db.scalars(select(MediaItem)).all()
    vectors = build_embeddings(rows)
    for row, vec in zip(rows, vectors):
        row.embedding = vec
    db.commit()
    invalidate_cache()
    return len(rows)


def artwork_key(title: str, media_type: str) -> str:
    return f"{title}|{media_type}"


def load_artwork() -> dict[str, dict]:
    if not ARTWORK_FILE.exists():
        return {}
    return json.loads(ARTWORK_FILE.read_text(encoding="utf-8"))


def apply_artwork(db: Session, overwrite: bool = False) -> int:
    """Fill poster/backdrop/logo URLs from data/artwork.json. Titles with TMDB artwork are left alone."""
    art = load_artwork()
    if not art:
        return 0
    changed = 0
    for row in db.scalars(select(MediaItem)).all():
        entry = art.get(artwork_key(row.title, row.type))
        if not entry or (row.source == "tmdb" and row.poster_url):
            continue
        has_art = row.poster_url or row.backdrop_url or row.logo_url
        if has_art and not overwrite:
            continue
        row.poster_url = entry.get("poster") or None
        row.backdrop_url = entry.get("backdrop") or None
        row.logo_url = entry.get("logo") or None
        row.image_source = entry.get("source") or None
        changed += 1
    if changed:
        db.commit()
        invalidate_cache()
    return changed


def seed_catalog(db: Session, force: bool = False) -> int:
    """Load the bundled catalog when the media table is empty. Returns rows inserted."""
    count = db.scalar(select(func.count()).select_from(MediaItem)) or 0
    if count and not force:
        return 0
    existing = {(t.lower(), ty) for t, ty in db.execute(select(MediaItem.title, MediaItem.type)).all()}
    raw_items = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    added = 0
    for raw in raw_items:
        if (raw["t"].lower(), raw["type"]) in existing:
            continue
        db.add(_seed_row(raw))
        added += 1
    db.commit()
    rebuild_embeddings(db)
    return added


# ---------------------------------------------------------------- serialization


def runtime_label(m: Media) -> str:
    if m.type == "movie":
        if not m.runtime_minutes:
            return "Movie"
        h, mins = divmod(m.runtime_minutes, 60)
        return f"{h}h {mins}m" if h else f"{mins}m"
    parts = []
    if m.season_count:
        parts.append(f"{m.season_count} season{'s' if m.season_count != 1 else ''}")
    if m.runtime_minutes:
        parts.append(f"~{m.runtime_minutes}m episodes")
    return " · ".join(parts) or "Series"


def logline(text: str) -> str:
    text = (text or "").strip()
    for sep in (". ", "! ", "? "):
        idx = text.find(sep)
        if 0 < idx < 220:
            return text[: idx + 1]
    return text if len(text) <= 220 else text[:217].rsplit(" ", 1)[0] + "…"


def media_card(m: Media) -> dict:
    return {
        "media_id": m.id,
        "tmdb_id": m.tmdb_id,
        "title": m.title,
        "type": m.type,
        "year": m.year,
        "genres": m.genres,
        "keywords": m.keywords[:8],
        "overview": m.overview,
        "logline": logline(m.overview),
        "tagline": m.tagline,
        "poster_url": proxied(m.poster_url),
        "backdrop_url": proxied(m.backdrop_url),
        "logo_url": proxied(m.logo_url),
        "image_source": m.image_source,
        "runtime_minutes": m.runtime_minutes,
        "season_count": m.season_count,
        "runtime_label": runtime_label(m),
        "language": m.language,
        "language_name": LANG_NAMES.get(m.language, m.language.upper()),
        "certification": m.certification,
        "content_flags": m.content_flags,
        "cast": m.cast[:4],
        "creator": m.creator,
        "vote_average": m.vote_average,
        "providers": [p["name"] for p in m.providers_in],
    }


def total_minutes(m: Media) -> int | None:
    """Rough commitment: movie runtime, or one episode for series."""
    return m.runtime_minutes
