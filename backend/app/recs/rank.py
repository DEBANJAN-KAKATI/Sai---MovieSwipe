"""Candidate generation, scoring, explanation and deck assembly.

score(u, i) =  w1 * cos(E_i, C+)          embedding similarity to liked centroid
             + w2 * genre_affinity
             + w3 * keyword_affinity
             + w3b * people_affinity        (creators / cast)
             - w4 * cos(E_i, C-)           similarity to rejected centroid
             + w5 * freshness
             + w6 * availability_boost      (on the user's subscriptions)
             + w7 * social_boost            (friends saved it recently)
             + w8 * exploration_noise
             + mood / mode adjustment

Personal scores are converted to a percentile within the eligible pool and blended with a
popularity prior during cold start (0% personal with no signal, 70% until 20 swipes, then 90%).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import math
import random
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import User, UserMediaAction, utcnow
from ..services.catalog import CERT_ORDER, Media, all_media, get_media, media_card
from ..services.social import friend_positive_map
from .embed import dot
from .moods import DECOMPRESS, MOODS, mood_adjustment

W = {
    "sim_pos": 1.0,
    "genre": 0.35,
    "keyword": 0.30,
    "people": 0.12,
    "sim_neg": 0.5,
    "lang": 0.08,
    "fresh": 0.05,
    "avail": 0.06,
    "social": 0.05,
    "noise": 0.04,
    "mood": 0.5,
}

FEED_MODES = ("solo", "quick", "mood", "decompress", "new", "blind")
DONE_ACTIONS = {"watchlist", "must_visit", "liked", "watched"}


@dataclass
class UserCtx:
    user_id: str
    taste: dict
    acted: dict[str, tuple[str, dt.datetime]]
    filters: dict
    subscriptions: set[str]
    languages_pref: set[str]
    friend_likes: dict[str, list[str]]
    n_actions: int
    n_positive: int

    @property
    def alpha(self) -> float:
        if self.n_positive == 0:
            return 0.0
        return 0.7 if self.n_actions < 20 else 0.9


@dataclass
class Scored:
    media: Media
    personal: float = 0.0
    sim_pos: float = 0.0
    pct: float = 0.0
    final: float = 0.0
    because: str | None = None
    because_id: str | None = None
    reasons: list[str] = field(default_factory=list)
    explore: bool = False
    resurfaced: bool = False
    availability: str | None = None
    friends: list[str] = field(default_factory=list)
    match_percent: int | None = None


def build_ctx(db: Session, user: User, with_social: bool = True) -> UserCtx:
    rows = db.execute(
        select(UserMediaAction.media_id, UserMediaAction.action, UserMediaAction.updated_at).where(
            UserMediaAction.user_id == user.id
        )
    ).all()
    taste = user.taste or {}
    prefs = user.preferences or {}
    return UserCtx(
        user_id=user.id,
        taste=taste,
        acted={mid: (action, ts) for mid, action, ts in rows},
        filters=user.content_filters or {},
        subscriptions=set(user.subscription_providers or []),
        languages_pref=set(prefs.get("languages") or []),
        friend_likes=friend_positive_map(db, user.id) if with_social else {},
        n_actions=int(taste.get("n_actions", len(rows))),
        n_positive=int(taste.get("n_positive", 0)),
    )


# ---------------------------------------------------------------- filtering


def passes_content_filters(m: Media, filters: dict) -> bool:
    blocked_genres = set(filters.get("blocked_genres") or [])
    if blocked_genres and blocked_genres.intersection(m.genres):
        return False
    blocked_flags = set(filters.get("blocked_flags") or [])
    if blocked_flags and blocked_flags.intersection(m.content_flags):
        return False
    max_cert = filters.get("max_certification")
    if max_cert in CERT_ORDER and m.certification in CERT_ORDER:
        if CERT_ORDER[m.certification] > CERT_ORDER[max_cert]:
            return False
    return True


def passes_options(m: Media, mode: str, opts: dict, now: dt.datetime) -> bool:
    if opts.get("type") in ("movie", "tv") and m.type != opts["type"]:
        return False
    if opts.get("language") and m.language != opts["language"]:
        return False
    max_rt = opts.get("max_runtime")
    if max_rt and m.runtime_minutes and m.runtime_minutes > max_rt:
        return False
    if mode == "quick":
        limit = 120 if m.type == "movie" else 35
        if not m.runtime_minutes or m.runtime_minutes > limit:
            return False
    if mode == "new" and (not m.year or m.year < now.year - 6):
        return False
    return True


def eligibility(m: Media, ctx: UserCtx, now: dt.datetime) -> tuple[bool, bool, float]:
    """Returns (eligible, resurfaced, penalty) based on the user's prior actions."""
    prior = ctx.acted.get(m.id)
    if prior is None:
        return True, False, 0.0
    action, ts = prior
    if action in DONE_ACTIONS:
        return False, False, 0.0
    age = now - ts
    if action == "undecided":
        if age >= dt.timedelta(hours=settings.undecided_cooldown_hours):
            return True, True, 0.0
        return False, False, 0.0
    if action == "rejected":
        if age >= dt.timedelta(days=settings.rejected_cooldown_days):
            return True, False, 0.3  # decays back in, low priority
        return False, False, 0.0
    return True, False, 0.0


