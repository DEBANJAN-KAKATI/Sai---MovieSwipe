"""Item embeddings.

Default backend ("hash") is a TF-IDF weighted bag of semantic features (genres, keywords,
people, overview words, language, decade) projected into a fixed 384-dim space with the
hashing trick. It needs no model download and captures the keyword/genre neighbourhoods
the recommender relies on (e.g. "consultant" + "police procedural" for The Mentalist).

Set EMBEDDING_BACKEND=sbert (and install the `sbert` extra) to use a sentence-transformer
model instead; its output is also 384-dim, so the rest of the system is unchanged.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Sequence
from typing import Protocol

from ..config import settings

DIM = 384

_STOP = set(
    """a an the and or but of to in on at by for with from into onto over under as is are was were be been
    being his her their its our your my he she they them it this that these those who whom whose which what
    when where why how all any both each few more most other some such no nor not only own same so than too
    very can will just after before while during until against between through about above below up down out
    off again further then once here there one two three four five six seven eight nine ten years year new
    life world man woman men women young old must find finds takes take gets get becomes become comes come
    makes make himself herself themselves itself own first last day days night nights even ever never every
    everything nothing someone something anyone anything set sets begins begin back away along across around
    only out own also turns turn starts start tries try toward towards help helps""".split()
)
_WORD = re.compile(r"[a-zA-ZÀ-ÿ]+")


class Embeddable(Protocol):
    title: str
    type: str
    overview: str
    genres: list
    keywords: list
    cast: list
    creator: str | None
    language: str
    year: int | None


def _stem(word: str) -> str:
    w = word.lower()
    for suffix in ("ing", "ers", "er", "es", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def features(item: Embeddable) -> dict[str, float]:
    feats: dict[str, float] = {}

    def add(key: str, weight: float) -> None:
        feats[key] = feats.get(key, 0.0) + weight

    for g in item.genres or []:
        add(f"g:{g.lower()}", 3.0)
    for k in item.keywords or []:
        k = k.lower()
        add(f"k:{k}", 2.2)
        for part in k.split():
            if part not in _STOP and len(part) > 2:
                add(f"w:{_stem(part)}", 0.4)
    for word in _WORD.findall(item.overview or ""):
        lw = word.lower()
        if len(lw) > 3 and lw not in _STOP:
            add(f"w:{_stem(lw)}", 0.6)
    if item.creator:
        for person in re.split(r"\s*(?:&|,| and )\s*", item.creator):
            if person:
                add(f"p:{person.lower()}", 1.4)
    for name in (item.cast or [])[:4]:
        add(f"p:{str(name).lower()}", 0.9)
    add(f"lang:{(item.language or 'en').lower()}", 1.2)
    add(f"type:{item.type}", 0.6)
    if item.year:
        add(f"dec:{item.year // 10 * 10}", 0.7)
    return feats


def compute_idf(docs: Sequence[dict[str, float]]) -> dict[str, float]:
    n = len(docs) or 1
    df: dict[str, int] = {}
    for d in docs:
        for key in d:
            df[key] = df.get(key, 0) + 1
    return {key: math.log((1 + n) / (1 + c)) + 1.0 for key, c in df.items()}


def _bucket(key: str) -> tuple[int, float]:
    h = hashlib.md5(key.encode("utf-8")).digest()
    idx = int.from_bytes(h[:4], "little") % DIM
    sign = 1.0 if h[4] & 1 else -1.0
    return idx, sign


def vectorize(feats: dict[str, float], idf: dict[str, float]) -> list[float]:
    vec = [0.0] * DIM
    default_idf = max(idf.values(), default=1.0)
    for key, weight in feats.items():
        idx, sign = _bucket(key)
        vec[idx] += sign * weight * idf.get(key, default_idf)
    return normalize(vec)


def normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [round(v / norm, 5) for v in vec]


def dot(a: Sequence[float] | None, b: Sequence[float] | None) -> float:
    if not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _sbert_embed(items: Sequence[Embeddable]) -> list[list[float]] | None:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError:
        return None
    model = SentenceTransformer(settings.embedding_model)
    texts = [
        f"{i.title}. {', '.join(i.genres or [])}. {', '.join(i.keywords or [])}. {i.overview or ''}" for i in items
    ]
    out = model.encode(texts, normalize_embeddings=True)
    return [[round(float(v), 5) for v in row] for row in out]


def build_embeddings(items: Iterable[Embeddable]) -> list[list[float]]:
    """Return one embedding per item (IDF is computed over the given corpus)."""
    items = list(items)
    if settings.embedding_backend == "sbert":
        vecs = _sbert_embed(items)
        if vecs is not None:
            return vecs
    docs = [features(i) for i in items]
    idf = compute_idf(docs)
    return [vectorize(d, idf) for d in docs]
