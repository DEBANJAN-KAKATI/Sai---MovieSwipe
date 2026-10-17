"""Personal lists: Itinerary (Must Visit + Watch List), Maybe Later, History."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, UserMediaAction
from ..recs.rank import build_ctx, explain, personal_score
from ..schemas import ListPatchIn
from ..security import get_current_user
from ..services.actions import apply_action
from ..services.catalog import get_media, media_card

router = APIRouter(prefix="/lists", tags=["lists"])


def _rows(db: Session, user_id: str, actions: tuple[str, ...]):
    return db.scalars(
        select(UserMediaAction)
        .where(UserMediaAction.user_id == user_id, UserMediaAction.action.in_(actions))
        .order_by(UserMediaAction.updated_at.desc())
    ).all()


def _item(db: Session, row: UserMediaAction, ctx=None) -> dict | None:
    m = get_media(db, row.media_id)
    if m is None:
        return None
    card = media_card(m)
    card.update(
        {
            "action": row.action,
            "rating": row.rating,
            "added_at": row.updated_at.isoformat() + "Z",
            "from_session": bool(row.session_id),
        }
    )
    if ctx is not None and ctx.alpha > 0:
        raw, sim = personal_score(m, ctx)
        card["match_score"] = round(raw, 4)
        because, _bid, reasons = explain(m, ctx, lambda mid: get_media(db, mid))
        card["reasons"] = reasons
    return card


SORTS = {
    "added": lambda c: c["added_at"],
    "runtime": lambda c: c.get("runtime_minutes") or 10_000,
    "title": lambda c: c["title"].lower(),
    "match": lambda c: -(c.get("match_score") or 0),
    "year": lambda c: -(c.get("year") or 0),
}


def _sorted(cards: list[dict], sort: str) -> list[dict]:
    if sort == "added":
        return sorted(cards, key=SORTS["added"], reverse=True)
    return sorted(cards, key=SORTS.get(sort, SORTS["added"]))


@router.get("/watchlist")
def watchlist(sort: str = Query("added"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ctx = build_ctx(db, user, with_social=False)
    must = [c for c in (_item(db, r, ctx) for r in _rows(db, user.id, ("must_visit",))) if c]
    wl = [c for c in (_item(db, r, ctx) for r in _rows(db, user.id, ("watchlist",))) if c]
    total_minutes = sum((c.get("runtime_minutes") or 0) for c in must + wl if c["type"] == "movie")
    return {"must_visit": _sorted(must, sort), "watchlist": _sorted(wl, sort), "sort": sort,
            "movie_minutes_total": total_minutes}


@router.get("/undecided")
def undecided(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": [c for c in (_item(db, r) for r in _rows(db, user.id, ("undecided",))) if c]}


@router.get("/history")
def history(kind: str = Query("rejected", pattern="^(rejected|watched|liked)$"),
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"kind": kind, "items": [c for c in (_item(db, r) for r in _rows(db, user.id, (kind,))) if c]}


@router.get("/counts")
def counts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(UserMediaAction.action, func.count()).where(UserMediaAction.user_id == user.id).group_by(
            UserMediaAction.action
        )
    ).all()
    return {action: n for action, n in rows}


@router.patch("/items/{media_id}")
def patch_item(media_id: str, body: ListPatchIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Promote / demote / remove, or mark watched with a 1–5 star rating (feeds back into the ranker)."""
    if get_media(db, media_id) is None:
        raise HTTPException(404, "Unknown title")
    apply_action(db, user, media_id, body.action, rating=body.rating)
    db.commit()
    return {"ok": True, "action": body.action, "rating": body.rating}