# ---------------------------------------------------------------- scoring


def _norm_max(d: dict[str, float]) -> float:
    return max((abs(v) for v in d.values()), default=0.0) or 1.0


def _stable_noise(*parts: str) -> float:
    h = hashlib.md5("|".join(parts).encode()).digest()
    return int.from_bytes(h[:4], "little") / 0xFFFFFFFF


def personal_score(m: Media, ctx: UserCtx) -> tuple[float, float]:
    """Returns (raw personal score, positive-centroid similarity)."""
    t = ctx.taste
    genres = t.get("genres", {})
    keywords = t.get("keywords", {})
    people = t.get("people", {})
    langs = t.get("languages", {})

    sim_pos = dot(m.embedding, t.get("pos_centroid"))
    sim_neg = dot(m.embedding, t.get("neg_centroid"))

    g_aff = 0.0
    if genres and m.genres:
        gmax = _norm_max(genres)
        g_aff = sum(genres.get(g, 0.0) for g in m.genres) / (gmax * math.sqrt(len(m.genres)))
    k_aff = 0.0
    if keywords and m.keywords:
        kmax = _norm_max(keywords)
        k_aff = math.tanh(sum(keywords.get(k.lower(), 0.0) for k in m.keywords) / (kmax * 2.0))
    p_aff = 0.0
    if people:
        pmax = _norm_max(people)
        names = ([m.creator] if m.creator else []) + m.cast[:3]
        p_aff = math.tanh(sum(people.get(p, 0.0) for p in names) / pmax)
    lang = 0.0
    if langs:
        lang = langs.get(m.language, 0.0) / _norm_max(langs)
    if ctx.languages_pref:
        lang = max(lang, 1.0 if m.language in ctx.languages_pref else -0.3)

    raw = (
        W["sim_pos"] * sim_pos
        + W["genre"] * g_aff
        + W["keyword"] * k_aff
        + W["people"] * p_aff
        - W["sim_neg"] * max(0.0, sim_neg)
        + W["lang"] * lang
    )
    return raw, sim_pos


def explain(m: Media, ctx: UserCtx, catalog_get) -> tuple[str | None, str | None, list[str]]:
    """'Because you liked X' + short reason chips from overlapping taste features."""
    best, best_id, best_sim = None, None, 0.0
    for seed in ctx.taste.get("seeds", [])[:25]:
        sm = catalog_get(seed["media_id"])
        if sm is None or sm.id == m.id:
            continue
        sim = dot(m.embedding, sm.embedding)
        if sim > best_sim:
            best, best_id, best_sim = sm.title, sm.id, sim
    because = f"Because you liked {best}" if best and best_sim >= 0.12 else None

    genres = ctx.taste.get("genres", {})
    keywords = ctx.taste.get("keywords", {})
    reasons: list[str] = []
    g_sorted = sorted((g for g in m.genres if genres.get(g, 0) > 0), key=lambda g: -genres[g])
    if g_sorted:
        reasons.append(g_sorted[0])
    k_sorted = sorted((k for k in m.keywords if keywords.get(k.lower(), 0) > 0), key=lambda k: -keywords[k.lower()])
    reasons.extend(k_sorted[:2])
    if m.year and ctx.taste.get("decades", {}).get(f"{m.year // 10 * 10}s", 0) > 0 and len(reasons) < 3:
        reasons.append(f"{m.year // 10 * 10}s")
    return because, (best_id if because else None), reasons[:3]


