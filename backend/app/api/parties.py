"""Watch parties: schedule a title, RSVP, export to calendar (.ics)."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PartyRSVP, User, WatchParty, utcnow
from ..schemas import PartyIn, RSVPIn
from ..security import get_current_user, random_code
from ..services.catalog import get_media, media_card
from ..services.ics import party_ics
from ..services.users import public_user
from ..services.watch_links import google_watch_url

router = APIRouter(prefix="/parties", tags=["watch parties"])


def _to_utc_naive(d: dt.datetime) -> dt.datetime:
    if d.tzinfo is not None:
        d = d.astimezone(dt.UTC).replace(tzinfo=None)
    return d


def _payload(db: Session, p: WatchParty, viewer: User | None) -> dict:
    m = get_media(db, p.media_id)
    rsvps = db.execute(
        select(User, PartyRSVP.status).join(PartyRSVP, PartyRSVP.user_id == User.id).where(PartyRSVP.party_id == p.id)
    ).all()
    host = db.get(User, p.host_id)
    return {
        "party_id": p.id,
        "code": p.invite_code,
        "media": media_card(m) if m else None,
        "starts_at": p.starts_at.isoformat() + "Z",
        "duration_minutes": p.duration_minutes,
        "notes": p.notes,
        "host": public_user(host) if host else None,
        "is_host": viewer is not None and viewer.id == p.host_id,
        "rsvps": [{**public_user(u), "status": s} for u, s in rsvps],
        "your_rsvp": next((s for u, s in rsvps if viewer and u.id == viewer.id), None),
        "watch_url": google_watch_url(m.title) if m else None,
        "calendar_path": f"/api/parties/{p.invite_code}/calendar.ics",
        "upcoming": p.starts_at >= utcnow() - dt.timedelta(hours=3),
    }


@router.post("")
def create(body: PartyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = get_media(db, body.media_id)
    if m is None:
        raise HTTPException(404, "Unknown title")
    starts = _to_utc_naive(body.starts_at)
    duration = (m.runtime_minutes or 120) if m.type == "movie" else max(60, (m.runtime_minutes or 45) * 2)
    p = WatchParty(host_id=user.id, media_id=m.id, starts_at=starts, duration_minutes=duration,
                   notes=body.notes.strip(), invite_code=f"P-{random_code(7)}", session_id=body.session_id)
    db.add(p)
    db.flush()
    db.add(PartyRSVP(party_id=p.id, user_id=user.id, status="going"))
    db.commit()
    return _payload(db, p, user)


@router.get("")
def mine(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    parties = db.scalars(
        select(WatchParty)
        .outerjoin(PartyRSVP, PartyRSVP.party_id == WatchParty.id)
        .where(or_(WatchParty.host_id == user.id, PartyRSVP.user_id == user.id))
        .order_by(WatchParty.starts_at)
        .distinct()
    ).all()
    return {"parties": [_payload(db, p, user) for p in parties]}


def _by_code(db: Session, code: str) -> WatchParty:
    p = db.scalar(select(WatchParty).where(WatchParty.invite_code == code.upper()))
    if p is None:
        raise HTTPException(404, "Watch party not found")
    return p


@router.get("/{code}")
def get_party(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _payload(db, _by_code(db, code), user)


@router.post("/{code}/rsvp")
def rsvp(code: str, body: RSVPIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _by_code(db, code)
    row = db.scalar(select(PartyRSVP).where(PartyRSVP.party_id == p.id, PartyRSVP.user_id == user.id))
    if row is None:
        db.add(PartyRSVP(party_id=p.id, user_id=user.id, status=body.status))
    else:
        row.status = body.status
        row.updated_at = utcnow()
    db.commit()
    return _payload(db, p, user)


@router.delete("/{code}")
def cancel(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _by_code(db, code)
    if p.host_id != user.id:
        raise HTTPException(403, "Only the host can cancel")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.get("/{code}/calendar.ics")
def calendar(code: str, request: Request, db: Session = Depends(get_db)):
    """Public by invite code so calendar apps can fetch it without a token."""
    p = _by_code(db, code)
    m = get_media(db, p.media_id)
    title = f"Watch party: {m.title}" if m else "Watch party"
    desc_lines = [p.notes] if p.notes else []
    if m:
        desc_lines += [m.overview, "", f"Where to watch in India: {google_watch_url(m.title)}"]
    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    body = party_ics(
        uid=p.id,
        title=title,
        starts_at=p.starts_at,
        duration_minutes=p.duration_minutes,
        description="\n".join(desc_lines),
        url=f"{origin}/party/{p.invite_code}",
    )
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="sai-{p.invite_code}.ics"'},
    )
