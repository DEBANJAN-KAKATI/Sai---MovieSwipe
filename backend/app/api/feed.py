"""Discover deck: feed, swipes, undo, onboarding and Tonight's Pick."""

from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import POSITIVE_ACTIONS, FeedImpression, SwipeEvent, User
from ..recs.rank import build_feed
from ..schemas import OnboardingIn, SwipeIn
from ..security import get_current_user, swipe_limiter
from ..services.actions import apply_action, undo_last
from ..services.catalog import CERT_ORDER, all_media, get_media, media_card
from ..services.picks import tonight
from ..services.realtime import hub
from ..services.sessions import get_session_for, match_payload, notify_progress, record_session_swipe
from ..services.taste import refresh_taste

router = APIRouter(tags=["discover"])


@router.get("/feed")
def feed(
    limit: int = Query(10, ge=1, le=30),
    mode: str = "solo",
    mood: str | None = None,
    type: str = "all",
    language: str | None = None,
    max_runtime: int | None = Query(None, ge=10, le=400),
    exclude: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    excl = {x for x in exclude.split(",") if x}
    opts = {"type": type, "language": language, "max_runtime": max_runtime}
    result = build_feed(db, user, mode=mode, mood=mood, limit=limit, exclude=excl, opts=opts)
    for rank, card in enumerate(result["cards"]):
        db.add(FeedImpression(user_id=user.id, media_id=card["media_id"], rank=rank, mode=result["mode"]))
    db.commit()
    return result


@router.post("/swipe", dependencies=[Depends(swipe_limiter)])
def swipe(body: SwipeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.idempotency_key:
        prior = db.scalar(select(SwipeEvent).where(SwipeEvent.idempotency_key == body.idempotency_key))
        if prior is not None:
            if prior.user_id != user.id:
                raise HTTPException(409, "Idempotency key already used")
            return {"ok": True, "duplicate": True, "action": prior.action, "match": None}

    sess = get_session_for(db, body.session_id, user) if body.session_id else None
    match = None
    if sess is not None and body.action == "watched":
        # Already seen it: moves the stack on for this member without voting for a match, and still teaches taste.
        record_session_swipe(db, sess, user, body.media_id, "seen")
        apply_action(db, user, body.media_id, "watched", session_id=sess.id, idempotency_key=body.idempotency_key)
    elif sess is not None and body.action in ("watchlist", "must_visit", "rejected", "undecided", "liked"):
        match = record_session_swipe(db, sess, user, body.media_id, body.action)
        # Group rejects are contextual ("not tonight"), so only positives touch personal lists.
        if body.action in POSITIVE_ACTIONS:
            apply_action(db, user, body.media_id, body.action, session_id=sess.id,
                         idempotency_key=body.idempotency_key)
        else:
            apply_action(db, user, body.media_id, "impression_detail", session_id=sess.id,
                         idempotency_key=body.idempotency_key)
    else:
        apply_action(db, user, body.media_id, body.action, idempotency_key=body.idempotency_key)
    db.commit()

    match_out = None
    if sess is not None:
        if match is not None:
            match_out = match_payload(db, match)
            hub.publish(sess.id, "session.match", match_out)
        notify_progress(db, sess)
    return {"ok": True, "duplicate": False, "action": body.action, "match": match_out}


@router.post("/swipe/undo")
def undo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = undo_last(db, user)
    if event is None:
        raise HTTPException(404, "Nothing to undo")
    db.commit()
    m = get_media(db, event.media_id)
    return {"undone_action": event.action, "restored_action": event.prev_action, "card": media_card(m) if m else None,
            "session_id": event.session_id}


@router.get("/onboarding/tiles")
def onboarding_tiles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """A diverse grid of recognisable titles across genres and languages."""
    items = sorted(all_media(db), key=lambda m: -m.popularity)
    rng = random.Random(user.id)
    chosen, genres_seen, langs = [], {}, {}
    for m in items:
        primary = m.genres[0] if m.genres else "Other"
        if genres_seen.get(primary, 0) >= 3 or langs.get(m.language, 0) >= 9:
            continue
        chosen.append(m)
        genres_seen[primary] = genres_seen.get(primary, 0) + 1
        langs[m.language] = langs.get(m.language, 0) + 1
        if len(chosen) >= 24:
            break
    rng.shuffle(chosen)
    return {"tiles": [media_card(m) for m in chosen]}


@router.post("/onboarding/taste")
def onboarding_taste(body: OnboardingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for mid in dict.fromkeys(body.liked_ids):
        if get_media(db, mid) is not None:
            apply_action(db, user, mid, "liked", refresh=False)
    if body.display_name:
        user.display_name = body.display_name.strip() or user.display_name
    if body.subscriptions is not None:
        user.subscription_providers = body.subscriptions
    if body.languages is not None:
        user.preferences = {**(user.preferences or {}), "languages": body.languages}
    if body.content_filters is not None:
        cf = dict(body.content_filters)
        if cf.get("max_certification") not in (None, *CERT_ORDER):
            raise HTTPException(422, "max_certification must be U, UA or A")
        user.content_filters = {**(user.content_filters or {}), **cf}
    refresh_taste(db, user)
    user.onboarded = True
    db.commit()
    return {"ok": True, "liked": len(body.liked_ids)}


@router.get("/picks/tonight")
def picks_tonight(
    minutes: int | None = Query(None, ge=15, le=600),
    mood: str | None = None,
    session_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if session_id:
        get_session_for(db, session_id, user)
    return tonight(db, user, minutes=minutes, mood=mood, session_id=session_id)
