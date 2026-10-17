"""'Where can I watch this in India?' links."""

from __future__ import annotations

from urllib.parse import quote_plus

from .catalog import Media

DISCLAIMER = "Streaming availability varies and changes often — verify on the provider's site."

# Services commonly available in India (used for the subscriptions picker).
PROVIDERS_IN = [
    {"name": "Netflix", "color": "#E50914", "domain": "netflix.com"},
    {"name": "Prime Video", "color": "#00A8E1", "domain": "primevideo.com"},
    {"name": "JioHotstar", "color": "#1F80E0", "domain": "hotstar.com"},
    {"name": "SonyLIV", "color": "#F5A623", "domain": "sonyliv.com"},
    {"name": "ZEE5", "color": "#8230C6", "domain": "zee5.com"},
    {"name": "Apple TV+", "color": "#A2AAAD", "domain": "tv.apple.com"},
    {"name": "Aha", "color": "#FF6D00", "domain": "aha.video"},
    {"name": "Sun NXT", "color": "#F7B500", "domain": "sunnxt.com"},
    {"name": "MX Player", "color": "#2D9CDB", "domain": "mxplayer.in"},
    {"name": "Lionsgate Play", "color": "#C9A227", "domain": "lionsgateplay.com"},
    {"name": "YouTube", "color": "#FF0000", "domain": "youtube.com"},
]
_PROVIDER_DOMAINS = {p["name"]: p["domain"] for p in PROVIDERS_IN}


def google_watch_url(title: str) -> str:
    return f"https://www.google.com/search?q=where+can+I+watch+{quote_plus(title)}+in+India"


def provider_search_url(provider: str, title: str) -> str:
    if provider == "Netflix":
        return f"https://www.netflix.com/search?q={quote_plus(title)}"
    if provider == "Prime Video":
        return f"https://www.primevideo.com/search/?phrase={quote_plus(title)}"
    domain = _PROVIDER_DOMAINS.get(provider)
    query = f"{title} site:{domain}" if domain else f"{title} {provider}"
    return f"https://www.google.com/search?q={quote_plus(query)}"


def trailer_links(m: Media) -> dict:
    query = quote_plus(f"{m.title} {m.year or ''} official trailer".strip())
    return {
        "youtube_key": m.trailer_key,
        "embed_url": f"https://www.youtube-nocookie.com/embed/{m.trailer_key}" if m.trailer_key else None,
        "search_url": f"https://www.youtube.com/results?search_query={query}",
    }


def watch_info(m: Media, subscriptions: set[str] | None = None) -> dict:
    subscriptions = subscriptions or set()
    providers = [
        {
            "name": p["name"],
            "type": p.get("type", "flatrate"),
            "link": p.get("link") or provider_search_url(p["name"], m.title),
            "on_your_plan": p["name"] in subscriptions,
        }
        for p in m.providers_in
    ]
    providers.sort(key=lambda p: (not p["on_your_plan"], p["type"] != "flatrate"))
    return {
        "google_url": google_watch_url(m.title),
        "providers": providers,
        "on_your_services": [p["name"] for p in providers if p["on_your_plan"]],
        "disclaimer": DISCLAIMER,
    }
