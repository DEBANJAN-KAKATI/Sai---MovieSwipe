"""User creation helpers, serialization and demo personas (bots for solo demos of social features)."""

from __future__ import annotations

import re
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Friendship, MediaItem, User, UserMediaAction, utcnow
from ..security import random_code
from .taste import refresh_taste

AVATARS = ["🍿", "🎬", "🎞️", "📽️", "🌙", "🦊", "🐼", "🐙", "🦉", "🌶️", "🪐", "🎧"]

DEFAULT_PRIVACY = {"share_activity": True, "public_profile": False}
DEFAULT_PREFERENCES = {"spoiler_shield": False, "languages": [], "haptics": True, "blind_mode": False}
DEFAULT_FILTERS = {"blocked_genres": [], "blocked_flags": [], "max_certification": None}

PERSONAS = [
    {
        "username": "demo-aanya",
        "display_name": "Aanya",
        "avatar": "🕵️",
        "tagline": "Whodunits, slow-burn crime and anything with a twist",
        "liked": ["Delhi Crime", "Scam 1992: The Harshad Mehta Story", "Sherlock", "Kahaani", "Drishyam", "Knives Out",
                  "Andhadhun", "Dark", "Broadchurch", "Mare of Easttown", "Psych"],
        "watchlist": ["Paatal Lok", "Aranyak", "Memories of Murder", "Only Murders in the Building", "Poker Face"],
        "rejected": ["The Hangover", "Superbad", "Avengers: Endgame"],
    },
    {
        "username": "demo-rohan",
        "display_name": "Rohan",
        "avatar": "🚀",
        "tagline": "Big ideas, big screens: sci-fi and spectacle",
        "liked": ["Interstellar", "Inception", "Dune", "The Matrix", "Arrival", "The Expanse", "RRR", "Severance",
                  "Mad Max: Fury Road", "Blade Runner 2049", "The Dark Knight"],
        "watchlist": ["Primer", "Westworld", "Ex Machina", "Baahubali: The Beginning", "Oppenheimer"],
        "rejected": ["Bridgerton", "Pride & Prejudice", "Crazy Rich Asians"],
    },
    {
        "username": "demo-meera",
        "display_name": "Meera",
        "avatar": "☕",
        "tagline": "Comfort comedies and feel-good stories",
        "liked": ["Panchayat", "Gullak", "The Office", "Ted Lasso", "Brooklyn Nine-Nine", "3 Idiots", "Queen",
                  "Paddington 2", "Schitt's Creek", "Laapataa Ladies", "Kumbalangi Nights"],
        "watchlist": ["Parks and Recreation", "The Good Place", "Zindagi Na Milegi Dobara", "Coco", "Jab We Met"],
        "rejected": ["Hereditary", "Hannibal", "Se7en", "Train to Busan"],
    },
]


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:20] or "user"


def unique_username(db: Session, base: str) -> str:
    base = _slug(base)
    candidate = base
    while db.scalar(select(User.id).where(User.username == candidate)):
        candidate = f"{base}-{secrets.token_hex(2)}"
    return candidate


def new_friend_code(db: Session) -> str:
    while True:
        code = f"MS-{random_code(6)}"
        if not db.scalar(select(User.id).where(User.friend_code == code)):
            return code


def create_user(
    db: Session,
    display_name: str | None = None,
    *,
    username: str | None = None,
    is_guest: bool = True,
    is_bot: bool = False,
    avatar: str | None = None,
) -> User:
    name = (display_name or "").strip() or "Movie buff"
    user = User(
        username=unique_username(db, username or (f"guest-{secrets.token_hex(3)}" if is_guest else name)),
        display_name=name,
        is_guest=is_guest,
        is_bot=is_bot,
        avatar=avatar or secrets.choice(AVATARS),
        friend_code=new_friend_code(db),
        privacy_settings=dict(DEFAULT_PRIVACY),
        preferences=dict(DEFAULT_PREFERENCES),
        content_filters=dict(DEFAULT_FILTERS),
        subscription_providers=[],
        taste={},
    )
    db.add(user)
    db.flush()
    return user


def public_user(u: User) -> dict:
    return {
        "user_id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "avatar": u.avatar,
        "is_bot": u.is_bot,
    }


def me_payload(u: User) -> dict:
    return {
        **public_user(u),
        "email": u.email,
        "is_guest": u.is_guest,
        "region": u.region,
        "friend_code": u.friend_code,
        "onboarded": u.onboarded,
        "subscription_providers": u.subscription_providers or [],
        "content_filters": {**DEFAULT_FILTERS, **(u.content_filters or {})},
        "preferences": {**DEFAULT_PREFERENCES, **(u.preferences or {})},
        "privacy_settings": {**DEFAULT_PRIVACY, **(u.privacy_settings or {})},
        "created_at": u.created_at.isoformat() + "Z",
    }


def ensure_persona(db: Session, spec: dict) -> User:
    user = db.scalar(select(User).where(User.username == spec["username"]))
    if user is not None:
        return user
    user = create_user(db, spec["display_name"], username=spec["username"], is_guest=False, is_bot=True,
                       avatar=spec["avatar"])
    user.onboarded = True
    user.preferences = {**DEFAULT_PREFERENCES, "tagline": spec["tagline"]}
    titles = {t.lower(): mid for mid, t in db.execute(select(MediaItem.id, MediaItem.title)).all()}
    now = utcnow()
    for action in ("liked", "watchlist", "rejected"):
        for title in spec[action]:
            mid = titles.get(title.lower())
            if mid:
                db.add(UserMediaAction(user_id=user.id, media_id=mid, action=action, created_at=now, updated_at=now))
    db.flush()
    refresh_taste(db, user)
    return user


def befriend(db: Session, a: User, b: User) -> Friendship:
    existing = db.scalar(
        select(Friendship).where(
            ((Friendship.requester_id == a.id) & (Friendship.addressee_id == b.id))
            | ((Friendship.requester_id == b.id) & (Friendship.addressee_id == a.id))
        )
    )
    if existing:
        existing.status = "accepted"
        return existing
    f = Friendship(requester_id=a.id, addressee_id=b.id, status="accepted")
    db.add(f)
    db.flush()
    return f
