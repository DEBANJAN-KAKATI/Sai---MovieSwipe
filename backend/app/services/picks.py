"""'Decide for me' — Tonight's Pick from your Watch List (or a session's matches)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Match, User, UserMediaAction
from ..recs.moods import MOODS
from ..recs.rank import build_ctx, build_feed, score_pool
from .catalog import get_media, media_card, runtime_label


def _fit(minutes: int | None, m) -> tuple[float, str | None]:
    if not minutes or not m.runtime_minutes:
        return 0.0, None
    rt = m.runtime_minutes
    if m.type == "movie":
        if rt <= minutes:
            return 0.25 * (rt / minutes), f"Fits your {minutes // 60}h{minutes % 60:02d} window ({runtime_label(m)})"
        return -0.8 * ((rt - minutes) / minutes), None
    episodes = minutes // rt
    if episodes >= 1:
        return 0.15, f"About {episodes} episode{'s' if episodes != 1 else ''} in your time"
    return -0.5, None


def tonight(db: Session, user: User, minutes: int | None = None, mood: str | None = None,
            session_id: str | None = None) -> dict:
    ctx = build_ctx(db, user)
    pinned: set[str] = set()
    if session_id:
        ids = list(db.scalars(select(Match.media_id).where(Match.session_id == session_id)).all())
        source = "session matches"
    else:
        rows = db.execute(
            select(UserMediaAction.media_id, UserMediaAction.action).where(
                UserMediaAction.user_id == user.id, UserMediaAction.action.in_(("watchlist", "must_visit"))
            )
        ).all()
        ids = [mid for mid, _ in rows]
        pinned = {mid for mid, a in rows if a == "must_visit"}
        source = "your Watch List"

    pool = [m for m in (get_media(db, mid) for mid in ids) if m]
    if not pool:
        feed = build_feed(db, user, mode="mood" if mood else "solo", mood=mood, limit=4,
                          opts={"max_runtime": minutes} if minutes else None)
        cards = feed["cards"]
        return {
            "source": "your feed",
            "pick": cards[0] if cards else None,
            "alternates": cards[1:4],
            "reasons": ["Your Watch List is empty — here's a fresh pick from your feed"],
        }

    scored = score_pool(db, ctx, "mood" if mood else "solo", mood, None, pool=pool, respect_history=False)
    ranked = []
    for s in scored:
        bonus, fit_reason = _fit(minutes, s.media)
        reasons = []
        if s.media.id in pinned:
            bonus += 0.3
            reasons.append("Pinned as Must Visit")
        if fit_reason:
            reasons.append(fit_reason)
        if mood and mood in MOODS:
            reasons.append(f"Matches a {MOODS[mood]['label'].lower()} mood")
        if s.availability and s.availability.startswith("On your"):
            reasons.append(s.availability)
        ranked.append((s.final + bonus, s, reasons))
    ranked.sort(key=lambda t: t[0], reverse=True)

    def card(entry):
        _score, s, reasons = entry
        c = media_card(s.media)
        c["reasons"] = reasons
        c["match_percent"] = s.match_percent
        return c

    return {
        "source": source,
        "pick": card(ranked[0]),
        "alternates": [card(e) for e in ranked[1:4]],
        "reasons": ranked[0][2] or [f"Top match from {source}"],
    }
