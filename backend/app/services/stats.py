"""Taste summary ("Taste DNA"), streaks and badges."""

from __future__ import annotations

import datetime as dt
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import CollabList, Match, SessionMember, SwipeEvent, User, UserMediaAction, utcnow
from .catalog import LANG_NAMES, get_media
from .social import friend_ids

IST = dt.timedelta(hours=5, minutes=30)
INDIAN_LANGS = {"hi", "te", "ta", "kn", "ml", "bn", "mr", "gu", "pa"}

ARCHETYPES = {
    "Crime": ("Case Cracker", "You live for the reveal — procedurals, cons and cat-and-mouse."),
    "Mystery": ("Puzzle Solver", "Clues, twists and whodunits keep you hooked."),
    "Comedy": ("Comfort Connoisseur", "You know exactly what makes a good night in: laughs."),
    "Sci-Fi": ("Future Gazer", "Big ideas, other worlds and mind-bending premises."),
    "Drama": ("Feels Collector", "Character-driven stories that stay with you."),
    "Thriller": ("Edge-of-Seat Addict", "Tension is your love language."),
    "Romance": ("Hopeless Romantic", "Meet-cutes, slow burns and grand gestures."),
    "Horror": ("Fearless Night Owl", "Lights off, volume up."),
    "Action": ("Adrenaline Junkie", "Stunts, chases and spectacle."),
    "Animation": ("Forever Young", "Animated worlds with big hearts."),
    "Documentary": ("Curious Mind", "Real stories, real people, real wow."),
    "Fantasy": ("Realm Walker", "Dragons, kingdoms and magic systems."),
    "History": ("Time Traveller", "Period pieces and true events."),
    "Family": ("Family Night Captain", "Crowd-pleasers everyone can share."),
    "Sports": ("Underdog Believer", "Comebacks and final-minute glory."),
    "Music": ("Rhythm Chaser", "Stories that sing."),
    "Adventure": ("Explorer", "Journeys, quests and wide horizons."),
    "War": ("Battle Historian", "Courage under fire."),
}


def streaks(db: Session, user_id: str) -> tuple[int, int]:
    stamps = db.scalars(select(SwipeEvent.created_at).where(SwipeEvent.user_id == user_id)).all()
    days = sorted({(t + IST).date() for t in stamps})
    if not days:
        return 0, 0
    best = run = 1
    for a, b in zip(days, days[1:]):
        run = run + 1 if (b - a).days == 1 else 1
        best = max(best, run)
    today = (utcnow() + IST).date()
    current = 0
    if days[-1] >= today - dt.timedelta(days=1):
        current = 1
        for a, b in zip(reversed(days[:-1]), reversed(days[1:])):
            if (b - a).days == 1:
                current += 1
            else:
                break
    return current, best


def _badge(key: str, label: str, emoji: str, desc: str, value: int, target: int) -> dict:
    return {
        "key": key,
        "label": label,
        "emoji": emoji,
        "description": desc,
        "progress": min(value, target),
        "target": target,
        "earned": value >= target,
    }


