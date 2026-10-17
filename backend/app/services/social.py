"""Friend graph helpers, privacy-safe social signals and compatibility scores."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import POSITIVE_ACTIONS, Friendship, User, UserMediaAction, utcnow
from ..recs.embed import dot


def friend_ids(db: Session, user_id: str) -> list[str]:
    rows = db.execute(
        select(Friendship.requester_id, Friendship.addressee_id).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        )
    ).all()
    return [b if a == user_id else a for a, b in rows]


def are_friends(db: Session, a: str, b: str) -> bool:
    return b in friend_ids(db, a)


def shares_activity(user: User) -> bool:
    return (user.privacy_settings or {}).get("share_activity", True)


def friend_positive_map(db: Session, user_id: str, days: int = 30) -> dict[str, list[str]]:
    """media_id -> display names of friends who recently saved it. Never exposes rejects."""
    ids = friend_ids(db, user_id)
    if not ids:
        return {}
    friends = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids))).all()}
    allowed = [fid for fid, u in friends.items() if shares_activity(u)]
    if not allowed:
        return {}
    since = utcnow() - dt.timedelta(days=days)
    rows = db.execute(
        select(UserMediaAction.media_id, UserMediaAction.user_id).where(
            UserMediaAction.user_id.in_(allowed),
            UserMediaAction.action.in_(POSITIVE_ACTIONS),
            UserMediaAction.updated_at >= since,
        )
    ).all()
    out: dict[str, list[str]] = {}
    for media_id, uid in rows:
        out.setdefault(media_id, []).append(friends[uid].display_name)
    return out


def positive_set(db: Session, user_id: str) -> set[str]:
    return set(
        db.scalars(
            select(UserMediaAction.media_id).where(
                UserMediaAction.user_id == user_id,
                or_(
                    UserMediaAction.action.in_(POSITIVE_ACTIONS),
                    (UserMediaAction.action == "watched") & ((UserMediaAction.rating >= 3) | (UserMediaAction.rating.is_(None))),
                ),
            )
        ).all()
    )


def compatibility(db: Session, a: User, b: User) -> dict:
    """Overlap score: Jaccard of saved titles blended with taste-centroid cosine similarity."""
    sa, sb = positive_set(db, a.id), positive_set(db, b.id)
    union = sa | sb
    jaccard = len(sa & sb) / len(union) if union else 0.0
    cos = dot((a.taste or {}).get("pos_centroid"), (b.taste or {}).get("pos_centroid"))
    ga = (a.taste or {}).get("genres", {})
    gb = (b.taste or {}).get("genres", {})
    shared_genres = sorted(
        (g for g in ga if ga.get(g, 0) > 0 and gb.get(g, 0) > 0), key=lambda g: -(ga[g] + gb[g])
    )[:3]
    # Jaccard on small sets is harsh; lean on the embedding similarity and boost overlap.
    raw = 0.35 * min(1.0, jaccard * 2.5) + 0.65 * max(0.0, cos)
    percent = round(100 * min(1.0, raw ** 0.7)) if (sa and sb) else 0
    return {
        "percent": percent,
        "shared_count": len(sa & sb),
        "shared_ids": list(sa & sb),
        "shared_genres": shared_genres,
    }
