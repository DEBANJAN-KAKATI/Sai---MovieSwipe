"""Duo / group swipe sessions + WebSocket channel."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, get_db
from ..models import Match, SessionMember, SessionSwipe, SwipeSession, User, utcnow
from ..recs.moods import MOODS
from ..schemas import JoinIn, SessionCreateIn
from ..security import decode_token, get_current_user, join_limiter, random_code
from ..services.realtime import hub
from ..services.sessions import (
    ensure_open,
    get_session_for,
    match_payload,
    members_of,
    session_feed,
    session_state,
)
from ..services.users import PERSONAS, ensure_persona, public_user

router = APIRouter(prefix="/sessions", tags=["sessions"])
ws_router = APIRouter()

DUO_MAX = 2
GROUP_MAX = 12


def _new_code(db: Session) -> str:
    while True:
        code = random_code(7)
        if not db.scalar(select(SwipeSession.id).where(SwipeSession.code == code)):
            return code


def _add_member(db: Session, sess: SwipeSession, user: User) -> bool:
    exists = db.scalar(
        select(SessionMember.id).where(SessionMember.session_id == sess.id, SessionMember.user_id == user.id)
    )
    if exists:
        return False
    count = db.scalar(select(func.count()).select_from(SessionMember).where(SessionMember.session_id == sess.id)) or 0
    if count >= (DUO_MAX if sess.mode == "duo" else GROUP_MAX):
        raise HTTPException(409, "This session is full")
    db.add(SessionMember(session_id=sess.id, user_id=user.id))
    db.flush()
    # Re-blend the stack for the new member if nobody has started swiping yet.
    started = db.scalar(select(func.count()).select_from(SessionSwipe).where(SessionSwipe.session_id == sess.id))
    if not started:
        sess.stack = []
    return True


@router.post("")
def create(body: SessionCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.mood and body.mood not in MOODS:
        raise HTTPException(422, "Unknown mood")
    sess = SwipeSession(
        code=_new_code(db),
        host_id=user.id,
        mode=body.mode,
        min_votes=body.min_votes if body.mode == "group" else None,
        filters={"mood": body.mood, "type": body.type, "max_runtime": body.max_runtime},
        stack=[],
        expires_at=utcnow() + dt.timedelta(minutes=settings.session_ttl_minutes),
    )
    db.add(sess)
    db.flush()
    _add_member(db, sess, user)
    db.commit()
    return session_state(db, sess, user)


@router.post("/join", dependencies=[Depends(join_limiter)])
def join(body: JoinIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sess = db.scalar(select(SwipeSession).where(SwipeSession.code == body.code.strip().upper()))
    if sess is None:
        raise HTTPException(404, "No session with that code")
    ensure_open(sess)
    if _add_member(db, sess, user):
        hub.publish(sess.id, "session.user_joined", public_user(user))
    db.commit()
    return session_state(db, sess, user)


@router.get("")
def mine(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.scalars(
        select(SwipeSession)
        .join(SessionMember, SessionMember.session_id == SwipeSession.id)
        .where(SessionMember.user_id == user.id)
        .order_by(SwipeSession.created_at.desc())
        .limit(30)
    ).all()
    out = []
    for s in sessions:
        members = members_of(db, s)
        n_matches = db.scalar(select(func.count()).select_from(Match).where(Match.session_id == s.id)) or 0
        latest = db.scalar(select(Match).where(Match.session_id == s.id).order_by(Match.matched_at.desc()).limit(1))
        status = "expired" if s.status == "open" and s.expires_at < utcnow() else s.status
        out.append(
            {
                "session_id": s.id,
                "code": s.code,
                "mode": s.mode,
                "status": status,
                "created_at": s.created_at.isoformat() + "Z",
                "members": [public_user(u) for u in members],
                "match_count": n_matches,
                "latest_match": match_payload(db, latest) if latest else None,
            }
        )
    return {"sessions": out}


@router.get("/{session_id}")
def state(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return session_state(db, get_session_for(db, session_id, user), user)


@router.get("/{session_id}/feed")
def feed(session_id: str, limit: int = Query(10, ge=1, le=30), user: User = Depends(get_current_user),
         db: Session = Depends(get_db)):
    sess = get_session_for(db, session_id, user)
    ensure_open(sess)
    cards = session_feed(db, sess, user, limit)
    db.commit()
    return {"cards": cards, "session_id": sess.id}


@router.get("/{session_id}/matches")
def matches(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sess = get_session_for(db, session_id, user)
    rows = db.scalars(select(Match).where(Match.session_id == sess.id).order_by(Match.matched_at.desc())).all()
    return {"matches": [match_payload(db, m) for m in rows]}


@router.post("/{session_id}/bot")
def add_bot(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Demo helper: add a persona bot that swipes along, so duo/group can be tried solo."""
    sess = get_session_for(db, session_id, user)
    ensure_open(sess)
    present = {u.username for u in members_of(db, sess)}
    spec = next((p for p in PERSONAS if p["username"] not in present), None)
    if spec is None:
        raise HTTPException(409, "All demo bots are already here")
    bot = ensure_persona(db, spec)
    if _add_member(db, sess, bot):
        hub.publish(sess.id, "session.user_joined", public_user(bot))
    db.commit()
    return session_state(db, sess, user)


@router.post("/{session_id}/close")
def close(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sess = get_session_for(db, session_id, user)
    if sess.host_id != user.id:
        raise HTTPException(403, "Only the host can end the session")
    sess.status = "closed"
    db.commit()
    hub.publish(sess.id, "session.closed", {})
    return session_state(db, sess, user)


@ws_router.websocket("/ws/sessions/{session_id}")
async def session_socket(ws: WebSocket, session_id: str, token: str = ""):
    user_id = decode_token(token)
    db = SessionLocal()
    try:
        allowed = user_id and db.scalar(
            select(SessionMember.id).where(SessionMember.session_id == session_id, SessionMember.user_id == user_id)
        )
    finally:
        db.close()
    if not allowed:
        await ws.close(code=4403)
        return
    await hub.connect(session_id, ws)
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text('{"event":"pong","data":{}}')
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(session_id, ws)
