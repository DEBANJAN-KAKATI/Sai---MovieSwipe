"""Profile, preferences, Taste DNA, import/export and account deletion."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    CollabList,
    Friendship,
    PartyRSVP,
    Recommendation,
    SessionSwipe,
    SwipeEvent,
    User,
    UserMediaAction,
    WatchParty,
)
from ..schemas import ProfilePatchIn
from ..security import get_current_user
from ..services.catalog import CERT_ORDER, get_media
from ..services.importers import import_csv
from ..services.stats import taste_summary
from ..services.users import me_payload

router = APIRouter(tags=["profile"])

MAX_IMPORT_BYTES = 5 * 1024 * 1024


@router.get("/users/me")
def me(user: User = Depends(get_current_user)):
    return me_payload(user)


@router.patch("/users/me")
def patch_me(body: ProfilePatchIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.display_name is not None:
        user.display_name = body.display_name.strip() or user.display_name
    if body.avatar is not None:
        user.avatar = body.avatar
    if body.region is not None:
        user.region = body.region.upper()
    if body.subscription_providers is not None:
        user.subscription_providers = body.subscription_providers[:20]
    if body.content_filters is not None:
        cf = {**(user.content_filters or {}), **body.content_filters}
        if cf.get("max_certification") not in (None, *CERT_ORDER):
            raise HTTPException(422, "max_certification must be U, UA or A")
        user.content_filters = cf
    if body.preferences is not None:
        user.preferences = {**(user.preferences or {}), **body.preferences}
    if body.privacy_settings is not None:
        user.privacy_settings = {**(user.privacy_settings or {}), **body.privacy_settings}
    db.commit()
    return me_payload(user)


@router.get("/users/me/taste-summary")
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return taste_summary(db, user)


@router.post("/import/letterboxd")
async def import_letterboxd(
    file: UploadFile = File(...),
    list_kind: str = Form("auto"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accepts Letterboxd (ratings/watched/watchlist/diary) or IMDb CSV exports."""
    if list_kind not in ("auto", "watched", "watchlist"):
        raise HTTPException(422, "list_kind must be auto, watched or watchlist")
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "File too large (5 MB max)")
    try:
        return import_csv(db, user, content, list_kind)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/users/me/export")
def export(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """GDPR-style export of everything we hold about you."""
    def title(mid):
        m = get_media(db, mid)
        return m.title if m else mid

    actions = db.scalars(select(UserMediaAction).where(UserMediaAction.user_id == user.id)).all()
    events = db.scalars(select(SwipeEvent).where(SwipeEvent.user_id == user.id)).all()
    data = {
        "profile": me_payload(user),
        "lists": [
            {"title": title(a.media_id), "action": a.action, "rating": a.rating,
             "updated_at": a.updated_at.isoformat() + "Z"}
            for a in actions
        ],
        "swipe_history": [
            {"title": title(e.media_id), "action": e.action, "undone": e.undone, "at": e.created_at.isoformat() + "Z"}
            for e in events
        ],
        "taste_profile": {k: v for k, v in (user.taste or {}).items() if not k.endswith("centroid")},
    }
    return Response(
        content=json.dumps(data, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="sai-export.json"'},
    )


@router.delete("/users/me")
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.id
    for model, col in (
        (UserMediaAction, UserMediaAction.user_id),
        (SwipeEvent, SwipeEvent.user_id),
        (SessionSwipe, SessionSwipe.user_id),
        (PartyRSVP, PartyRSVP.user_id),
        (WatchParty, WatchParty.host_id),
        (CollabList, CollabList.owner_id),
    ):
        db.execute(delete(model).where(col == uid))
    db.execute(delete(Friendship).where(or_(Friendship.requester_id == uid, Friendship.addressee_id == uid)))
    db.execute(delete(Recommendation).where(or_(Recommendation.from_user_id == uid, Recommendation.to_user_id == uid)))
    db.delete(user)
    db.commit()
    return {"ok": True}
