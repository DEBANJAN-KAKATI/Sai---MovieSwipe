"""Runtime settings, read from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


def _load_dotenv() -> None:
    """Minimal .env loader: KEY=VALUE lines; real environment variables win."""
    for candidate in (BACKEND_DIR / ".env", PROJECT_DIR / ".env"):
        if not candidate.exists():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET", "").strip()
    if secret:
        return secret
    # Persist a generated secret so tokens survive restarts in local dev.
    path = BACKEND_DIR / ".jwt_secret"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    secret = secrets.token_urlsafe(48)
    try:
        path.write_text(secret, encoding="utf-8")
    except OSError:
        pass
    return secret


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str
    tmdb_api_key: str
    jwt_secret: str
    region_default: str
    embedding_backend: str
    embedding_model: str
    taste_half_life_days: float
    undecided_cooldown_hours: float
    rejected_cooldown_days: float
    session_ttl_minutes: float
    admin_token: str
    cors_origins: list[str]

    @property
    def tmdb_enabled(self) -> bool:
        return bool(self.tmdb_api_key)


def load_settings() -> Settings:
    default_db = f"sqlite:///{(BACKEND_DIR / 'movieswipe.db').as_posix()}"
    return Settings(
        database_url=os.environ.get("DATABASE_URL", "").strip() or default_db,
        tmdb_api_key=os.environ.get("TMDB_API_KEY", "").strip(),
        jwt_secret=_jwt_secret(),
        region_default=os.environ.get("APP_REGION_DEFAULT", "IN"),
        embedding_backend=os.environ.get("EMBEDDING_BACKEND", "hash"),
        embedding_model=os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        taste_half_life_days=_float("TASTE_HALF_LIFE_DAYS", 14),
        undecided_cooldown_hours=_float("UNDECIDED_COOLDOWN_HOURS", 72),
        rejected_cooldown_days=_float("REJECTED_COOLDOWN_DAYS", 60),
        session_ttl_minutes=_float("SESSION_TTL_MINUTES", 120),
        admin_token=os.environ.get("ADMIN_TOKEN", "").strip(),
        cors_origins=[
            o.strip()
            for o in os.environ.get(
                "CORS_ORIGINS",
                # Vite dev server + the Android app's WebView origins
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost,https://localhost,capacitor://localhost",
            ).split(",")
            if o.strip()
        ],
    )


settings = load_settings()
