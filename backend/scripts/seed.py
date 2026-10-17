"""Migrate the schema and load the bundled catalog (also happens automatically on API startup).

    python scripts/seed.py            # only if the catalog is empty
    python scripts/seed.py --force    # add any bundled titles missing from the database
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.migrate import upgrade_db  # noqa: E402
from app.services.catalog import seed_catalog  # noqa: E402

if __name__ == "__main__":
    upgrade_db()
    with SessionLocal() as db:
        added = seed_catalog(db, force="--force" in sys.argv)
    print(f"Added {added} titles.")
