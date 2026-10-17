"""Bootstrap taste from Letterboxd / IMDb CSV exports."""

from __future__ import annotations

import csv
import io
import re
import unicodedata

from sqlalchemy.orm import Session

from ..models import User
from .actions import apply_action, current_action
from .catalog import all_media
from .taste import refresh_taste


def norm_title(title: str) -> str:
    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"^(the|a|an)\s+", "", t.strip())
    return re.sub(r"[^a-z0-9]+", "", t)


def _num(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def parse_csv(content: bytes) -> tuple[str, list[dict]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    fields = {f.strip().lower(): f for f in (reader.fieldnames or [])}
    rows = []
    if "name" in fields:  # Letterboxd (ratings.csv / watched.csv / watchlist.csv / diary.csv)
        kind = "letterboxd"
        for r in reader:
            rating = _num(r.get(fields.get("rating", ""), None))  # 0.5 - 5 stars
            rows.append({"title": r[fields["name"]], "year": _num(r.get(fields.get("year", ""), None)),
                         "stars": rating})
    elif "title" in fields:  # IMDb export
        kind = "imdb"
        rating_col = fields.get("your rating")
        for r in reader:
            rating = _num(r.get(rating_col)) if rating_col else None  # 1 - 10
            rows.append({"title": r[fields["title"]], "year": _num(r.get(fields.get("year", ""), None)),
                         "stars": rating / 2 if rating is not None else None})
    else:
        raise ValueError("Unrecognised CSV: expected a Letterboxd or IMDb export with a Name/Title column")
    return kind, rows


def import_csv(db: Session, user: User, content: bytes, list_kind: str = "auto") -> dict:
    """list_kind: auto | watched | watchlist. Ratings >= 3.5★ become 'liked', <= 2★ become 'rejected'."""
    kind, rows = parse_csv(content)
    index: dict[str, list] = {}
    for m in all_media(db):
        index.setdefault(norm_title(m.title), []).append(m)

    matched, unmatched = [], []
    added = {"liked": 0, "watchlist": 0, "watched": 0, "rejected": 0}
    for r in rows:
        candidates = index.get(norm_title(r["title"] or ""), [])
        if r["year"] and len(candidates) > 1:
            candidates = [m for m in candidates if m.year and abs(m.year - int(r["year"])) <= 1] or candidates
        if not candidates:
            unmatched.append(r["title"])
            continue
        m = candidates[0]
        stars = r["stars"]
        if list_kind == "watchlist":
            action, rating = "watchlist", None
        elif stars is None:
            action, rating = ("watched", None) if list_kind == "watched" else ("liked", None)
        elif stars >= 3.5:
            action, rating = "liked", None
        elif stars <= 2:
            action, rating = "rejected", None
        else:
            action, rating = "watched", 3
        existing = current_action(db, user.id, m.id)
        if existing and existing.action in ("must_visit", "liked") and action != "liked":
            continue  # don't downgrade stronger signals
        apply_action(db, user, m.id, action, rating=rating, refresh=False)
        added[action] += 1
        matched.append(m.title)
    refresh_taste(db, user)
    db.commit()
    return {
        "source": kind,
        "rows": len(rows),
        "matched": len(matched),
        "matched_titles": matched[:50],
        "unmatched": unmatched[:50],
        "unmatched_count": len(unmatched),
        "added": added,
    }
