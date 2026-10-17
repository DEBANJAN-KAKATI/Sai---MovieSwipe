"""Mood and context modes: genre/keyword re-weighting applied on top of personal taste."""

from __future__ import annotations

MOODS: dict[str, dict] = {
    "cozy": {
        "label": "Cozy",
        "emoji": "☕",
        "genres": {"Comedy": 0.25, "Family": 0.3, "Romance": 0.15, "Animation": 0.25},
        "keywords": {"feel-good": 0.35, "friendship": 0.1, "small town": 0.1, "slice of life": 0.25, "family": 0.1},
        "avoid_genres": {"Horror": 0.6, "Thriller": 0.25, "War": 0.3},
        "avoid_flags": {"gore": 0.5, "disturbing": 0.4, "violence": 0.2},
    },
    "intense": {
        "label": "Intense",
        "emoji": "🔥",
        "genres": {"Thriller": 0.3, "Action": 0.25, "Crime": 0.15},
        "keywords": {"survival": 0.2, "heist": 0.2, "cat and mouse": 0.2, "revenge": 0.15, "spy": 0.15},
        "avoid_genres": {"Family": 0.3, "Animation": 0.2},
        "avoid_flags": {},
    },
    "mind-bend": {
        "label": "Mind-bend",
        "emoji": "🌀",
        "genres": {"Sci-Fi": 0.25, "Mystery": 0.25},
        "keywords": {
            "mind-bending": 0.45,
            "twist ending": 0.3,
            "time travel": 0.3,
            "nonlinear timeline": 0.25,
            "simulated reality": 0.3,
            "psychological": 0.15,
            "multiverse": 0.25,
        },
        "avoid_genres": {"Family": 0.2},
        "avoid_flags": {},
    },
    "laugh": {
        "label": "Laugh out loud",
        "emoji": "😂",
        "genres": {"Comedy": 0.5},
        "keywords": {"sitcom": 0.2, "slapstick": 0.25, "workplace comedy": 0.2, "mockumentary": 0.2},
        "avoid_genres": {"Horror": 0.3, "War": 0.3},
        "avoid_flags": {"disturbing": 0.3},
    },
    "dark": {
        "label": "Dark & gritty",
        "emoji": "🌑",
        "genres": {"Crime": 0.25, "Thriller": 0.2, "Horror": 0.15},
        "keywords": {"dark": 0.35, "serial killer": 0.2, "antihero": 0.2, "neo-noir": 0.25, "gangster": 0.15},
        "avoid_genres": {"Family": 0.4, "Animation": 0.3},
        "avoid_flags": {},
    },
    "romantic": {
        "label": "Romantic",
        "emoji": "💘",
        "genres": {"Romance": 0.5},
        "keywords": {"love story": 0.3, "romantic comedy": 0.3, "kdrama": 0.15},
        "avoid_genres": {"Horror": 0.4},
        "avoid_flags": {"gore": 0.4},
    },
    "epic": {
        "label": "Epic",
        "emoji": "⚔️",
        "genres": {"Adventure": 0.25, "Fantasy": 0.25, "Action": 0.15, "History": 0.15, "War": 0.15},
        "keywords": {"epic": 0.4, "kingdom": 0.2, "war": 0.15, "space": 0.1, "period piece": 0.1},
        "avoid_genres": {},
        "avoid_flags": {},
    },
    "learn": {
        "label": "Learn something",
        "emoji": "🧠",
        "genres": {"Documentary": 0.5, "History": 0.25},
        "keywords": {"based on true story": 0.3, "biopic": 0.3, "scientists": 0.2},
        "avoid_genres": {},
        "avoid_flags": {},
    },
}

DECOMPRESS = {
    "genres": {"Comedy": 0.3, "Family": 0.3, "Animation": 0.3, "Documentary": 0.1},
    "keywords": {"feel-good": 0.35, "slice of life": 0.25},
    "avoid_genres": {"Horror": 0.8, "Thriller": 0.3, "War": 0.4, "Crime": 0.15},
    "avoid_flags": {"violence": 0.4, "gore": 0.9, "disturbing": 0.9, "sexual": 0.2},
}


def mood_adjustment(spec: dict | None, genres: list[str], keywords: list[str], flags: list[str]) -> float:
    if not spec:
        return 0.0
    adj = 0.0
    for g in genres:
        adj += spec["genres"].get(g, 0.0)
        adj -= spec.get("avoid_genres", {}).get(g, 0.0)
    kws = {k.lower() for k in keywords}
    for k, w in spec["keywords"].items():
        if k in kws:
            adj += w
    for f in flags:
        adj -= spec.get("avoid_flags", {}).get(f, 0.0)
    return adj


def moods_meta() -> list[dict]:
    return [{"key": k, "label": v["label"], "emoji": v["emoji"]} for k, v in MOODS.items()]
