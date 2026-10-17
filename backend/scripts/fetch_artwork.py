"""Find artwork for the bundled catalog.

    python scripts/fetch_artwork.py                  # look up titles missing from data/artwork.json
    python scripts/fetch_artwork.py --refresh        # look everything up again
    python scripts/fetch_artwork.py --type tv        # (re)fetch only TV shows
    python scripts/fetch_artwork.py --only "The Mentalist,Dark"
    python scripts/fetch_artwork.py --warm-only      # just download missing images into the local cache

Sources (official public APIs, no keys):
  * TV shows: TVmaze (https://www.tvmaze.com/api) — portrait posters (~680x1000) and landscape backgrounds.
  * Films, and shows TVmaze doesn't know: English Wikipedia's infobox image.

Each title's article infobox image is classified by shape:
  portrait (h/w >= 1.15)      -> poster   (fills the card)
  wide photo / title card     -> backdrop (fills the card, cropped)
  very wide (logos/wordmarks) -> logo     (shown on a plate over generated art)

Results go to app/data/artwork.json (URLs only — images are loaded from Wikimedia at runtime and are not
redistributed with the app) and are applied to the database. Film posters on Wikipedia are non-free
images used there under fair use; keep the attribution link (image_source) visible in the app.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.migrate import upgrade_db  # noqa: E402
from app.services import images  # noqa: E402
from app.services.catalog import ARTWORK_FILE, DATA_FILE, apply_artwork, artwork_key, seed_catalog  # noqa: E402

API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "MovieSwipe/0.1 (personal hobby project; https://github.com/; poster lookup)"}
THUMB = 500
MEDIA_WORDS = re.compile(
    r"film|movie|series|television|tv|sitcom|anime|miniseries|documentary|show|drama|serial|web", re.I
)

# Article titles for names that search alone gets wrong or that share a name with something more famous.
OVERRIDES = {
    "Scam 1992: The Harshad Mehta Story|tv": "Scam 1992",
    "The Office|tv": "The Office (American TV series)",
    "House M.D.|tv": "House (TV series)",
    "Suits|tv": "Suits (American TV series)",
    "Leverage|tv": "Leverage (American TV series)",
    "Shōgun|tv": "Shōgun (2024 TV series)",
    "Dune|movie": "Dune (2021 film)",
    "Up|movie": "Up (2009 film)",
    "Queen|movie": "Queen (2014 film)",
    "Talaash|movie": "Talaash: The Answer Lies Within",
    "Drishyam|movie": "Drishyam (2015 film)",
    "Pride & Prejudice|movie": "Pride & Prejudice (2005 film)",
    "The Family Man|tv": "The Family Man (Indian TV series)",
    "Planet Earth II|tv": "Planet Earth II",
    "Black Mirror|tv": "Black Mirror",
    "Friends|tv": "Friends",
    "Dark|tv": "Dark (TV series)",
    "Stree|movie": "Stree (2018 film)",
    "Kahaani|movie": "Kahaani",
    "Chernobyl|tv": "Chernobyl (miniseries)",
    "Avatar: The Last Airbender|tv": "Avatar: The Last Airbender",
    "Sherlock|tv": "Sherlock (TV series)",
    "Psych|tv": "Psych",
    "Monk|tv": "Monk (TV series)",
    "Castle|tv": "Castle (TV series)",
    "Mirzapur|tv": "Mirzapur (TV series)",
    "Death Note|tv": "Death Note (2006 TV series)",
    "Bridgerton|tv": "Bridgerton (TV series)",
    "Se7en|movie": "Seven (1995 film)",
    "Numb3rs|tv": "Numbers (TV series)",
}

client = httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True)


def api(params: dict, attempts: int = 5) -> dict:
    delay = 1.0
    for _ in range(attempts):
        try:
            r = client.get(API, params={"format": "json", "formatversion": 2, **params})
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                time.sleep(0.2)  # be polite
                return r.json()
        except httpx.HTTPError:
            pass
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"Wikipedia API kept failing for {params}")


def norm(title: str) -> str:
    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\s*\(.*?\)\s*$", "", t).replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", t)


def clean_url(url: str | None) -> str | None:
    return url.split("?", 1)[0] if url else None


PAGE_PROPS = {"prop": "pageimages|description", "piprop": "thumbnail", "pithumbsize": THUMB, "pilicense": "any"}


def find_page(title: str, year: int | None, media_type: str) -> dict | None:
    override = OVERRIDES.get(artwork_key(title, media_type))
    if override:
        pages = api({"action": "query", "titles": override, "redirects": 1, **PAGE_PROPS})["query"]["pages"]
        return pages[0] if pages and not pages[0].get("missing") else None

    kind = "film" if media_type == "movie" else "television series"
    pages = api(
        {"action": "query", "generator": "search", "gsrsearch": f"{title} {year or ''} {kind}", "gsrlimit": 6,
         **PAGE_PROPS}
    ).get("query", {}).get("pages", [])
    pages.sort(key=lambda p: p.get("index", 99))
    want = norm(title)

    def ok(p: dict, exact: bool) -> bool:
        desc = p.get("description") or ""
        if desc and not MEDIA_WORDS.search(desc):
            return False
        if re.search(r"\b(season|episode|soundtrack|list of|character|actor|actress)\b", p["title"] + " " + desc, re.I):
            return False
        return norm(p["title"]) == want if exact else norm(p["title"]).startswith(want)

    for exact in (True, False):
        matches = [p for p in pages if ok(p, exact)]
        if matches:
            if year:  # prefer the article whose description mentions the right year
                matches.sort(key=lambda p: str(year) not in (p.get("description") or ""))
            return matches[0]
    return None


def infobox_image(page_title: str) -> dict | None:
    wt = api({"action": "parse", "page": page_title, "prop": "wikitext", "section": 0, "redirects": 1})
    text = (wt.get("parse") or {}).get("wikitext", "")
    m = re.search(r"\|\s*image\s*=\s*([^\n|{}<]+)", text)
    if not m:
        return None
    name = re.sub(r"^\[\[(?:File|Image):", "", m.group(1).strip()).split("|")[0].strip()
    if not name or "." not in name:
        return None
    pages = api({"action": "query", "titles": f"File:{name}", "prop": "imageinfo", "iiprop": "url|size",
                 "iiurlwidth": THUMB})["query"]["pages"]
    info = (pages[0].get("imageinfo") or [None])[0] if pages else None
    if not info:
        return None
    return {
        "source": info.get("thumburl") or info.get("url"),
        "width": info.get("thumbwidth") or info.get("width"),
        "height": info.get("thumbheight") or info.get("height"),
    }


def classify(img: dict) -> str:
    ratio = (img.get("height") or 1) / (img.get("width") or 1)
    if ratio >= 1.15:
        return "poster"
    if ratio >= 0.42:
        return "backdrop"
    return "logo"


def wiki_lookup(title: str, year: int | None, media_type: str) -> dict | None:
    page = find_page(title, year, media_type)
    if page is None:
        return None
    img = page.get("thumbnail")
    if not img:
        img = infobox_image(page["title"])
    entry = {
        "page": page["title"],
        "source": f"https://en.wikipedia.org/wiki/{quote(page['title'].replace(' ', '_'))}",
        "credit": "Wikipedia",
    }
    if img and img.get("source"):
        kind = classify(img)
        entry[kind] = clean_url(img["source"])
        entry["shape"] = f"{img.get('width')}x{img.get('height')}"
    return entry


TVMAZE = "https://api.tvmaze.com"
TVMAZE_NAMES = {"House M.D.": "House", "Money Heist": "La Casa de Papel"}


def tvmaze_get(path: str, **params) -> list | dict | None:
    delay = 2.0
    for _ in range(4):
        try:
            r = client.get(f"{TVMAZE}{path}", params=params)
        except httpx.HTTPError:
            r = None
        if r is not None and r.status_code == 200:
            time.sleep(0.6)  # TVmaze allows 20 calls / 10 s
            return r.json()
        if r is not None and r.status_code == 404:
            return None
        time.sleep(delay)
        delay *= 2
    return None


def tvmaze_lookup(title: str, year: int | None) -> dict | None:
    results = tvmaze_get("/search/shows", q=TVMAZE_NAMES.get(title, title)) or []
    want = norm(title)
    show = None
    for hit in results:
        s = hit["show"]
        premiered = (s.get("premiered") or "")[:4]
        same_year = year and premiered.isdigit() and abs(int(premiered) - year) <= 1
        if same_year or (not year and norm(s["name"]) == want):
            show = s
            break
    if not show or not show.get("image"):
        return None
    entry = {
        "poster": show["image"].get("original") or show["image"].get("medium"),
        "source": show.get("url"),
        "page": show["name"],
        "credit": "TVmaze",
    }
    imgs = tvmaze_get(f"/shows/{show['id']}/images") or []
    backgrounds = [i for i in imgs if i.get("type") == "background"]
    backgrounds.sort(key=lambda i: not i.get("main"))
    if backgrounds:
        res = backgrounds[0]["resolutions"]
        entry["backdrop"] = (res.get("medium") or res.get("original") or {}).get("url")
    return entry


def lookup(item: dict) -> dict | None:
    title, year, media_type = item["t"], item.get("y"), item["type"]
    wiki = wiki_lookup(title, year, media_type)
    if media_type != "tv":
        return wiki
    tv = tvmaze_lookup(title, year)
    if not tv:
        return wiki
    # TVmaze poster for the card; its background (or Wikipedia's title card) for the details header.
    tv["backdrop"] = tv.get("backdrop") or (wiki or {}).get("backdrop")
    return tv


def warm_cache() -> None:
    """Download every artwork image into backend/image_cache, one per second, so phones never wait on Wikimedia."""
    art = json.loads(ARTWORK_FILE.read_text(encoding="utf-8")) if ARTWORK_FILE.exists() else {}
    urls = [v[k] for v in art.values() for k in ("poster", "backdrop", "logo") if v.get(k)]
    missing = [u for u in urls if not images.cached_path(u)]
    print(f"Image cache: {len(urls) - len(missing)}/{len(urls)} already cached, downloading {len(missing)}...")
    failed = 0
    for n, url in enumerate(missing, 1):
        if images.fetch(url) is None:
            failed += 1
        if n % 25 == 0:
            print(f"  {n}/{len(missing)}")
        time.sleep(1.0)
    print(f"Image cache ready ({len(urls) - failed}/{len(urls)} images; {failed} failed — rerun with --warm-only).")
    keep = {images.cached_path(u) for u in urls} - {None}
    stale = [p for p in images.CACHE_DIR.rglob("*") if p.is_file() and p not in keep]
    for p in stale:
        p.unlink()
    if stale:
        print(f"Removed {len(stale)} cached images no longer used.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="look up every title again")
    parser.add_argument("--only", default="", help="comma-separated titles to (re)fetch")
    parser.add_argument("--type", choices=["movie", "tv"], help="only (re)fetch this kind of title")
    parser.add_argument("--warm-only", action="store_true", help="just download missing images into the local cache")
    args = parser.parse_args()

    if args.warm_only:
        warm_cache()
        return 0

    catalog = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    art = {} if args.refresh or not ARTWORK_FILE.exists() else json.loads(ARTWORK_FILE.read_text(encoding="utf-8"))
    only = {t.strip() for t in args.only.split(",") if t.strip()}

    if args.type:
        todo = [i for i in catalog if i["type"] == args.type]
    else:
        todo = [i for i in catalog if (i["t"] in only) or (not only and artwork_key(i["t"], i["type"]) not in art)]
    print(f"Looking up {len(todo)} of {len(catalog)} titles (TVmaze for TV, Wikipedia for films)...")
    found = {"poster": 0, "backdrop": 0, "logo": 0, "none": 0}
    for n, item in enumerate(todo, 1):
        key = artwork_key(item["t"], item["type"])
        try:
            entry = lookup(item)
        except RuntimeError as exc:
            print(f"  ! {item['t']}: {exc}")
            continue
        art[key] = entry or {}
        kind = next((k for k in ("poster", "backdrop", "logo") if entry and entry.get(k)), "none")
        found[kind] += 1
        credit = (entry or {}).get("credit", "")
        print(f"  [{n:>3}/{len(todo)}] {kind:8} {credit:9} {item['t']} <- {entry['page'] if entry else 'no article found'}")
        if n % 20 == 0:
            ARTWORK_FILE.write_text(json.dumps(art, indent=1, ensure_ascii=False), encoding="utf-8")

    ARTWORK_FILE.write_text(json.dumps(art, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nPosters {found['poster']} · title cards {found['backdrop']} · logos {found['logo']} · none {found['none']}")

    upgrade_db()
    with SessionLocal() as db:
        seed_catalog(db)
        changed = apply_artwork(db, overwrite=True)
    print(f"Applied artwork to {changed} titles in the database (restart the API to refresh its cache).")
    warm_cache()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
