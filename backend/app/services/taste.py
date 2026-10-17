"""Taste profile: derived from a user's current list state with exponential time decay.

The profile is rebuilt from scratch after every list change, which keeps it consistent under
undo, list edits and imports (a few hundred rows per user is cheap to recompute).
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import User, UserMediaAction, utcnow
from ..recs.embed import DIM, normalize
from .catalog import get_media

ACTION_WEIGHT = {"must_visit": 2.0, "liked": 1.5, "watchlist": 1.0, "undecided": 0.3, "rejected": -1.0}
RATING_WEIGHT = {5: 2.0, 4: 1.2, 3: 0.3, 2: -0.6, 1: -1.2}


def action_weight(action: str, rating: int | None) -> float:
    if action == "watched":
        return RATING_WEIGHT.get(rating or 0, 0.8)
    return ACTION_WEIGHT.get(action, 0.0)


def decay(updated_at: dt.datetime, now: dt.datetime) -> float:
    age_days = max(0.0, (now - updated_at).total_seconds() / 86400)
    # Floor keeps long-standing favourites from vanishing entirely.
    return max(0.25, 0.5 ** (age_days / settings.taste_half_life_days))


def _top(d: dict[str, float], n: int) -> dict[str, float]:
    items = sorted(d.items(), key=lambda kv: abs(kv[1]), reverse=True)[:n]
    return {k: round(v, 4) for k, v in items}


def compute_taste(db: Session, user_id: str) -> dict:
    rows = db.execute(
        select(
            UserMediaAction.media_id, UserMediaAction.action, UserMediaAction.rating, UserMediaAction.updated_at
        ).where(UserMediaAction.user_id == user_id)
    ).all()
    now = utcnow()
    genres: dict[str, float] = {}
    keywords: dict[str, float] = {}
    people: dict[str, float] = {}
    languages: dict[str, float] = {}
    decades: dict[str, float] = {}
    pos = [0.0] * DIM
    neg = [0.0] * DIM
    pos_mass = neg_mass = 0.0
    seeds: list[tuple[float, str, str]] = []
    counts: Counter[str] = Counter()

    for media_id, action, rating, updated_at in rows:
        counts[action] += 1
        m = get_media(db, media_id)
        if m is None:
            continue
        w = action_weight(action, rating) * decay(updated_at, now)
        if w == 0:
            continue
        g_fac, k_fac = (1.0, 0.7) if w > 0 else (0.6, 0.45)
        for g in m.genres:
            genres[g] = genres.get(g, 0.0) + w * g_fac
        for k in m.keywords:
            k = k.lower()
            keywords[k] = keywords.get(k, 0.0) + w * k_fac
        for p in ([m.creator] if m.creator else []) + m.cast[:3]:
            people[p] = people.get(p, 0.0) + w * 0.5
        if w > 0:
            languages[m.language] = languages.get(m.language, 0.0) + w
            if m.year:
                dec = f"{m.year // 10 * 10}s"
                decades[dec] = decades.get(dec, 0.0) + w
            if m.embedding:
                pos = [a + w * b for a, b in zip(pos, m.embedding)]
            pos_mass += w
            seeds.append((w, m.id, m.title))
        else:
            if m.embedding:
                neg = [a + (-w) * b for a, b in zip(neg, m.embedding)]
            neg_mass += -w

    seeds.sort(reverse=True)
    return {
        "genres": _top(genres, 40),
        "keywords": _top(keywords, 200),
        "people": _top(people, 80),
        "languages": _top(languages, 20),
        "decades": _top(decades, 12),
        "pos_centroid": normalize(pos) if pos_mass else [],
        "neg_centroid": normalize(neg) if neg_mass else [],
        "pos_mass": round(pos_mass, 4),
        "neg_mass": round(neg_mass, 4),
        "counts": dict(counts),
        "n_actions": len(rows),
        "n_positive": sum(counts[a] for a in ("watchlist", "must_visit", "liked"))
        + sum(1 for r in rows if r[1] == "watched" and (r[2] or 4) >= 3),
        "seeds": [{"media_id": mid, "title": title, "weight": round(w, 3)} for w, mid, title in seeds[:40]],
        "updated_at": now.isoformat(),
    }


def refresh_taste(db: Session, user: User) -> dict:
    user.taste = compute_taste(db, user.id)
    return user.taste