def taste_summary(db: Session, user: User) -> dict:
    taste = user.taste or {}
    rows = db.execute(
        select(UserMediaAction.media_id, UserMediaAction.action, UserMediaAction.rating).where(
            UserMediaAction.user_id == user.id
        )
    ).all()
    counts = Counter(a for _, a, _ in rows)
    positive = [mid for mid, a, r in rows if a in ("watchlist", "must_visit", "liked") or (a == "watched" and (r or 4) >= 3)]
    pos_media = [m for m in (get_media(db, mid) for mid in positive) if m]

    n_swipes = db.scalar(select(func.count()).select_from(SwipeEvent).where(SwipeEvent.user_id == user.id)) or 0
    n_matches = db.scalar(
        select(func.count(func.distinct(Match.id)))
        .select_from(Match)
        .join(SessionMember, SessionMember.session_id == Match.session_id)
        .where(SessionMember.user_id == user.id)
    ) or 0
    n_friends = len(friend_ids(db, user.id))
    n_public_lists = db.scalar(
        select(func.count()).select_from(CollabList).where(CollabList.owner_id == user.id, CollabList.is_public.is_(True))
    ) or 0
    current_streak, best_streak = streaks(db, user.id)

    genres = {g: w for g, w in (taste.get("genres") or {}).items() if w > 0}
    gmax = max(genres.values(), default=1.0)
    top_genres = [
        {"name": g, "score": round(100 * w / gmax)} for g, w in sorted(genres.items(), key=lambda kv: -kv[1])[:8]
    ]
    keywords = {k: w for k, w in (taste.get("keywords") or {}).items() if w > 0}
    kmax = max(keywords.values(), default=1.0)
    top_keywords = [
        {"name": k, "score": round(100 * w / kmax)} for k, w in sorted(keywords.items(), key=lambda kv: -kv[1])[:14]
    ]
    avoided = [g for g, w in sorted((taste.get("genres") or {}).items(), key=lambda kv: kv[1]) if w < 0][:3]
    lang_counts = Counter(m.language for m in pos_media)
    decade_counts = Counter(f"{m.year // 10 * 10}s" for m in pos_media if m.year)
    type_counts = Counter(m.type for m in pos_media)
    rated = sum(1 for _, a, r in rows if a == "watched" and r)

    archetype = None
    if top_genres:
        label, blurb = ARCHETYPES.get(top_genres[0]["name"], ("Eclectic Viewer", "Your taste refuses to be boxed in."))
        archetype = {"label": label, "blurb": blurb}

    crime_pos = sum(1 for m in pos_media if "Crime" in m.genres)
    indian_pos = sum(1 for m in pos_media if m.language in INDIAN_LANGS)
    badges = [
        _badge("first_swipe", "First Swipe", "👆", "Make your first swipe", n_swipes, 1),
        _badge("century", "Century", "💯", "Swipe 100 times", n_swipes, 100),
        _badge("binge_planner", "Binge Planner", "🗓️", "Save 25 titles to your Watch List",
               counts["watchlist"] + counts["must_visit"], 25),
        _badge("procedural", "Procedural Explorer", "🔎", "Save 10 crime titles", crime_pos, 10),
        _badge("globetrotter", "Globetrotter", "🌏", "Love titles in 4 languages", len(lang_counts), 4),
        _badge("desi", "Desi Cinephile", "🪔", "Love 10 Indian-language titles", indian_pos, 10),
        _badge("critic", "Critic", "⭐", "Rate 10 titles you watched", rated, 10),
        _badge("matchmaker", "Matchmaker", "💞", "Get your first duo match", n_matches, 1),
        _badge("perfect_pair", "Perfect Pair", "👯", "Reach 10 session matches", n_matches, 10),
        _badge("social", "Social Butterfly", "🦋", "Add 3 friends", n_friends, 3),
        _badge("on_fire", "On Fire", "🔥", "Swipe 7 days in a row", best_streak, 7),
        _badge("curator", "Curator", "📚", "Publish a public list", n_public_lists, 1),
    ]

    return {
        "archetype": archetype,
        "top_genres": top_genres,
        "top_keywords": top_keywords,
        "avoided_genres": avoided,
        "languages": [
            {"code": c, "name": LANG_NAMES.get(c, c), "count": n} for c, n in lang_counts.most_common(6)
        ],
        "decades": [{"name": d, "count": n} for d, n in sorted(decade_counts.items())],
        "type_split": {"movie": type_counts.get("movie", 0), "tv": type_counts.get("tv", 0)},
        "counts": {
            "watchlist": counts["watchlist"],
            "must_visit": counts["must_visit"],
            "undecided": counts["undecided"],
            "rejected": counts["rejected"],
            "liked": counts["liked"],
            "watched": counts["watched"],
            "swipes": n_swipes,
            "matches": n_matches,
            "friends": n_friends,
        },
        "accept_rate": round(100 * len(positive) / len(rows)) if rows else None,
        "streak": {"current": current_streak, "best": best_streak},
        "personalization": {
            "signals": taste.get("n_actions", 0),
            "level": 0 if not taste.get("n_positive") else (70 if taste.get("n_actions", 0) < 20 else 90),
        },
        "badges": badges,
        "seeds": [s["title"] for s in (taste.get("seeds") or [])[:5]],
    }
