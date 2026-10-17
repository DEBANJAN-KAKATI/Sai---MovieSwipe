"""Grow / enrich the catalog from TMDB.

    python scripts/sync_tmdb.py --pages 5            # trending movies + TV, plus popular Indian titles
    python scripts/sync_tmdb.py --enrich-seed        # add posters, trailers and IN providers to bundled titles

Requires TMDB_API_KEY (v3 key or v4 read token) in the environment or .env.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.migrate import upgrade_db  # noqa: E402
from app.models import MediaItem  # noqa: E402
from app.services import tmdb  # noqa: E402
from app.services.catalog import rebuild_embeddings, seed_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pages", type=int, default=3, help="pages of trending results per type (20 per page)")
    parser.add_argument("--no-indian", action="store_true", help="skip the popular Indian-language discover pass")
    parser.add_argument("--enrich-seed", action="store_true", help="enrich bundled titles instead of importing new")
    args = parser.parse_args()

    if not settings.tmdb_enabled:
        print("TMDB_API_KEY is not set — add it to .env first (https://www.themoviedb.org/settings/api).")
        return 1

    upgrade_db()
    client = tmdb.TMDB()
    with SessionLocal() as db:
        seed_catalog(db)
        if args.enrich_seed:
            rows = db.scalars(select(MediaItem).where(MediaItem.source == "seed", MediaItem.tmdb_id.is_(None))).all()
            ok = 0
            for i, row in enumerate(rows, 1):
                try:
                    ok += tmdb.enrich_seed_item(db, client, row)
                except httpx.HTTPError as exc:
                    print(f"  ! {row.title}: {exc}")
                if i % 20 == 0:
                    db.commit()
                    print(f"  {i}/{len(rows)} …")
            db.commit()
            print(f"Enriched {ok}/{len(rows)} bundled titles.")
        else:
            refs: list[tuple[str, int]] = []
            for media_type in ("movie", "tv"):
                for page in range(1, args.pages + 1):
                    refs += [(media_type, r["id"]) for r in client.trending(media_type, page)]
                    if not args.no_indian:
                        refs += [(media_type, r["id"]) for r in client.discover_indian(media_type, page)]
            refs = list(dict.fromkeys(refs))
            print(f"Fetching details for {len(refs)} titles …")
            rows = tmdb.import_titles(db, client, refs)
            print(f"Upserted {len(rows)} titles.")
        n = rebuild_embeddings(db)
        print(f"Rebuilt embeddings for {n} titles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
