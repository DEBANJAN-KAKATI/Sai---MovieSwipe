"""Phase 2+ relational features: accounts, duo/group sessions, friends, lists, parties, import/export."""

import io


def _swipe(client, h, media_id, action, session_id=None):
    r = client.post("/api/swipe", headers=h, json={"media_id": media_id, "action": action, "session_id": session_id})
    assert r.status_code == 200, r.text
    return r.json()


def test_guest_upgrade_and_login_keeps_history(client, guest, titles):
    h, user = guest("Kabir")
    _swipe(client, h, titles["RRR"], "must_visit")
    r = client.post("/api/auth/register", headers=h, json={"username": "kabir_k", "password": "popcorn-123",
                                                          "email": "kabir@example.com"})
    assert r.status_code == 200 and r.json()["user"]["user_id"] == user["user_id"]
    assert r.json()["user"]["is_guest"] is False
    bad = client.post("/api/auth/login", json={"login": "kabir_k", "password": "wrong-pass"})
    assert bad.status_code == 401
    ok = client.post("/api/auth/login", json={"login": "KABIR@example.com", "password": "popcorn-123"})
    h2 = {"Authorization": f"Bearer {ok.json()['token']}"}
    assert client.get("/api/lists/watchlist", headers=h2).json()["must_visit"][0]["title"] == "RRR"
    dup = client.post("/api/auth/register", json={"username": "kabir_k", "password": "another-123"})
    assert dup.status_code == 409


def test_duo_session_match(client, guest, titles):
    """README §16 item 8: two users swipe the same stack and get a match when both accept."""
    ha, _ = guest("A")
    hb, _ = guest("B")
    _swipe(client, ha, titles["The Office"], "liked")
    _swipe(client, hb, titles["Parks and Recreation"], "liked")

    s = client.post("/api/sessions", headers=ha, json={"mode": "duo"}).json()
    assert len(s["code"]) == 7 and s["required_votes"] == 2
    joined = client.post("/api/sessions/join", headers=hb, json={"code": s["code"].lower()}).json()
    assert len(joined["members"]) == 2
    third, _ = guest("C")
    assert client.post("/api/sessions/join", headers=third, json={"code": s["code"]}).status_code == 409

    stack_a = client.get(f"/api/sessions/{s['session_id']}/feed", headers=ha).json()["cards"]
    stack_b = client.get(f"/api/sessions/{s['session_id']}/feed", headers=hb).json()["cards"]
    assert [c["media_id"] for c in stack_a] == [c["media_id"] for c in stack_b], "both see the same stack"
    target = stack_a[0]["media_id"]

    first = _swipe(client, ha, target, "watchlist", s["session_id"])
    assert first["match"] is None
    second = _swipe(client, hb, target, "watchlist", s["session_id"])
    assert second["match"]["media"]["media_id"] == target
    assert sorted(second["match"]["participants"]) == ["A", "B"]

    state = client.get(f"/api/sessions/{s['session_id']}", headers=ha).json()
    assert len(state["matches"]) == 1
    assert any(x["session_id"] == s["session_id"] and x["match_count"] == 1
               for x in client.get("/api/sessions", headers=hb).json()["sessions"])
    # Session positives also land on personal watchlists.
    assert target in {c["media_id"] for c in client.get("/api/lists/watchlist", headers=hb).json()["watchlist"]}
    pick = client.get(f"/api/picks/tonight?session_id={s['session_id']}", headers=ha).json()
    assert pick["pick"]["media_id"] == target and pick["source"] == "session matches"


def test_group_session_with_demo_bots(client, guest):
    h, _ = guest("Host")
    s = client.post("/api/sessions", headers=h, json={"mode": "group", "min_votes": 2}).json()
    for _ in range(2):
        s = client.post(f"/api/sessions/{s['session_id']}/bot", headers=h).json()
    assert sum(m["is_bot"] for m in s["members"]) == 2 and s["required_votes"] == 2
    matches = 0
    for _ in range(3):
        cards = client.get(f"/api/sessions/{s['session_id']}/feed", headers=h).json()["cards"]
        for c in cards:
            if _swipe(client, h, c["media_id"], "watchlist", s["session_id"])["match"]:
                matches += 1
    assert matches > 0, "bots should agree on at least some titles"
    state = client.get(f"/api/sessions/{s['session_id']}", headers=h).json()
    assert all(m["swiped"] >= 10 for m in state["members"])


