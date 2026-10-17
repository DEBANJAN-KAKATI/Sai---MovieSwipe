"""Duo / group sessions: blended stacks, match detection, demo bots."""

from __future__ import annotations

import math
import random

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import POSITIVE_ACTIONS, Match, SessionMember, SessionSwipe, SwipeSession, User, utcnow
from ..recs.rank import Scored, _stable_noise, build_ctx, card_from_scored, personal_score, score_pool
from .catalog import get_media, media_card
from .realtime import hub
from .users import public_user

STACK_CHUNK = 40


def iso(d) -> str | None:
    return d.isoformat() + "Z" if d else None


def members_of(db: Session, sess: SwipeSession) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(SessionMember, SessionMember.user_id == User.id)
            .where(SessionMember.session_id == sess.id)
            .order_by(SessionMember.joined_at)
        ).all()
    )


def required_votes(sess: SwipeSession, n_members: int) -> int:
    if sess.mode == "duo":
        return 2
    if sess.min_votes:
        return min(sess.min_votes, max(2, n_members))
    return max(2, n_members)  # unanimous


def ensure_open(sess: SwipeSession) -> None:
    if sess.status == "open" and sess.expires_at < utcnow():
        sess.status = "expired"
    if sess.status != "open":
        raise HTTPException(410, "This session has ended")


def get_session_for(db: Session, session_id: str, user: User) -> SwipeSession:
    sess = db.get(SwipeSession, session_id)
    if sess is None:
        raise HTTPException(404, "Session not found")
    is_member = db.scalar(
        select(SessionMember.id).where(SessionMember.session_id == sess.id, SessionMember.user_id == user.id)
    )
    if not is_member:
        raise HTTPException(403, "Join the session first")
    return sess


def _harmonic(values: list[float]) -> float:
    vals = [max(0.02, v) for v in values]
    return len(vals) / sum(1.0 / v for v in vals)


def extend_stack(db: Session, sess: SwipeSession, n: int = STACK_CHUNK) -> None:
    members = members_of(db, sess)
    if not members:
        return
    filters = sess.filters or {}
    mood = filters.get("mood")
    mode = "mood" if mood else "solo"
    opts = {"type": filters.get("type"), "max_runtime": filters.get("max_runtime")}
    in_stack = {e["id"] for e in sess.stack or []}

    per_member: list[tuple[User, dict]] = []
    blocked: set[str] = set()
    on_lists: dict[str, list[str]] = {}
    for u in members:
        ctx = build_ctx(db, u, with_social=False)
        scored = score_pool(db, ctx, mode, mood, opts, exclude=in_stack, respect_history=False)
        per_member.append((u, {s.media.id: s.final for s in scored}))
        for mid, (action, _ts) in ctx.acted.items():
            # Already seen (watched / loved at onboarding) or rejected by a real member: leave it out.
            if action in ("rejected", "watched", "liked") and not u.is_bot:
                blocked.add(mid)
            elif action in ("watchlist", "must_visit"):
                on_lists.setdefault(mid, []).append(u.display_name)

    common = set.intersection(*(set(scores) for _u, scores in per_member)) - blocked
    top_by_member = {u.id: max(scores.values(), default=1.0) for u, scores in per_member}
    combined: list[tuple[float, str, int]] = []
    for mid in common:
        fits = []
        for u, scores in per_member:
            fit = scores[mid] / (top_by_member[u.id] or 1.0)
            if u.display_name in on_lists.get(mid, []):
                fit = max(fit, 0.97)
            fits.append(min(1.0, fit))
        h = _harmonic(fits)
        combined.append((h, mid, int(round(40 + 59 * h))))
    combined.sort(reverse=True)
    chosen = combined[:n]
    # Light, reproducible shuffle inside small windows so stacks feel less mechanical.
    rng = random.Random(f"{sess.feed_seed}-{len(in_stack)}")
    entries = []
    for i in range(0, len(chosen), 5):
        window = chosen[i : i + 5]
        rng.shuffle(window)
        entries.extend({"id": mid, "fit": fit, "on_lists": on_lists.get(mid, [])} for _h, mid, fit in window)
    sess.stack = (sess.stack or []) + entries


def session_feed(db: Session, sess: SwipeSession, user: User, limit: int = 10) -> list[dict]:
    swiped = set(
        db.scalars(
            select(SessionSwipe.media_id).where(SessionSwipe.session_id == sess.id, SessionSwipe.user_id == user.id)
        ).all()
    )
    remaining = [e for e in (sess.stack or []) if e["id"] not in swiped]
    if len(remaining) < limit:
        extend_stack(db, sess)
        db.commit()
        remaining = [e for e in (sess.stack or []) if e["id"] not in swiped]
    ctx = build_ctx(db, user, with_social=False)
    names = {u.id: u.display_name for u in members_of(db, sess)}
    cards = []
    for entry in remaining[:limit]:
        m = get_media(db, entry["id"])
        if m is None:
            continue
        s = Scored(media=m)
        card = card_from_scored(s, ctx, db)
        others = [n for n in entry.get("on_lists", []) if n != names.get(user.id)]
        card.update(
            {
                "match_percent": entry["fit"],
                "group_fit": entry["fit"],
                "because": f"On {', '.join(others)}'s list" if others else (card.get("because") or "Good fit for the group"),
            }
        )
        cards.append(card)
    return cards


