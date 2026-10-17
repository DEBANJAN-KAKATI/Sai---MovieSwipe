from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..schemas import GuestIn, LoginIn, RegisterIn
from ..security import auth_limiter, create_token, get_optional_user, hash_password, verify_password
from ..services.users import create_user, me_payload

router = APIRouter(prefix="/auth", tags=["auth"])


def _session(user: User) -> dict:
    return {"token": create_token(user.id), "user": me_payload(user)}


@router.post("/guest", dependencies=[Depends(auth_limiter)])
def guest(body: GuestIn, db: Session = Depends(get_db)):
    """Start instantly without an account; upgrade later via /auth/register."""
    user = create_user(db, body.display_name, is_guest=True)
    db.commit()
    return _session(user)


@router.post("/register", dependencies=[Depends(auth_limiter)])
def register(body: RegisterIn, db: Session = Depends(get_db), current: User | None = Depends(get_optional_user)):
    username = body.username.lower()
    email = body.email.strip().lower() if body.email else None
    conditions = [User.username == username] + ([User.email == email] if email else [])
    taken = db.scalar(select(User).where(or_(*conditions)))
    if taken is not None and (current is None or taken.id != current.id):
        raise HTTPException(409, "That username or email is already taken")

    # A guest upgrading keeps all of their swipes, lists and friends.
    if current is not None and current.is_guest:
        user = current
    else:
        user = create_user(db, body.display_name or body.username, username=username, is_guest=False)
    user.username = username
    user.email = email
    user.password_hash = hash_password(body.password)
    user.is_guest = False
    if body.display_name:
        user.display_name = body.display_name
    db.commit()
    return _session(user)


@router.post("/login", dependencies=[Depends(auth_limiter)])
def login(body: LoginIn, db: Session = Depends(get_db)):
    ident = body.login.strip().lower()
    user = db.scalar(select(User).where(or_(User.username == ident, User.email == ident)))
    if user is None or user.is_bot or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong username or password")
    return _session(user)