def test_friends_compatibility_and_recommendations(client, guest, titles):
    """README §16 item 9: user can send a title recommendation to a friend."""
    ha, a = guest("Isha")
    hb, b = guest("Vik")
    for t in ["Inception", "Interstellar", "Dune"]:
        _swipe(client, ha, titles[t], "liked")
    for t in ["Inception", "Arrival", "The Matrix"]:
        _swipe(client, hb, titles[t], "liked")

    req = client.post("/api/friends/request", headers=ha, json={"friend_code": b["friend_code"]}).json()
    assert req["status"] == "pending"
    incoming = client.get("/api/friends", headers=hb).json()["incoming"]
    client.post(f"/api/friends/{incoming[0]['friendship_id']}/accept", headers=hb)
    fl = client.get("/api/friends", headers=ha).json()["friends"]
    assert fl[0]["display_name"] == "Vik" and fl[0]["compatibility"] > 0 and fl[0]["shared_count"] == 1

    cmp = client.get(f"/api/friends/{b['user_id']}/compare", headers=ha).json()
    assert {c["title"] for c in cmp["shared"]} == {"Inception"}
    assert {"Arrival", "The Matrix"} <= {c["title"] for c in cmp["you_havent_seen"]}

    sent = client.post("/api/recommendations/send", headers=ha,
                       json={"to_user_id": b["user_id"], "media_id": titles["Dark"], "message": "Mind = blown"})
    assert sent.status_code == 200
    inbox = client.get("/api/recommendations/inbox", headers=hb).json()
    assert inbox["unseen"] == 1 and inbox["items"][0]["media"]["title"] == "Dark"
    client.post(f"/api/recommendations/{inbox['items'][0]['recommendation_id']}/respond", headers=hb,
                json={"action": "watchlist"})
    assert "Dark" in [c["title"] for c in client.get("/api/lists/watchlist", headers=hb).json()["watchlist"]]

    stranger, _ = guest("Nope")
    blocked = client.post("/api/recommendations/send", headers=stranger,
                          json={"to_user_id": b["user_id"], "media_id": titles["Dark"]})
    assert blocked.status_code == 403

    act = client.get("/api/social/activity", headers=ha).json()["items"]
    assert any(i["media"]["title"] == "Dark" for i in act)


def test_activity_never_leaks_rejects(client, guest, titles):
    ha, _ = guest()
    hb, _ = guest()
    client.post("/api/friends/demo", headers=ha)
    client.post("/api/friends/demo", headers=hb)
    _swipe(client, hb, titles["Hereditary"], "rejected")
    titles_seen = {i["media"]["title"] for i in client.get("/api/social/activity", headers=ha).json()["items"]}
    assert "Hereditary" not in titles_seen and "Se7en" not in titles_seen  # Meera rejected Se7en


def test_collaborative_and_public_lists(client, guest, titles):
    ha, _ = guest("Owner")
    hb, _ = guest("Editor")
    cl = client.post("/api/collab-lists", headers=ha, json={"name": "Weekend horror", "emoji": "🎃"}).json()
    joined = client.post("/api/collab-lists/join", headers=hb, json={"code": cl["invite_code"]}).json()
    assert joined["your_role"] == "editor"
    client.post(f"/api/collab-lists/{cl['list_id']}/items", headers=hb,
                json={"media_id": titles["Get Out"], "note": "classic"})
    assert client.get(f"/api/public/lists/{cl['list_id']}").status_code == 404
    client.patch(f"/api/collab-lists/{cl['list_id']}", headers=ha, json={"is_public": True})
    assert client.patch(f"/api/collab-lists/{cl['list_id']}", headers=hb, json={"name": "x"}).status_code == 403
    pub = client.get(f"/api/public/lists/{cl['list_id']}").json()
    assert pub["items"][0]["title"] == "Get Out" and pub["items"][0]["added_by"] == "Editor"
    assert "invite_code" not in pub


def test_watch_party_and_calendar(client, guest, titles):
    h, _ = guest("Party host")
    p = client.post("/api/parties", headers=h, json={"media_id": titles["Dune"],
                                                     "starts_at": "2026-12-24T20:00:00+05:30",
                                                     "notes": "Bring snacks; seats, limited"}).json()
    assert p["starts_at"] == "2026-12-24T14:30:00Z" and p["your_rsvp"] == "going"
    hg, _ = guest("Guest")
    assert client.post(f"/api/parties/{p['code']}/rsvp", headers=hg, json={"status": "maybe"}).status_code == 200
    ics = client.get(p["calendar_path"])
    body = ics.text
    assert ics.headers["content-type"].startswith("text/calendar")
    assert "DTSTART:20261224T143000Z" in body and "SUMMARY:Watch party: Dune" in body
    assert "Bring snacks\\; seats\\, limited" in body and "TRIGGER:-PT1H" in body