def availability_label(m: Media, subscriptions: set[str]) -> tuple[str | None, bool]:
    names = [p["name"] for p in m.providers_in]
    for n in names:
        if n in subscriptions:
            return f"On your {n}", True
    if names:
        return f"On {names[0]}", False
    return None, False


def mode_spec(mode: str, mood: str | None) -> dict | None:
    if mode == "decompress":
        return DECOMPRESS
    if mood and mood in MOODS:
        return MOODS[mood]
    return None


def percentile_map(values: list[float]) -> list[float]:
    if not values:
        return []
    order = sorted(range(len(values)), key=lambda i: values[i])
    n = len(values)
    out = [0.0] * n
    for rank, i in enumerate(order):
        out[i] = rank / (n - 1) if n > 1 else 1.0
    return out


def score_pool(
    db: Session,
    ctx: UserCtx,
    mode: str = "solo",
    mood: str | None = None,
    opts: dict | None = None,
    exclude: set[str] | None = None,
    pool: list[Media] | None = None,
    respect_history: bool = True,
) -> list[Scored]:
    opts = opts or {}
    exclude = exclude or set()
    now = utcnow()
    spec = mode_spec(mode, mood)
    items = pool if pool is not None else all_media(db)
    day_key = now.strftime("%Y-%m-%d")

    scored: list[Scored] = []
    for m in items:
        if m.id in exclude:
            continue
        if not passes_content_filters(m, ctx.filters) or not passes_options(m, mode, opts, now):
            continue
        resurfaced, penalty = False, 0.0
        if respect_history:
            ok, resurfaced, penalty = eligibility(m, ctx, now)
            if not ok:
                continue
        raw, sim_pos = personal_score(m, ctx)
        s = Scored(media=m, personal=raw, sim_pos=sim_pos, resurfaced=resurfaced)
        s.final = -penalty
        scored.append(s)

    pcts = percentile_map([s.personal for s in scored])
    alpha = ctx.alpha
    for s, p in zip(scored, pcts):
        m = s.media
        s.pct = p
        pop = min(1.0, m.popularity / 100.0)
        rating = ((m.vote_average or 7.0) - 5.0) / 5.0
        prior = 0.75 * pop + 0.25 * max(0.0, rating)
        ctx_boost = 0.0
        if spec:
            ctx_boost += W["mood"] * mood_adjustment(spec, m.genres, m.keywords, m.content_flags)
        if m.year and m.year >= now.year - 3:
            ctx_boost += 0.3 if mode == "new" else W["fresh"]
        s.availability, on_sub = availability_label(m, ctx.subscriptions)
        if on_sub:
            ctx_boost += W["avail"]
        s.friends = ctx.friend_likes.get(m.id, [])
        if s.friends:
            ctx_boost += W["social"] * min(3, len(s.friends))
        if s.resurfaced:
            ctx_boost += 0.03
        ctx_boost += W["noise"] * _stable_noise(ctx.user_id, day_key, m.id)
        s.final += alpha * p + (1 - alpha) * prior + ctx_boost
        if alpha > 0:
            closeness = min(1.0, max(0.0, s.sim_pos) / 0.5)
            s.match_percent = int(round(50 + 49 * (0.55 * p + 0.45 * closeness)))
    scored.sort(key=lambda x: x.final, reverse=True)
    return scored


def _genre_overlap(a: Media, b: Media) -> int:
    return len(set(a.genres) & set(b.genres))


