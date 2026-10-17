"""TMDB integration (optional — enabled when TMDB_API_KEY is set).

Accepts either a v3 API key or a v4 read-access token. Used by scripts/sync_tmdb.py to grow the
catalog, by search to import titles on demand, and to refresh India watch providers.
"""

from __future__ import annotations

import datetime as dt
import logging
import math

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import MediaItem, utcnow
from .catalog import invalidate_cache

log = logging.getLogger("movieswipe.tmdb")

API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p"

GENRE_MAP = {
    "Science Fiction": ["Sci-Fi"],
    "Sci-Fi & Fantasy": ["Sci-Fi", "Fantasy"],
    "Action & Adventure": ["Action", "Adventure"],
    "War & Politics": ["War"],
    "Kids": ["Family"],
    "TV Movie": [],
}
PROVIDER_MAP = {
    "Amazon Prime Video": "Prime Video",
    "Amazon Prime Video with Ads": "Prime Video",
    "Hotstar": "JioHotstar",
    "Disney Plus Hotstar": "JioHotstar",
    "Jio Hotstar": "JioHotstar",
    "JioCinema": "JioHotstar",
    "Sony Liv": "SonyLIV",
    "Zee5": "ZEE5",
    "Apple TV Plus": "Apple TV+",
    "Apple TV": "Apple TV+",
    "aha": "Aha",
    "Sun Nxt": "Sun NXT",
    "Netflix basic with Ads": "Netflix",
}
FLAG_HINTS = {
    "violence": ("violence", "murder", "serial killer", "shootout", "massacre", "gangster", "brutal"),
    "gore": ("gore", "splatter", "dismemberment", "cannibal", "body horror"),
    "sexual": ("sex", "nudity", "erotic", "prostitut"),
    "substance": ("drug", "cocaine", "heroin", "alcohol", "meth", "addiction"),
    "disturbing": ("suicide", "rape", "abuse", "torture", "self-harm", "child abuse"),
}
US_TO_IN = {"G": "U", "PG": "U", "TV-Y": "U", "TV-Y7": "U", "TV-G": "U", "TV-PG": "U",
            "PG-13": "UA", "TV-14": "UA", "R": "A", "NC-17": "A", "TV-MA": "A"}


class TMDB:
    def __init__(self, key: str | None = None, timeout: float = 8.0) -> None:
        key = key if key is not None else settings.tmdb_api_key
        self.params: dict[str, str] = {}
        headers = {"accept": "application/json"}
        if len(key) > 40:  # v4 read access token
            headers["Authorization"] = f"Bearer {key}"
        else:
            self.params["api_key"] = key
        self.client = httpx.Client(base_url=API, headers=headers, timeout=timeout)

    def get(self, path: str, **params) -> dict:
        resp = self.client.get(path, params={**self.params, **params})
        resp.raise_for_status()
        return resp.json()

    def trending(self, media_type: str, page: int = 1) -> list[dict]:
        return self.get(f"/trending/{media_type}/week", page=page).get("results", [])

    def discover_indian(self, media_type: str, page: int = 1) -> list[dict]:
        return self.get(
            f"/discover/{media_type}",
            page=page,
            sort_by="popularity.desc",
            with_original_language="hi|ta|te|ml|kn|bn|mr",
            watch_region="IN",
        ).get("results", [])

    def details(self, media_type: str, tmdb_id: int) -> dict:
        extra = "keywords,credits,videos,watch/providers," + (
            "release_dates" if media_type == "movie" else "content_ratings"
        )
        return self.get(f"/{media_type}/{tmdb_id}", append_to_response=extra)

    def providers(self, media_type: str, tmdb_id: int) -> dict:
        return self.get(f"/{media_type}/{tmdb_id}/watch/providers")

    def search(self, query: str) -> list[dict]:
        res = self.get("/search/multi", query=query, include_adult="false", region="IN").get("results", [])
        return [r for r in res if r.get("media_type") in ("movie", "tv")]

    def search_typed(self, media_type: str, title: str, year: int | None) -> list[dict]:
        params = {"query": title, "include_adult": "false"}
        if year:
            params["year" if media_type == "movie" else "first_air_date_year"] = str(year)
        return self.get(f"/search/{media_type}", **params).get("results", [])


# ---------------------------------------------------------------- mapping


def _genres(raw: list[dict]) -> list[str]:
    out: list[str] = []
    for g in raw:
        for name in GENRE_MAP.get(g["name"], [g["name"]]):
            if name not in out:
                out.append(name)
    return out


def _providers_in(payload: dict) -> list[dict]:
    region = (payload.get("results") or {}).get("IN") or {}
    link = region.get("link")
    out: list[dict] = []
    seen: set[str] = set()
    for kind in ("flatrate", "free", "ads", "rent", "buy"):
        for p in region.get(kind, []) or []:
            name = PROVIDER_MAP.get(p["provider_name"], p["provider_name"])
            if name in seen:
                continue
            seen.add(name)
            out.append({"name": name, "type": "flatrate" if kind in ("free", "ads") else kind, "link": link})
    return out


def _certification(media_type: str, d: dict) -> str | None:
    by_country: dict[str, str] = {}
    if media_type == "movie":
        for r in (d.get("release_dates") or {}).get("results", []):
            certs = [x.get("certification") for x in r.get("release_dates", []) if x.get("certification")]
            if certs:
                by_country[r["iso_3166_1"]] = certs[0]
    else:
        for r in (d.get("content_ratings") or {}).get("results", []):
            if r.get("rating"):
                by_country[r["iso_3166_1"]] = r["rating"]
    cert_in = by_country.get("IN", "").upper()
    if cert_in:
        if cert_in.startswith("UA"):
            return "UA"
        if cert_in in ("U", "A"):
            return cert_in
        if cert_in == "S":
            return "A"
    return US_TO_IN.get(by_country.get("US", ""))