def test_letterboxd_import(client, guest):
    h, _ = guest()
    csv_text = ("Date,Name,Year,Letterboxd URI,Rating\n"
                "2024-01-01,The Mentalist,2008,x,4.5\n"
                "2024-01-02,Parasite,2019,x,5\n"
                "2024-01-03,The Hangover,2009,x,1.5\n"
                "2024-01-04,Some Obscure Film,1999,x,4\n")
    r = client.post("/api/import/letterboxd", headers=h,
                    files={"file": ("ratings.csv", io.BytesIO(csv_text.encode()), "text/csv")})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["matched"] == 3 and res["unmatched"] == ["Some Obscure Film"]
    assert res["added"] == {"liked": 2, "watchlist": 0, "watched": 0, "rejected": 1}
    bad = client.post("/api/import/letterboxd", headers=h, files={"file": ("x.csv", io.BytesIO(b"foo,bar\n1,2"))})
    assert bad.status_code == 422


def test_taste_summary_export_and_delete(client, guest, titles):
    h, _ = guest()
    for t in ["Panchayat", "Gullak", "3 Idiots"]:
        _swipe(client, h, titles[t], "watchlist")
    s = client.get("/api/users/me/taste-summary", headers=h).json()
    assert s["archetype"]["label"] == "Comfort Connoisseur"
    assert any(b["key"] == "first_swipe" and b["earned"] for b in s["badges"])
    assert s["streak"]["current"] == 1
    export = client.get("/api/users/me/export", headers=h)
    assert export.status_code == 200 and "Panchayat" in export.text
    assert client.delete("/api/users/me", headers=h).status_code == 200
    assert client.get("/api/users/me", headers=h).status_code == 401


def test_admin_metrics_requires_token(client):
    assert client.get("/api/admin/metrics").status_code == 404
    m = client.get("/api/admin/metrics", headers={"X-Admin-Token": "admin-test"}).json()
    assert m["catalog_size"] >= 150 and m["swipes_24h"] > 0


def test_websocket_rejects_non_members(client, guest):
    h, _ = guest()
    s = client.post("/api/sessions", headers=h, json={"mode": "duo"}).json()
    token = h["Authorization"].split()[1]
    with client.websocket_connect(f"/api/ws/sessions/{s['session_id']}?token={token}") as ws:
        ws.send_text("ping")
        assert ws.receive_json()["event"] == "pong"
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/ws/sessions/{s['session_id']}?token=bogus") as ws:
            ws.receive_text()


def test_unknown_api_path_is_404_not_spa(client):
    assert client.get("/api/does-not-exist").status_code == 404


def test_image_proxy_only_allows_known_hosts(client):
    assert client.get("/api/img", params={"url": "https://evil.example.com/x.jpg"}).status_code == 400
    assert client.get("/api/img", params={"url": "http://upload.wikimedia.org/x.jpg"}).status_code == 400
    assert client.get("/api/img", params={"url": "file:///etc/passwd"}).status_code == 400


def test_artwork_is_served_through_local_cache(client, guest, titles):
    from app.services.catalog import load_artwork

    if not load_artwork():
        return  # artwork.json not generated in this checkout
    h, _ = guest()
    d = client.get(f"/api/media/{titles['Inception']}", headers=h).json()
    assert d["poster_url"].startswith("/api/img?url=https%3A%2F%2Fupload.wikimedia.org")
    assert d["image_source"].startswith("https://en.wikipedia.org/wiki/")
    mentalist = client.get(f"/api/media/{titles['The Mentalist']}", headers=h).json()
    # TV shows get TVmaze posters plus a landscape background for the details header.
    assert mentalist["poster_url"].startswith("/api/img?url=https%3A%2F%2Fstatic.tvmaze.com")
    assert mentalist["backdrop_url"].startswith("/api/img?url=")
    assert mentalist["image_source"].startswith("https://www.tvmaze.com/shows/")


def test_watched_in_session_is_not_a_match_vote(client, guest, titles):
    ha, _ = guest("A")
    hb, _ = guest("B")
    s = client.post("/api/sessions", headers=ha, json={"mode": "duo"}).json()
    client.post("/api/sessions/join", headers=hb, json={"code": s["code"]})
    target = client.get(f"/api/sessions/{s['session_id']}/feed", headers=ha).json()["cards"][0]["media_id"]
    _swipe(client, ha, target, "watched", s["session_id"])
    assert _swipe(client, hb, target, "watchlist", s["session_id"])["match"] is None
    remaining = {c["media_id"] for c in client.get(f"/api/sessions/{s['session_id']}/feed", headers=ha).json()["cards"]}
    assert target not in remaining, "seen titles leave this member's stack"
    assert client.get("/api/lists/history?kind=watched", headers=ha).json()["items"][0]["media_id"] == target


def test_public_showcase_needs_no_login(client):
    r = client.get("/api/public/showcase")
    assert r.status_code == 200
    data = r.json()
    assert data["catalog_size"] >= 150 and data["language_count"] >= 5
    if data["posters"]:
        assert {p["type"] for p in data["posters"]} == {"movie", "tv"}
        assert all(p["poster_url"] for p in data["posters"])