def assemble_deck(
    ranked: list[Scored], ctx: UserCtx, limit: int, rng: random.Random, explore_rate: float = 0.12
) -> list[Scored]:
    """Greedy diversity-aware selection with an exploration slot."""
    if not ranked:
        return []
    window = ranked[: max(limit * 6, 40)]
    tail = ranked[len(ranked) // 3 :]
    top_genres = [g for g, _ in sorted(ctx.taste.get("genres", {}).items(), key=lambda kv: -kv[1])[:3]]
    n_explore = 0
    if ctx.alpha > 0 and len(ranked) > limit * 2:
        n_explore = max(1, round(limit * explore_rate))
    explore_positions = {limit - 1 - i * 5 for i in range(n_explore)} if n_explore else set()

    picks: list[Scored] = []
    used: set[str] = set()
    for pos in range(limit):
        if pos in explore_positions:
            options = [s for s in tail if s.media.id not in used and not set(s.media.genres) & set(top_genres)]
            if options:
                choice = rng.choice(options[:30])
                choice.explore = True
                picks.append(choice)
                used.add(choice.media.id)
                continue
        best, best_val = None, -1e9
        recent = picks[-2:]
        for s in window:
            if s.media.id in used:
                continue
            val = s.final - 0.06 * sum(_genre_overlap(s.media, r.media) for r in recent)
            if val > best_val:
                best, best_val = s, val
        if best is None:
            break
        picks.append(best)
        used.add(best.media.id)
    return picks


def card_from_scored(s: Scored, ctx: UserCtx, db: Session) -> dict:
    card = media_card(s.media)
    if ctx.alpha > 0:
        because, because_id, reasons = explain(s.media, ctx, lambda mid: get_media(db, mid))
    else:
        because, because_id, reasons = None, None, s.media.genres[:2]
    if s.resurfaced:
        because = "Back from Maybe Later"
    elif s.explore:
        because = "Exploring something different"
    elif because is None and ctx.alpha == 0:
        because = "Popular right now" if s.media.popularity >= 75 else "A strong place to start"
    card.update(
        {
            "match_percent": s.match_percent,
            "because": because,
            "because_media_id": because_id,
            "reasons": reasons,
            "badges": s.media.genres[:2],
            "availability": s.availability,
            "friends_saved": s.friends[:3],
            "friends_saved_count": len(s.friends),
            "explore": s.explore,
            "resurfaced": s.resurfaced,
        }
    )
    return card


def build_feed(
    db: Session,
    user: User,
    mode: str = "solo",
    mood: str | None = None,
    limit: int = 10,
    exclude: set[str] | None = None,
    opts: dict | None = None,
) -> dict:
    ctx = build_ctx(db, user)
    effective_mode = mode if mode in FEED_MODES else "solo"
    ranked = score_pool(db, ctx, effective_mode, mood, opts, exclude)
    rng = random.Random(f"{user.id}-{len(exclude or ())}-{ctx.n_actions}")
    deck = assemble_deck(ranked, ctx, limit, rng)
    return {
        "cards": [card_from_scored(s, ctx, db) for s in deck],
        "mode": effective_mode,
        "mood": mood,
        "cold_start": ctx.alpha == 0,
        "personalization": round(ctx.alpha, 2),
        "remaining": max(0, len(ranked) - len(deck)),
        "exhausted": len(deck) == 0,
    }


def similar_items(db: Session, m: Media, limit: int = 12, ctx: UserCtx | None = None) -> list[dict]:
    out = []
    for other in all_media(db):
        if other.id == m.id:
            continue
        sim = dot(m.embedding, other.embedding)
        jacc = len(set(m.genres) & set(other.genres)) / (len(set(m.genres) | set(other.genres)) or 1)
        out.append((0.8 * sim + 0.2 * jacc, other))
    out.sort(key=lambda t: t[0], reverse=True)
    result = []
    for score, other in out[:limit]:
        card = media_card(other)
        card["similarity_percent"] = int(round(100 * min(1.0, max(0.0, score) / 0.6)))
        if ctx is not None and other.id in ctx.acted:
            card["your_action"] = ctx.acted[other.id][0]
        result.append(card)
    return result
