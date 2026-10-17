"""Recompute every title's embedding (run after large catalog changes or switching EMBEDDING_BACKEND)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.migrate import upgrade_db  # noqa: E402
from app.services.catalog import rebuild_embeddings, seed_catalog  # noqa: E402

if __name__ == "__main__":
    upgrade_db()
    with SessionLocal() as db:
        seed_catalog(db)
        n = rebuild_embeddings(db)
    print(f"Rebuilt {n} embeddings with backend '{settings.embedding_backend}'.")