def _bot_vote(db: Session, bot: User, sess: SwipeSession, media_id: str) -> str:
    m = get_media(db, media_id)
    if m is None:
        return "rejected"
    ctx = build_ctx(db, bot, with_social=False)
    prior = ctx.acted.get(media_id)
    if prior and prior[0] in ("watchlist", "must_visit", "liked"):
        return "watchlist"
    raw, _ = personal_score(m, ctx)
    p_like = 1 / (1 + math.exp(-(raw - 0.3) * 7))
    p_like = min(0.9, max(0.12, p_like))
    return "watchlist" if _stable_noise(bot.id, sess.id, media_id) < p_like else "rejected"


def _check_match(db: Session, sess: SwipeSession, media_id: str) -> Match | None:
    if db.scalar(select(Match.id).where(Match.session_id == sess.id, Match.media_id == media_id)):
        return None
    members = members_of(db, sess)
    if len(members) < 2:
        return None
    votes = db.execute(
        select(SessionSwipe.user_id, SessionSwipe.action).where(
            SessionSwipe.session_id == sess.id,
            SessionSwipe.media_id == media_id,
            SessionSwipe.action.in_(POSITIVE_ACTIONS),
        )
    ).all()
    if len(votes) < required_votes(sess, len(members)):
        return None
    names = {u.id: u.display_name for u in members}
    match = Match(
        session_id=sess.id,
        media_id=media_id,
        participants=[names.get(uid, "?") for uid, _ in votes],
        super_match=all(a == "must_visit" for _, a in votes),
    )
    db.add(match)
    db.flush()
    return match


def record_session_swipe(db: Session, sess: SwipeSession, user: User, media_id: str, action: str) -> Match | None:
    ensure_open(sess)
    existing = db.scalar(
        select(SessionSwipe).where(
            SessionSwipe.session_id == sess.id, SessionSwipe.user_id == user.id, SessionSwipe.media_id == media_id
        )
    )
    if existing:
        existing.action = action
    else:
        db.add(SessionSwipe(session_id=sess.id, user_id=user.id, media_id=media_id, action=action))
    db.flush()

    match = _check_match(db, sess, media_id) if action in POSITIVE_ACTIONS else None
    for bot in (u for u in members_of(db, sess) if u.is_bot):
        already = db.scalar(
            select(SessionSwipe.id).where(
                SessionSwipe.session_id == sess.id, SessionSwipe.user_id == bot.id, SessionSwipe.media_id == media_id
            )
        )
        if already:
            continue
        db.add(SessionSwipe(session_id=sess.id, user_id=bot.id, media_id=media_id, action=_bot_vote(db, bot, sess, media_id)))
        db.flush()
        match = match or _check_match(db, sess, media_id)
    return match


def match_payload(db: Session, match: Match) -> dict:
    m = get_media(db, match.media_id)
    return {
        "match_id": match.id,
        "media": media_card(m) if m else None,
        "participants": match.participants,
        "super_match": match.super_match,
        "matched_at": iso(match.matched_at),
    }


def session_state(db: Session, sess: SwipeSession, viewer: User) -> dict:
    if sess.status == "open" and sess.expires_at < utcnow():
        sess.status = "expired"
        db.commit()
    members = members_of(db, sess)
    counts = dict(
        db.execute(
            select(SessionSwipe.user_id, func.count())
            .where(SessionSwipe.session_id == sess.id)
            .group_by(SessionSwipe.user_id)
        ).all()
    )
    matches = db.scalars(select(Match).where(Match.session_id == sess.id).order_by(Match.matched_at.desc())).all()
    return {
        "session_id": sess.id,
        "code": sess.code,
        "mode": sess.mode,
        "min_votes": sess.min_votes,
        "required_votes": required_votes(sess, len(members)),
        "status": sess.status,
        "filters": sess.filters or {},
        "host_id": sess.host_id,
        "is_host": sess.host_id == viewer.id,
        "expires_at": iso(sess.expires_at),
        "created_at": iso(sess.created_at),
        "members": [
            {**public_user(u), "swiped": counts.get(u.id, 0), "is_you": u.id == viewer.id} for u in members
        ],
        "matches": [match_payload(db, mt) for mt in matches],
        "join_path": f"/join/{sess.code}",
    }


def notify_progress(db: Session, sess: SwipeSession) -> None:
    counts = dict(
        db.execute(
            select(SessionSwipe.user_id, func.count())
            .where(SessionSwipe.session_id == sess.id)
            .group_by(SessionSwipe.user_id)
        ).all()
    )
    hub.publish(sess.id, "session.progress", {"swiped": counts})
