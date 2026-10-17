"""Local cache for poster/title-card/logo images.

Phones load artwork from this server (`/api/img?url=…`) instead of hot-linking Wikimedia, which throttles bursts of
image requests (HTTP 429). Each image is downloaded once, politely, and kept in backend/image_cache/.
Only known image hosts are allowed, so the endpoint can't be used to fetch arbitrary URLs.
"""

from __future__ import annotations

import hashlib
import os
import mimetypes
import threading
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx

from ..config import BACKEND_DIR

CACHE_DIR = Path(os.environ.get("IMAGE_CACHE_DIR") or BACKEND_DIR / "image_cache")
ALLOWED_HOSTS = {"upload.wikimedia.org", "thumb.wikimedia.org", "image.tmdb.org", "static.tvmaze.com"}
USER_AGENT = "MovieSwipe/0.1 (personal hobby project; image cache)"
MAX_BYTES = 8 * 1024 * 1024
MAX_WIDTH = 900  # plenty for a phone card; TVmaze originals can be 4000px / 2MB+

_upstream = threading.Semaphore(2)  # at most two concurrent downloads from upstream hosts
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True)


def is_allowed(url: str) -> bool:
    p = urlparse(url)
    return p.scheme == "https" and p.hostname in ALLOWED_HOSTS


def proxied(url: str | None) -> str | None:
    """Rewrite an external artwork URL to this server's cached copy."""
    if not url or not is_allowed(url):
        return url
    return f"/api/img?url={quote(url, safe='')}"


def _path_for(url: str) -> Path:
    digest = hashlib.sha1(url.encode()).hexdigest()
    ext = Path(urlparse(url).path).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}:
        ext = ".img"
    return CACHE_DIR / digest[:2] / f"{digest}{ext}"


def cached_path(url: str) -> Path | None:
    p = _path_for(url)
    return p if p.exists() else None


def shrink(path: Path) -> None:
    """Downscale big raster images in place (keeps transparency for PNG/WebP logos)."""
    try:
        from PIL import Image
    except ImportError:
        return
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".img"}:
        return
    try:
        with Image.open(path) as im:
            if im.width <= MAX_WIDTH:
                return
            im.load()
            fmt = im.format or "JPEG"
            height = round(im.height * MAX_WIDTH / im.width)
            small = im.resize((MAX_WIDTH, height), Image.LANCZOS)
    except Exception:
        return
    tmp = path.with_suffix(path.suffix + ".part")
    if fmt == "JPEG" or small.mode not in ("RGBA", "LA", "P"):
        small.convert("RGB").save(tmp, "JPEG", quality=84, optimize=True, progressive=True)
    else:
        small.save(tmp, fmt)
    tmp.replace(path)


def fetch(url: str, attempts: int = 4) -> Path | None:
    """Return the cached file for url, downloading it first if needed. None if it can't be fetched."""
    if not is_allowed(url):
        return None
    path = _path_for(url)
    if path.exists():
        return path
    with _locks_guard:
        lock = _locks.setdefault(url, threading.Lock())
    with lock:
        if path.exists():
            return path
        delay = 1.5
        for _ in range(attempts):
            with _upstream:
                try:
                    r = _client.get(url)
                except httpx.HTTPError:
                    r = None
            if r is not None and r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                if len(r.content) > MAX_BYTES:
                    return None
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(path.suffix + ".part")
                tmp.write_bytes(r.content)
                tmp.replace(path)
                shrink(path)
                return path
            if r is not None and r.status_code not in (429, 500, 502, 503, 504):
                return None
            retry_after = r.headers.get("retry-after") if r is not None else None
            time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else delay)
            delay *= 2
    return None


def media_type_for(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "image/jpeg"
