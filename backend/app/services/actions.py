"""Applying list actions (swipes, list edits, imports) with an undoable event log."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import LIST_ACTIONS, LOG_ACTIONS, Match, SessionSwipe, SwipeEvent, User, UserMediaAction, utcnow
from .catalog import get_media
from .taste import refresh_taste


def current_action(db: Session, user_id: str, media_id: str) -> UserMediaAction | None:
    return db.scalar(
        select(UserMediaAction).where(UserMediaAction.user_id == user_id, UserMediaAction.media_id == media_id)
    )


def apply_action(
    db: Session,
    user: User,
    media_id: str,
    action: str,
    *,
    rating: int | None = None,
    session_id: str | None = None,
    idempotency_key: str | None = None,
    refresh: bool = True,
) -> SwipeEvent:
    if get_media(db, media_id) is None:
        raise HTTPException(404, "Unknown title")
    if action not in LIST_ACTIONS and action not in LOG_ACTIONS and action != "remove":
        raise HTTPException(422, f"Unsupported action {action}")

    now = utcnow()
    event = SwipeEvent(
        user_id=user.id,
        media_id=media_id,
        action=action,
        idempotency_key=idempotency_key,
        session_id=session_id,
        created_at=now,
    )
    if action in LOG_ACTIONS:
        db.add(event)
        db.flush()
        return event

    row = current_action(db, user.id, media_id)
    if row is not None:
        event.prev_action, event.prev_rating, event.prev_updated_at = row.action, row.rating, row.updated_at
    if action == "remove":
        if row is not None:
            db.delete(row)
    else:
        if row is None:
            row = UserMediaAction(user_id=user.id, media_id=media_id, created_at=now)
            db.add(row)
        row.action = action
        row.rating = rating if action == "watched" else None
        row.session_id = session_id
        row.updated_at = now
    db.add(event)
    db.flush()
    if refresh:
        refresh_taste(db, user)
    return event


def undo_last(db: Session, user: User) -> SwipeEvent | None:
    event = db.scalar(
        select(SwipeEvent)
        .where(
            SwipeEvent.user_id == user.id,
            SwipeEvent.undone.is_(False),
            SwipeEvent.action.in_((*LIST_ACTIONS, "remove")),
        )
        .order_by(SwipeEvent.created_at.desc())
        .limit(1)
    )
    if event is None:
        return None
    row = current_action(db, user.id, event.media_id)
    if event.prev_action is None:
        if row is not None:
            db.delete(row)
    else:
        if row is None:
            row = UserMediaAction(user_id=user.id, media_id=event.media_id)
            db.add(row)
        row.action = event.prev_action
        row.rating = event.prev_rating
        row.updated_at = event.prev_updated_at or utcnow()
    if event.session_id:
        matched = db.scalar(
            select(Match.id).where(Match.session_id == event.session_id, Match.media_id == event.media_id)
        )
        if not matched:
            db.execute(
                delete(SessionSwipe).where(
                    SessionSwipe.session_id == event.session_id,
                    SessionSwipe.user_id == user.id,
                    SessionSwipe.media_id == event.media_id,
                )
            )
    event.undone = True
    db.flush()
    refresh_taste(db, user)
    return event
