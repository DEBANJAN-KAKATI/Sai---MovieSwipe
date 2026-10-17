import os
import tempfile
import uuid
from pathlib import Path

import pytest

_DB = Path(tempfile.gettempdir()) / f"movieswipe-test-{uuid.uuid4().hex[:8]}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.as_posix()}"
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 40
os.environ["TMDB_API_KEY"] = ""
os.environ["ADMIN_TOKEN"] = "admin-test"

from fastapi.testclient import TestClient  # noqa: E402

from app import security  # noqa: E402
from app.main import app  # noqa: E402

# Tests create many accounts quickly from one client; keep limiters out of the way.
for _limiter in (security.auth_limiter, security.swipe_limiter, security.join_limiter):
    _limiter.limit = 100_000


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    from app.db import engine

    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        Path(str(_DB) + suffix).unlink(missing_ok=True)


def _guest(client, name="Tester"):
    r = client.post("/api/auth/guest", json={"display_name": name})
    assert r.status_code == 200, r.text
    data = r.json()
    return {"Authorization": f"Bearer {data['token']}"}, data["user"]


@pytest.fixture
def guest(client):
    return lambda name="Tester": _guest(client, name)


@pytest.fixture
def titles(client):
    """title -> media_id for the bundled catalog."""
    from app.db import SessionLocal
    from app.services.catalog import all_media

    with SessionLocal() as db:
        return {m.title: m.id for m in all_media(db)}
