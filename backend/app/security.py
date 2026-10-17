"""Password hashing (scrypt, stdlib), JWT auth and a small in-memory rate limiter."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
import threading
import time

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User, utcnow

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
TOKEN_TTL = dt.timedelta(days=30)
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, salt_hex, digest_hex = stored.split("$", 2)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(digest.hex(), digest_hex)


def random_code(length: int) -> str:
    """Short human-friendly code; 31 symbols -> ~4.95 bits each (7 chars ≈ 34.7 bits)."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def create_token(user_id: str) -> str:
    now = dt.datetime.now(dt.UTC)
    payload = {"sub": user_id, "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


def _bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = _bearer(request)
    if not token:
        return None
    user_id = decode_token(token)
    if not user_id:
        return None
    return db.get(User, user_id)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_optional_user(request, db)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    now = utcnow()
    if (now - user.last_active_at) > dt.timedelta(minutes=5):
        user.last_active_at = now
        db.commit()
    return user


class RateLimiter:
    """Sliding-window limiter keyed by client IP + user. Good enough for a single process."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self.hits: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    def __call__(self, request: Request) -> None:
        key = f"{request.client.host if request.client else 'anon'}|{_bearer(request) or ''}|{request.url.path}"
        now = time.monotonic()
        with self.lock:
            hits = [t for t in self.hits.get(key, []) if now - t < self.window]
            if len(hits) >= self.limit:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down a little")
            hits.append(now)
            self.hits[key] = hits


swipe_limiter = RateLimiter(limit=120, window_seconds=60)
auth_limiter = RateLimiter(limit=20, window_seconds=60)
join_limiter = RateLimiter(limit=20, window_seconds=60)