def _flags(keywords: list[str], cert: str | None) -> list[str]:
    flags = []
    joined = " | ".join(k.lower() for k in keywords)
    for flag, hints in FLAG_HINTS.items():
        if any(h in joined for h in hints):
            flags.append(flag)
    if cert == "A" and not flags:
        flags.append("profanity")
    return flags


def _trailer(d: dict) -> str | None:
    vids = [v for v in (d.get("videos") or {}).get("results", []) if v.get("site") == "YouTube"]
    vids.sort(key=lambda v: (v.get("type") != "Trailer", not v.get("official"), v.get("iso_639_1") != "en"))
    return vids[0]["key"] if vids else None


def map_details(media_type: str, d: dict) -> dict:
    kw_block = d.get("keywords") or {}
    keywords = [k["name"] for k in kw_block.get("keywords", kw_block.get("results", []))][:20]
    credits = d.get("credits") or {}
    cast = [c["name"] for c in credits.get("cast", [])[:6]]
    if media_type == "movie":
        title = d.get("title") or d.get("original_title") or "Untitled"
        date_str = d.get("release_date") or ""
        creator = next((c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"), None)
        runtime = d.get("runtime")
        seasons = None
    else:
        title = d.get("name") or d.get("original_name") or "Untitled"
        date_str = d.get("first_air_date") or ""
        creator = " & ".join(c["name"] for c in d.get("created_by", [])[:2]) or None
        ert = d.get("episode_run_time") or []
        runtime = ert[0] if ert else (d.get("last_episode_to_air") or {}).get("runtime")
        seasons = d.get("number_of_seasons")
    try:
        release = dt.date.fromisoformat(date_str) if date_str else None
    except ValueError:
        release = None
    cert = _certification(media_type, d)
    pop = float(d.get("popularity") or 0)
    return {
        "tmdb_id": d["id"],
        "type": media_type,
        "title": title,
        "original_title": d.get("original_title") or d.get("original_name"),
        "overview": d.get("overview") or "",
        "tagline": d.get("tagline") or None,
        "release_date": release,
        "year": release.year if release else None,
        "genres": _genres(d.get("genres", [])),
        "keywords": keywords,
        "cast": cast,
        "creator": creator,
        "runtime_minutes": runtime,
        "season_count": seasons,
        "language": d.get("original_language") or "en",
        "certification": cert,
        "content_flags": _flags(keywords, cert),
        "poster_url": f"{IMG}/w500{d['poster_path']}" if d.get("poster_path") else None,
        "backdrop_url": f"{IMG}/w780{d['backdrop_path']}" if d.get("backdrop_path") else None,
        "trailer_key": _trailer(d),
        "popularity": round(100 * (1 - math.exp(-pop / 80)), 2),
        "vote_average": d.get("vote_average"),
        "providers_in": _providers_in(d.get("watch/providers") or {}),
        "providers_checked_at": utcnow(),
        "source": "tmdb",
    }


def upsert(db: Session, fields: dict, keep_seed_semantics: bool = False) -> MediaItem:
    row = db.scalar(select(MediaItem).where(MediaItem.tmdb_id == fields["tmdb_id"], MediaItem.type == fields["type"]))
    if row is None:
        row = MediaItem(**fields)
        db.add(row)
    else:
        for key, value in fields.items():
            if keep_seed_semantics and key in ("genres", "keywords", "overview", "content_flags", "source", "title"):
                continue
            setattr(row, key, value)
    return row


def import_titles(db: Session, client: TMDB, refs: list[tuple[str, int]]) -> list[MediaItem]:
    rows = []
    for media_type, tmdb_id in refs:
        try:
            rows.append(upsert(db, map_details(media_type, client.details(media_type, tmdb_id))))
        except httpx.HTTPError as exc:
            log.warning("TMDB fetch failed for %s/%s: %s", media_type, tmdb_id, exc)
    db.commit()
    return rows


def enrich_seed_item(db: Session, client: TMDB, row: MediaItem) -> bool:
    """Attach TMDB id, poster, trailer and providers to a bundled title (keeps curated keywords)."""
    results = client.search_typed(row.type, row.title, row.year)
    if not results:
        return False
    details = client.details(row.type, results[0]["id"])
    fields = map_details(row.type, details)
    for key in ("tmdb_id", "poster_url", "backdrop_url", "trailer_key", "providers_checked_at", "tagline"):
        setattr(row, key, fields[key])
    if fields["providers_in"]:
        row.providers_in = fields["providers_in"]
    if fields["vote_average"]:
        row.vote_average = fields["vote_average"]
    return True


def refresh_providers(db: Session, media_id: str) -> None:
    """Best-effort refresh of IN providers for one title (at most daily)."""
    if not settings.tmdb_enabled:
        return
    row = db.get(MediaItem, media_id)
    if row is None or not row.tmdb_id:
        return
    if row.providers_checked_at and utcnow() - row.providers_checked_at < dt.timedelta(days=1):
        return
    try:
        payload = TMDB(timeout=4).providers(row.type, row.tmdb_id)
    except httpx.HTTPError:
        return
    row.providers_in = _providers_in(payload) or row.providers_in
    row.providers_checked_at = utcnow()
    db.commit()
    invalidate_cache()
