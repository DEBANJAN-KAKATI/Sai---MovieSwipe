"""Phase 1 'definition of done' checks (README §16, items 1–7) plus core solo behaviour."""

import dataclasses

from app.config import settings
from app.recs import rank

CRIME_PROCEDURALS = ["The Mentalist", "Psych", "Castle", "Elementary", "Monk"]


def _swipe(client, h, media_id, action, **extra):
    r = client.post("/api/swipe", headers=h, json={"media_id": media_id, "action": action, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_cold_start_then_onboarding_personalises_deck(client, guest, titles):
    h, user = guest("Asha")
    cold = client.get("/api/feed?limit=8", headers=h).json()
    assert cold["cold_start"] is True and len(cold["cards"]) == 8
    assert all(c["match_percent"] is None for c in cold["cards"])

    tiles = client.get("/api/onboarding/tiles", headers=h).json()["tiles"]
    assert len(tiles) >= 12

    r = client.post("/api/onboarding/taste", headers=h, json={
        "liked_ids": [titles["The Mentalist"], titles["Sherlock"], titles["Lie to Me"]],
        "subscriptions": ["Netflix"], "languages": [],
    })
    assert r.status_code == 200
    assert client.get("/api/users/me", headers=h).json()["onboarded"] is True

    feed = client.get("/api/feed?limit=10", headers=h).json()
    assert feed["cold_start"] is False and len(feed["cards"]) == 10
    liked = {titles["The Mentalist"], titles["Sherlock"], titles["Lie to Me"]}
    assert not liked & {c["media_id"] for c in feed["cards"]}, "already-liked titles must not reappear"
    assert any(c["because"] and c["because"].startswith("Because you liked") for c in feed["cards"])
    assert all(c["match_percent"] is not None for c in feed["cards"] if not c["explore"])


def test_six_interactions_land_in_correct_lists(client, guest, titles):
    h, _ = guest()
    _swipe(client, h, titles["Dark"], "watchlist")
    _swipe(client, h, titles["Friends"], "rejected")
    _swipe(client, h, titles["Dune"], "undecided")
    _swipe(client, h, titles["Interstellar"], "must_visit")
    _swipe(client, h, titles["Arrival"], "watch_intent")
    _swipe(client, h, titles["Severance"], "impression_detail")

    wl = client.get("/api/lists/watchlist", headers=h).json()
    assert [c["title"] for c in wl["must_visit"]] == ["Interstellar"]
    assert [c["title"] for c in wl["watchlist"]] == ["Dark"]
    assert [c["title"] for c in client.get("/api/lists/undecided", headers=h).json()["items"]] == ["Dune"]
    rejected = client.get("/api/lists/history?kind=rejected", headers=h).json()["items"]
    assert [c["title"] for c in rejected] == ["Friends"]
    counts = client.get("/api/lists/counts", headers=h).json()
    assert "watch_intent" not in counts and "impression_detail" not in counts  # logged only


def test_must_visit_pinned_and_sorting(client, guest, titles):
    h, _ = guest()
    for t in ["Inception", "Primer", "Interstellar"]:
        _swipe(client, h, titles[t], "watchlist")
    _swipe(client, h, titles["Memento"], "must_visit")
    wl = client.get("/api/lists/watchlist?sort=runtime", headers=h).json()
    assert wl["must_visit"][0]["title"] == "Memento"
    assert [c["title"] for c in wl["watchlist"]] == ["Primer", "Inception", "Interstellar"]


def test_undecided_resurfaces_after_cooldown(client, guest, titles, monkeypatch):
    h, _ = guest()
    _swipe(client, h, titles["Kahaani"], "liked")
    _swipe(client, h, titles["Drishyam"], "undecided")
    ids = lambda: {c["media_id"] for c in client.get("/api/feed?limit=30&language=hi", headers=h).json()["cards"]}  # noqa: E731
    assert titles["Drishyam"] not in ids()
    monkeypatch.setattr(rank, "settings", dataclasses.replace(settings, undecided_cooldown_hours=0))
    cards = client.get("/api/feed?limit=30&language=hi", headers=h).json()["cards"]
    back = [c for c in cards if c["media_id"] == titles["Drishyam"]]
    assert back and back[0]["resurfaced"] and back[0]["because"] == "Back from Maybe Later"


def test_flip_panel_qa_and_similar(client, guest, titles):
    h, _ = guest()
    _swipe(client, h, titles["Psych"], "liked")
    d = client.get(f"/api/media/{titles['The Mentalist']}", headers=h).json()
    qa = d["qa"]
    assert qa["about"] and qa["format"].startswith("Series")
    assert "Simon Baker" in qa["cast"]
    assert qa["trailer"]["search_url"].startswith("https://www.youtube.com/results")
    assert qa["match"]["match_percent"] >= 60 and qa["match"]["because"] == "Because you liked Psych"
    assert {c["flag"] for c in qa["content_notes"]} == {"violence"}
    similar = [c["title"] for c in d["similar"]]
    assert {"Psych", "Lie to Me", "Monk", "Elementary"} & set(similar[:6])


def test_watch_in_india_google_link(client, guest, titles):
    h, _ = guest()
    r = client.get(f"/api/media/{titles['The Mentalist']}/watch-in-india", headers=h).json()
    assert r["google_url"] == "https://www.google.com/search?q=where+can+I+watch+The+Mentalist+in+India"
    client.patch("/api/users/me", headers=h, json={"subscription_providers": ["Netflix"]})
    sg = client.get(f"/api/media/{titles['Sacred Games']}/watch-in-india", headers=h).json()
    assert sg["on_your_services"] == ["Netflix"] and sg["providers"][0]["link"].startswith("https://www.netflix.com")


def test_liking_procedurals_skews_feed(client, guest, titles):
    """README §16 item 7: after liking crime procedurals, later cards measurably skew similar."""
    h, _ = guest()
    base = client.get("/api/feed?limit=12", headers=h).json()["cards"]
    base_crime = sum("Crime" in c["genres"] for c in base)
    for t in CRIME_PROCEDURALS:
        _swipe(client, h, titles[t], "watchlist")
    after = client.get("/api/feed?limit=12", headers=h).json()["cards"]
    after_crime = sum("Crime" in c["genres"] for c in after if not c["explore"])
    assert after_crime >= 8 and after_crime > base_crime
    keywords = {k for c in after[:6] for k in c["keywords"]}
    assert keywords & {"consultant", "detective", "police procedural", "case of the week"}


def test_undo_restores_previous_state(client, guest, titles):
    h, _ = guest()
    _swipe(client, h, titles["Coco"], "undecided")
    _swipe(client, h, titles["Coco"], "rejected")
    u = client.post("/api/swipe/undo", headers=h).json()
    assert u["restored_action"] == "undecided" and u["card"]["title"] == "Coco"
    assert [c["title"] for c in client.get("/api/lists/undecided", headers=h).json()["items"]] == ["Coco"]
    client.post("/api/swipe/undo", headers=h)
    assert client.get("/api/lists/undecided", headers=h).json()["items"] == []
    assert client.post("/api/swipe/undo", headers=h).status_code == 404


def test_idempotent_swipes(client, guest, titles):
    h, _ = guest()
    first = _swipe(client, h, titles["Up"], "watchlist", idempotency_key="key-123")
    again = _swipe(client, h, titles["Up"], "watchlist", idempotency_key="key-123")
    assert first["duplicate"] is False and again["duplicate"] is True
    assert client.get("/api/users/me/taste-summary", headers=h).json()["counts"]["swipes"] == 1


def test_content_filters_and_modes(client, guest, titles):
    h, _ = guest()
    client.patch("/api/users/me", headers=h, json={
        "content_filters": {"blocked_genres": ["Horror"], "blocked_flags": ["gore"], "max_certification": "UA"}})
    cards = client.get("/api/feed?limit=30", headers=h).json()["cards"]
    assert cards
    assert all("Horror" not in c["genres"] and "gore" not in c["content_flags"] for c in cards)
    assert all(c["certification"] in ("U", "UA") for c in cards)

    quick = client.get("/api/feed?limit=15&mode=quick", headers=h).json()["cards"]
    assert all((c["runtime_minutes"] or 999) <= (120 if c["type"] == "movie" else 35) for c in quick)
    hindi = client.get("/api/feed?limit=10&language=hi", headers=h).json()["cards"]
    assert hindi and all(c["language"] == "hi" for c in hindi)


def test_post_watch_rating_updates_taste(client, guest, titles):
    h, _ = guest()
    _swipe(client, h, titles["Whiplash"], "watchlist")
    r = client.patch(f"/api/lists/items/{titles['Whiplash']}", headers=h, json={"action": "watched", "rating": 5})
    assert r.status_code == 200
    watched = client.get("/api/lists/history?kind=watched", headers=h).json()["items"]
    assert watched[0]["rating"] == 5
    summary = client.get("/api/users/me/taste-summary", headers=h).json()
    assert summary["top_genres"][0]["name"] in ("Drama", "Music")


def test_tonight_pick_respects_time_budget(client, guest, titles):
    h, _ = guest()
    for t in ["Lagaan", "Primer", "Up"]:
        _swipe(client, h, titles[t], "watchlist")
    r = client.get("/api/picks/tonight?minutes=100", headers=h).json()
    assert r["pick"]["title"] in ("Primer", "Up") and r["source"] == "your Watch List"
    assert all(a["title"] != r["pick"]["title"] for a in r["alternates"])


def test_search_by_title_cast_and_keyword(client, guest):
    h, _ = guest()
    assert client.get("/api/media/search?q=mentalist", headers=h).json()["results"][0]["title"] == "The Mentalist"
    by_cast = [c["title"] for c in client.get("/api/media/search?q=Tabu", headers=h).json()["results"]]
    assert {"Andhadhun", "Drishyam"} <= set(by_cast)


def test_already_watched_teaches_taste_but_skips_watchlist(client, guest, titles):
    h, _ = guest()
    _swipe(client, h, titles["The Mentalist"], "watched")
    assert client.get("/api/lists/watchlist", headers=h).json()["watchlist"] == []
    watched = client.get("/api/lists/history?kind=watched", headers=h).json()["items"]
    assert [c["title"] for c in watched] == ["The Mentalist"] and watched[0]["rating"] is None
    feed = client.get("/api/feed?limit=10", headers=h).json()
    assert feed["cold_start"] is False, "a watched title counts as a positive signal"
    assert titles["The Mentalist"] not in {c["media_id"] for c in feed["cards"]}
    assert any(c["because"] == "Because you liked The Mentalist" for c in feed["cards"])
