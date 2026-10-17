# sai (formerly MovieSwipe) — Complete Implementation Plan

> A Tinder-style discovery app for movies and TV. The feed learns from every swipe and surfaces titles that match taste and knowledge—e.g. after *The Mentalist*, expect neighbors like *Dexter*, *Hannibal*, *Lie to Me*, *Psych*, and *White Collar*.

**Document version:** 1.1  
**Last updated:** October 17, 2026  
**Status:** Implemented — Phases 0–2 complete, most of Phase 3 and parts of Phase 4 (see [Implementation status](#implementation-status))

---

## Implementation status

Everything below runs locally with **no Docker, no API keys and no model downloads**: SQLite by default, a bundled
166-title catalog (Hollywood + Indian cinema/series across 10 languages) and a hashed TF-IDF embedding. Add a TMDB key
to get real posters, trailers, live India watch providers and an unlimited catalog.

### What's built

| Area | Delivered |
|------|-----------|
| **Swipe deck** | All six gestures with spring physics: right = Watch List, left = Not for me, down = Maybe Later, up = Where to watch (intent only, card stays), **long-press 450 ms with progress ring** = Must Visit, tap = Q&A panel. **✓ button = Already watched** (taste signal → History, never the Watch List). Every gesture duplicated by buttons and keyboard (← → ↑ ↓ S W Space Z). Undo. |
| **Lists** | Itinerary (Must Visit pinned, then Watch List; sort by added / match / shortest / newest / A–Z, total queued runtime), Maybe Later (re-surfaces after cooldown), History (watched + ★ rating, loved, rejected with rescue). |
| **Q&A panel** | About (spoiler shield), format & runtime, cast & creator, trailer (embed or YouTube search), match % + "Because you liked X", content notes & certification, where to watch in India, similar titles. |
| **Recommender** | §7 formula: embedding similarity to liked/rejected centroids, genre/keyword/people affinity, language, freshness, subscription boost, friends' boost, stable exploration noise; time-decayed taste (14-day half-life); cold-start blend 0 → 70 → 90 % personal; 12 % exploration slot; diversity re-ranking; explainability on every card. |
| **Modes** | For you · Quick pick · Mood (8 moods) · Decompress · New releases, plus type and language filters. |
| **Duo / Group** | 7-char codes (~35 bits), QR + share link, blended stack ranked by **harmonic mean** of member fit, watchlist overlap boost, matches at 2 / K / unanimous votes, super-match when all super-save, live WebSocket updates (+ polling fallback), match celebration, session history. |
| **Social** | Friend codes, requests, block, **compatibility %** (Jaccard + centroid cosine), side-by-side compare, recommend-to-friend inbox with one-tap accept, privacy-safe friends' activity (never exposes rejects). |
| **Collaborative lists** | Owner / editor / viewer roles, invite codes, notes, public read-only share page. |
| **Watch parties** | Schedule from any title or match, RSVP, `.ics` export with 1-hour reminder. |
| **Profile** | Guest-first accounts (upgrade keeps history), login, subscriptions, languages, content filters (genres, flags, max certification), spoiler shield, privacy, Letterboxd / IMDb CSV import, JSON export, account deletion. |
| **Ops** | Rate limiting, idempotent swipes, scrypt password hashing, JWT, `/api/admin/metrics` (DAU, accept rate, watch-link CTR, session match rate), OpenAPI docs at `/docs`. |

### Extra features (beyond the original plan)

- **🎲 Decide for me / Tonight's Pick** — "I have 90 minutes and feel cozy": picks from your Watch List (or a session's matches), weighting Must Visit, runtime fit and mood, with a slot-machine reveal and runners-up.
- **🙈 Blind date mode** — cards hide poster and title; you judge on the logline alone, and the title is revealed after you swipe.
- **🧬 Taste DNA** — an archetype ("Case Cracker", "Comfort Connoisseur"…), genre bars, theme cloud, language/era mix, say-yes rate, streaks and 12 badges with progress.
- **🤖 Demo personas** — Aanya (whodunits), Rohan (sci-fi) and Meera (comfort comedy) can join sessions as bots or be added as friends, so every social feature can be tried solo.
- **Time-budget aware** list sorting and runtime totals; **guest-first onboarding** with search-to-seed ("pick shows you love").
- **Single-process deploy** — FastAPI serves the built PWA, so one `uvicorn` command runs the whole app.

### Deviations from the plan (and why)

- **SQLite** by default instead of Postgres so it runs anywhere; Postgres works via `DATABASE_URL` (`backend[postgres]` extra, or `docker compose`). The schema is managed by Alembic (`backend/migrations`) and upgraded automatically on startup.
- **Embeddings:** hashed TF-IDF over genres/keywords/people/overview (384-dim, no download) with candidate scoring in Python instead of pgvector ANN — fine at catalog sizes in the low thousands. `EMBEDDING_BACKEND=sbert` swaps in MiniLM.
- **No Redis/Celery:** feed caching is in-process; WebSocket fan-out is single-process.
- **Passwords:** scrypt (stdlib) rather than Argon2 — equivalent memory-hard KDF, no native dependency.
- **Group session rejects** don't touch personal lists ("not tonight" ≠ "never"); positives do.
- The bundled catalog's ratings and maturity labels are approximate; real values come from TMDB when a key is set.

Not yet built: collaborative filtering, LLM natural-language search, kid profiles with PIN, push/email notifications,
weekly digest, offline PWA queue, leaving-soon alerts.

---

## Table of contents

1. [Product vision](#1-product-vision)
2. [Core interactions](#2-core-interactions)
3. [Relational & social features](#3-relational--social-features)
4. [Advanced features](#4-advanced-features)
5. [System architecture](#5-system-architecture)
6. [Data model](#6-data-model)
7. [Recommendation engine](#7-recommendation-engine)
8. [API design](#8-api-design)
9. [Client application](#9-client-application)
10. [Integrations & compliance](#10-integrations--compliance)
11. [Security & privacy](#11-security--privacy)
12. [Phased roadmap](#12-phased-roadmap)
13. [Project structure](#13-project-structure)
14. [Metrics & experimentation](#14-metrics--experimentation)
15. [Risks & mitigations](#15-risks--mitigations)
16. [MVP definition of done](#16-mvp-definition-of-done)
17. [Appendix](#17-appendix)
- [Implementation status](#implementation-status) · [Quick start](#quick-start)

---

## 1. Product vision

### 1.1 Problem

Choice overload on streaming platforms; generic “top 10” lists ignore personal taste; couples and friend groups rarely agree on one title without friction.

### 1.2 Solution

**MovieSwipe** combines:

- **Fast binary discovery** (swipe deck) with rich actions (undecided, super-save, watch-now).
- **Personalized ranking** from explicit signals and semantic similarity (genres, keywords, embeddings).
- **Relational layers** so taste connects to people: shared lists, match scores, group picks, and social proof—not a solo silo.

### 1.3 Primary personas

| Persona | Need |
|---------|------|
| Solo binge planner | Build a smart watchlist and find where to stream in India |
| Couple / roommates | “What do we both actually want tonight?” |
| Friend group | Poll-less group session: everyone swipes, app surfaces overlap |
| Curator | Share public lists; followers get a slice of their feed |
| Power user | Mood modes, filters, import from Letterboxd/Trakt, AI explainability |

### 1.4 Non-goals (v1)

- Hosting or pirating video streams (links only).
- Full social network (no generic feed of posts in MVP).
- Replacing Letterboxd/IMDb for long-form reviews (light ratings optional later).

---

## 2. Core interactions

### 2.1 Gesture & action map

| Gesture | Action | User-facing label | Backend `action` | Signal strength |
|---------|--------|-------------------|------------------|-----------------|
| Swipe right | Accept | Watch List | `watchlist` | Strong positive |
| Swipe left | Reject | Not for me | `rejected` | Strong negative |
| Swipe up / tap center | Watch now | Where to watch (India) | `watch_intent` (optional log) | Intent (no list change) |
| Swipe down | Park | Maybe Later | `undecided` | Weak positive |
| Tap card | Info | Flip → Q&A panel | `impression_detail` | Engagement |
| Long press | Pin | Must Visit | `must_visit` | Strongest positive |

### 2.2 Lists & itinerary UX

- **Itinerary (Watch List):** `must_visit` pinned at top, then `watchlist`, sortable by date added, rating preview, or “shortest runtime first.”
- **Undecided:** Separate pile; items can be promoted to watchlist, rejected, or re-entered into deck after cooldown.
- **History:** Rejected and watched (optional) for transparency and “undo bias.”

### 2.3 Info panel (card flip) — practical Q&A

| Question | Source |
|----------|--------|
| What is it about? | TMDB overview (truncated + “read more”) |
| Movie or series? How long? | Runtime / season count |
| Who’s in it? | Top cast |
| Trailer | TMDB videos → YouTube embed |
| Similar to things I like? | Internal rec engine + “Because you liked *X*” |
| Content notes | Keywords + user filters (violence, etc.) |
| Where can I watch in India? | Google deep link (MVP) → TMDB/JustWatch providers (v2) |

### 2.4 Where to watch (India) — MVP

```
https://www.google.com/search?q=where+can+I+watch+{URL_ENCODED_TITLE}+in+India
```

Optional query params for app attribution. Phase 2: structured providers with deep links to Netflix, Prime, JioCinema, etc., filtered by user’s declared subscriptions.

---

## 3. Relational & social features

Relational features turn MovieSwipe from a personal recommender into a **shared decision and taste graph**.

### 3.1 Connections & profiles

| Feature | Description | Phase |
|---------|-------------|-------|
| **Follow / friend** | Bidirectional (friends) or one-way (follow curators) | 2 |
| **Public taste profile** | Optional: top genres, favorite titles, “currently swiping” stat | 2 |
| **Privacy tiers** | Public / friends-only / private lists and activity | 2 |
| **Block & report** | Standard safety | 2 |

### 3.2 Shared lists & collaboration

| Feature | Description | Phase |
|---------|-------------|-------|
| **Collaborative watchlist** | Invite link; multiple editors; roles: owner, editor, viewer | 2 |
| **List templates** | “Weekend horror,” “Marvel order,” “Partner picks” | 3 |
| **Comments on list items** | “You have to see this”—thread per title | 3 |
| **Version history** | Who added/removed what (audit log) | 3 |

### 3.3 Match & overlap (Tinder-for-movies with friends)

| Feature | Description | Phase |
|---------|-------------|-------|
| **Duo Session** | Two users swipe the same stack; **Match** when both right-swipe or both super-save | 2 |
| **Group Session** | N users; show titles with ≥K approvals (K configurable: unanimous, majority, any 2) | 3 |
| **Session lobby** | QR / 6-digit code; time-boxed (e.g. 15 min) | 2 |
| **Match celebration UI** | Poster stack reveal; one-tap “where to watch” for matched title | 2 |
| **Overlap score** | Persistent **compatibility %** between two users based on Jaccard + embedding similarity of shared likes | 3 |

**Duo session flow (conceptual)**

```mermaid
sequenceDiagram
  participant A as User A
  participant B as User B
  participant S as Session Service
  participant F as Feed Service
  A->>S: Create duo session
  S->>B: Invite code
  A->>F: Request duo stack (blend both tastes)
  B->>F: Same stack
  A->>S: Swipe right on title T
  B->>S: Swipe right on title T
  S->>A: Match notification
  S->>B: Match notification
```

**Duo feed blending:** Intersect candidate pools from both taste profiles, rank by `min(score_A, score_B)` or harmonic mean to favor **mutual** appeal, not only one-sided taste.

### 3.4 Social discovery

| Feature | Description | Phase |
|---------|-------------|-------|
| **Friends’ activity (privacy-safe)** | “3 friends added *Dune* this week”—aggregated, no leak of rejects | 3 |
| **Recommend to friend** | Send title card in-app; friend gets pre-filled detail + one-swipe accept | 2 |
| **Shared “Must Visit”** | Couple’s pinned queue | 2 |
| **Curator mode** | Public list drives a **follower feed slice** (e.g. 20% of deck from followed curators’ recent adds) | 4 |

### 3.5 Invites & growth (relational)

- Referral codes tied to **bonus exploration packs** (genre packs unlocked).
- **Watch party RSVP:** relational event attached to a matched or list title (see Advanced → Watch party).

### 3.6 Notifications (relational)

- Match in duo session.
- Friend recommended a title.
- Collaborative list updated.
- Group session starting (push / email).

---

## 4. Advanced features

### 4.1 Intelligence & personalization

| Feature | Description | Phase |
|---------|-------------|-------|
| **Embedding retrieval (pgvector)** | Semantic neighbors beyond genre tags | 2 |
| **Collaborative filtering** | “Users with similar swipe patterns liked…” | 3 |
| **Multi-interest vectors** | Separate centroids: “crime procedural” vs “comfort comedy”—route by **mode** | 3 |
| **Temporal taste** | Weekday short episodes vs weekend films; time-of-day boosts | 3 |
| **Negative space** | Hard exclude genres/actors; “never show horror” | 2 |
| **Rejection cooldown** | Rejected titles decay back into low-priority exploration | 2 |
| **Explainability** | Every card: “87% match — procedural, consultant lead, 2000s” + seed title | 2 |
| **LLM assistant (optional)** | Natural language: “something like Mentalist but lighter”; converts to embedding + filters | 4 |
| **Import taste** | Letterboxd CSV, Trakt, IMDb list → bootstrap centroid | 3 |
| **Post-watch feedback** | After marked watched: 1–5 stars updates ranker (implicit quality signal) | 3 |

### 4.2 Context & session modes

| Mode | Behavior |
|------|----------|
| **Solo discover** | Default personalized deck |
| **Quick pick** | Only movies &lt; 2h or single episodes |
| **Duo / Group** | Blended or intersection feed |
| **Mood** | User picks mood chip → reweights genres/keywords (e.g. “cozy,” “intense,” “mind-bend”) |
| **Decompress** | Downrank violent/distressing via keyword filters |
| **New releases** | Boost recent TMDB releases in taste neighborhood |

### 4.3 Streaming & availability intelligence

| Feature | Description | Phase |
|---------|-------------|-------|
| **My subscriptions** | User selects services available in India | 2 |
| **Availability badge** | On card: “On your Netflix” vs “Rent only” | 3 |
| **Leave alerts** | “Leaving Prime in 7 days” (provider APIs / third-party) | 4 |
| **Price-aware rent** | Show rent price when no subscription match | 4 |

### 4.4 Watch party & calendar

| Feature | Description | Phase |
|---------|-------------|-------|
| **Schedule watch party** | Pick matched/list title; datetime; invite link | 3 |
| **Calendar export** | .ics for Google Calendar | 3 |
| **Countdown & reminders** | Push notification 1h before | 3 |
| **Sync start (future)** | Integrate Teleparty-style sync (partner API or extension—not in core MVP) | 5 |

### 4.5 Content safety & household

| Feature | Description | Phase |
|---------|-------------|-------|
| **Content filters** | Violence, sexual content, substance—map from TMDB keywords/certifications | 2 |
| **Kid profile** | Separate taste + stricter filters + PIN | 4 |
| **Spoiler shield** | Hide overview beyond logline until watched | 3 |

### 4.6 Gamification & retention (light)

| Feature | Description | Phase |
|---------|-------------|-------|
| **Streaks** | Daily swipe or daily match with partner | 3 |
| **Badges** | “Procedural explorer,” “100 matches” | 4 |
| **Weekly digest** | Email: top 5 you might have missed | 3 |

### 4.7 Power-user & platform

| Feature | Description | Phase |
|---------|-------------|-------|
| **PWA offline** | Queue swipes; cache next cards | 3 |
| **Widgets** | “Next up from Must Visit” (mobile) | 4 |
| **Voice search** | “Find me a heist movie” → search + deck injection | 4 |
| **API keys for devs** | Read-only public lists (curators) | 5 |
| **Admin dashboard** | DAU, accept rate, session match rate, TMDB sync health | 3 |

### 4.8 Advanced relational + ML

| Feature | Description | Phase |
|---------|-------------|-------|
| **Graph-based recs** | Edges: friend liked → small boost if you trust friend’s overlap score | 4 |
| **Trust-weighted social** | Close friends weigh more than acquaintances | 4 |
| **Session outcome learning** | If duo always picks comedy after 9pm, boost comedy in late duo stacks | 4 |

---

## 5. System architecture

### 5.1 Component diagram

```mermaid
flowchart TB
  subgraph clients [Clients]
    Web[PWA / React]
    Mobile[Flutter or RN - optional]
  end

  subgraph gateway [Edge]
    CDN[CDN - posters]
    WAF[Rate limit / WAF]
  end

  subgraph services [Backend Services]
    API[FastAPI Gateway]
    Auth[Auth Service]
    Feed[Feed Service]
    Swipe[Swipe Ingest]
    Rec[Recommendation Engine]
    Social[Social / Sessions]
    Notify[Notification Worker]
    Media[Media Catalog Sync]
  end

  subgraph data [Data]
    PG[(PostgreSQL)]
    Vec[(pgvector)]
    Redis[(Redis)]
    S3[Object storage - exports]
  end

  subgraph external [External]
    TMDB[TMDB API]
    Push[FCM / APNs]
    Email[SendGrid / SES]
    LLM[Optional LLM API]
  end

  Web --> WAF --> API
  Mobile --> WAF
  API --> Auth
  API --> Feed
  API --> Swipe
  API --> Social
  Feed --> Rec
  Swipe --> Rec
  Rec --> Vec
  Rec --> PG
  Social --> PG
  Media --> TMDB
  Media --> PG
  Feed --> Redis
  Notify --> Push
  Notify --> Email
```

### 5.2 Recommended technology stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| API | **Python 3.12 + FastAPI** | Matches repo; async; OpenAPI |
| ORM | SQLAlchemy 2.0 + Alembic | Migrations |
| DB | **PostgreSQL 16** | Relational + JSONB |
| Vectors | **pgvector** | Co-locate vectors with metadata |
| Cache | Redis | Feed queues, session state, rate limits |
| Jobs | Celery + Redis or **ARQ** | Embeddings, TMDB sync, digests |
| Search (optional) | Meilisearch / Postgres FTS | Title search |
| Frontend | **React + Vite + TypeScript** | PWA, gesture libraries |
| Mobile (optional) | Flutter | Smooth gestures, single codebase |
| Auth | Supabase Auth / Clerk / custom JWT | Social login phase 2 |
| Infra | Docker Compose → Fly.io / Railway / AWS | Start simple |

### 5.3 Event-driven swipe pipeline

1. Client POST `/swipe` → validate idempotency key.
2. Write `user_media_actions` + emit `SwipeRecorded` event.
3. Update taste profile (sync or async).
4. Invalidate user feed cache in Redis.
5. Pre-warm next N cards in background worker.
6. If duo session: check match condition → emit `MatchCreated` → notify.

---

## 6. Data model

### 6.1 Core catalog

**`media_items`**

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tmdb_id | int | unique per type |
| type | enum | movie, tv |
| title | text | |
| original_title | text | |
| overview | text | |
| release_date | date | |
| genres | jsonb | id + name |
| keywords | jsonb | |
| cast | jsonb | top 10 |
| runtime_minutes | int | nullable for TV |
| season_count | int | TV |
| poster_path | text | TMDB path |
| embedding | vector(384) | nullable until backfill |
| popularity | float | TMDB |
| updated_at | timestamptz | |

**`media_availability_in`** (phase 3)

| Column | Type |
|--------|------|
| media_id | FK |
| provider_id | int |
| type | flatrate / rent / buy |
| link | text |
| last_checked | timestamptz |

### 6.2 User & taste

**`users`**

| Column | Type |
|--------|------|
| id | UUID |
| email | text |
| display_name | text |
| region | char(2) default `IN` |
| subscription_providers | jsonb |
| privacy_settings | jsonb |
| created_at | timestamptz |

**`user_media_actions`**

| Column | Type |
|--------|------|
| user_id | FK |
| media_id | FK |
| action | enum |
| session_id | UUID nullable (duo/group) |
| created_at | timestamptz |

Unique: `(user_id, media_id)` — latest action wins or use soft history table.

**`user_taste_snapshots`** (optional audit)

Daily JSON snapshot of genre weights and centroid hash for debugging.

**`user_content_filters`**

| Column | Type |
|--------|------|
| user_id | FK |
| blocked_genre_ids | int[] |
| blocked_keyword_ids | int[] |
| max_certification | text |

### 6.3 Relational

**`friendships`**

| Column | Type |
|--------|------|
| user_a, user_b | FK |
| status | pending / accepted / blocked |
| created_at | timestamptz |

**`collaborative_lists`**

| Column | Type |
|--------|------|
| id | UUID |
| name | text |
| owner_id | FK |
| is_public | bool |

**`list_members`**

| list_id, user_id | role: owner / editor / viewer |

**`list_items`**

| list_id, media_id, added_by, priority, note |

**`duo_sessions` / `group_sessions`**

| Column | Type |
|--------|------|
| id | UUID |
| code | text |
| host_id | FK |
| mode | duo / group |
| min_votes | int (group) |
| expires_at | timestamptz |
| feed_seed | text | reproducible stack |

**`session_swipes`**

| session_id, user_id, media_id, action, created_at |

**`matches`**

| session_id, media_id, matched_at, participants jsonb |

**`recommendations_to_user`**

| from_user_id, to_user_id, media_id, message, seen_at |

### 6.4 Feed & analytics

**`feed_impressions`**

| user_id, media_id, rank, shown_at, acted_at |

**`experiments`**

| user_id, experiment_key, variant |

---

## 7. Recommendation engine

### 7.1 Example: *The Mentalist* neighborhood

Mechanisms combining:

1. **Keywords:** consultant, police procedural, FBI, detective, psychological.
2. **Embedding similarity** on overview + keywords.
3. **TMDB similar** as cold backup.
4. **Optional curated adjacency** JSON for onboarding demos.

Expected neighbors: *Psych*, *Lie to Me*, *White Collar*, *Dexter*, *Hannibal*, *Castle*, *Elementary*, *Broadchurch* (stretch genre).

### 7.2 Taste representation

- **Genre vector:** EMA weights from accepts/rejects.
- **Keyword vector:** Same, with higher weight for super-save.
- **Embedding centroid:** Mean of liked + must_visit embeddings, minus rejected (weighted).
- **Multi-centroid (advanced):** Cluster likes into 3–5 taste clusters (k-means on liked embeddings); pick cluster by mood mode or time.

### 7.3 Candidate generation

1. Filter out: already acted, hard blocked genres, rejected within cooldown.
2. Retrieve top K=500 from pgvector ANN index.
3. Union TMDB similar for last 3 accepts (cap 50).
4. Inject exploration: 10–15% from trending or random genre.

### 7.4 Ranking formula

```
score(u, i) =
    w1 * cos_sim(E_i, C_u)
  + w2 * genre_affinity(u, i)
  + w3 * keyword_affinity(u, i)
  - w4 * cos_sim(E_i, R_u)
  + w5 * freshness(i)
  + w6 * availability_boost(i)   # if on user's subscriptions
  + w7 * social_boost(i)         # friends liked (phase 4)
  + w8 * exploration_noise
```

**Duo ranking:** use `score_duo = harmonic_mean(score_A, score_B)` or prioritize titles above threshold for both.

### 7.5 Online update (after swipe)

| Action | Update |
|--------|--------|
| watchlist | +genre/keyword; move centroid toward embedding |
| must_visit | 2× weight vs watchlist |
| undecided | +0.3× positive |
| rejected | +negative centroid; cooldown list |
| watch_intent | +intent feature for “ready to watch soon” re-rank |

Half-life for weights: ~14 days (configurable).

### 7.6 Cold start

1. Pick 8–12 poster tiles (multi-genre).
2. Optional: “Pick 3 shows you love” typeahead search.
3. Initial centroid = mean(selected embeddings).
4. Mix 70% personalized / 30% trending until 20 swipes, then 90/10 exploration.

### 7.7 Model ops

- Batch job: embed new TMDB items nightly.
- Monitor: embedding drift, accept rate by cohort.
- A/B: `w1`–`w8` via experiment service.

---

## 8. API design

### 8.1 REST (MVP + extensions)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register`, `/auth/login` | Phase 2 |
| GET | `/feed` | Query: `limit`, `mode=solo|duo|mood`, `mood=`, `session_id=` |
| POST | `/swipe` | Body: `media_id`, `action`, `idempotency_key`, `session_id?` |
| GET | `/lists/watchlist` | Must Visit first |
| GET | `/lists/undecided` | |
| PATCH | `/lists/items/{media_id}` | Promote, demote, remove |
| GET | `/media/{id}` | Detail for flip panel |
| GET | `/media/{id}/similar` | |
| GET | `/media/{id}/watch-in-india` | Returns Google URL + later providers[] |
| POST | `/onboarding/taste` | Poster picks + loved titles |
| POST | `/sessions/duo` | Create session → `{ code, session_id }` |
| POST | `/sessions/join` | `{ code }` |
| GET | `/sessions/{id}/matches` | |
| POST | `/friends/request` | |
| GET | `/friends` | |
| POST | `/recommendations/send` | Recommend title to friend |
| GET | `/users/me/taste-summary` | Explainability snapshot |
| POST | `/import/letterboxd` | CSV upload phase 3 |

### 8.2 WebSocket (phase 2+)

| Event | Direction |
|-------|-----------|
| `session.user_joined` | Server → clients |
| `session.swipe` | Optional obfuscated progress |
| `session.match` | Server → clients with media payload |

---

## 9. Client application

### 9.1 Key screens

1. **Onboarding** — region (India default), subscriptions, taste picker, content filters.
2. **Discover** — swipe deck + mode switcher (Solo / Duo / Mood).
3. **Itinerary** — Must Visit + Watch List.
4. **Undecided** — parked cards.
5. **Matches** — duo/group history.
6. **Social** — friends, invites, shared lists.
7. **Profile** — filters, subscriptions, privacy, import.

### 9.2 Gesture implementation notes

- Use spring physics; show icons (✅❌🔖🗺️⭐) during drag.
- **Conflict resolution:** swipe up opens watch; tap center opens flip; distinguish by distance threshold.
- Long press delay ~400ms with progress ring.
- Accessibility: buttons duplicate every gesture.

### 9.3 Libraries (web)

- `@use-gesture/react` or `react-swipeable`
- `framer-motion` for card stack
- TanStack Query for feed cache
- Zustand for session + duo state

---

## 10. Integrations & compliance

| Integration | Use | Notes |
|-------------|-----|-------|
| TMDB | Metadata, images, videos, keywords, watch providers | API key; attribution in UI |
| Google Search | Watch in India MVP | No scraping |
| JustWatch / TMDB providers | Structured availability | Region IN |
| YouTube | Trailers | Embed policy |
| FCM / Web Push | Notifications | |
| Optional LLM | NL queries | Rate limit; no PII in prompts |

**Attribution:** Display TMDB logo and disclaimer per their terms.

---

## 11. Security & privacy

- Hash passwords (Argon2); OAuth phase 2.
- Rate limit swipe and session join by IP + user.
- Duo codes: short-lived, entropy ≥ 32 bits.
- **Privacy:** Never expose friend’s rejects; aggregate activity only.
- GDPR-style export/delete account (phase 3).
- Idempotent swipes to prevent double-counting.
- Sanitize all TMDB text before rendering (XSS).

---

## 12. Phased roadmap

### Phase 0 — Foundation (week 1–2)

- [ ] Monorepo, Docker Compose (Postgres, Redis, API)
- [ ] TMDB sync script → `media_items`
- [ ] Basic GET `/feed` (trending only)
- [ ] POST `/swipe` persistence
- [ ] Minimal React deck (right/left only)

### Phase 1 — MVP solo (week 3–5)

- [ ] All six gestures + three lists
- [ ] Rule-based taste (genre/keyword EMA)
- [ ] Onboarding poster picker
- [ ] Flip panel Q&A
- [ ] Google “watch in India” link
- [ ] Content filters (basic)
- [ ] Undo last swipe

### Phase 2 — Smart solo + duo (week 6–9)

- [ ] pgvector embeddings + retrieval
- [ ] Explainability strings
- [ ] Subscriptions profile + badge stub
- [ ] Auth + user accounts
- [ ] **Duo session** + match notifications
- [ ] Recommend to friend
- [ ] Collaborative list (basic)

### Phase 3 — Group & availability (week 10–14)

- [ ] Group session + vote thresholds
- [ ] Overlap / compatibility score
- [ ] TMDB watch providers for IN
- [ ] Watch party + calendar .ics
- [ ] Post-watch ratings
- [ ] Letterboxd import
- [ ] Mood modes + multi-centroid (basic)
- [ ] Admin metrics dashboard

### Phase 4 — Advanced (week 15+)

- [ ] Collaborative filtering
- [ ] LLM natural language discover
- [ ] Social boost in ranker
- [ ] Weekly digest email
- [ ] Spoiler shield
- [ ] Kid profile
- [ ] PWA offline queue

### Phase 5 — Platform (optional)

- [ ] Native app (Flutter)
- [ ] Teleparty-style sync partner
- [ ] Public API for curators
- [ ] Leaving-soon alerts

---

## 13. Project structure

```
MovieSwipe/
├── README.md                 # This document
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── feed.py
│   │   │   ├── swipe.py
│   │   │   ├── lists.py
│   │   │   ├── media.py
│   │   │   ├── sessions.py
│   │   │   └── social.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── tmdb.py
│   │   │   ├── taste.py
│   │   │   └── watch_links.py
│   │   └── recs/
│   │       ├── embed.py
│   │       ├── retrieve.py
│   │       └── rank.py
│   ├── scripts/
│   │   ├── sync_tmdb.py
│   │   └── backfill_embeddings.py
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── components/
│       │   ├── SwipeDeck.tsx
│       │   ├── MediaCard.tsx
│       │   ├── InfoPanel.tsx
│       │   └── SessionLobby.tsx
│       ├── pages/
│       └── api/
└── docs/
    ├── API.md
    └── RECSYS.md
```

---

## 14. Metrics & experimentation

| Metric | Definition | Target (indicative) |
|--------|------------|---------------------|
| D1 retention | Return next day | &gt; 30% early beta |
| Swipes / session | Engagement depth | 15+ |
| Accept rate | Rights / impressions | 12–25% (genre dependent) |
| Duo match rate | Matches / duo sessions | Track uplift vs random |
| Time to first match | Session start → first match | &lt; 5 min |
| Watch link CTR | Clicks / impressions | Product intent signal |
| Diversity | Genre entropy per 20 cards | Avoid &lt; threshold |
| Latency p95 | `/feed` | &lt; 300 ms cached |

**Experiments:** exploration %, duo harmonic vs min score, explainability on/off, subscription badge on/off.

---

## 15. Risks & mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Filter bubble | Boring feed | Exploration slot + mood diversity |
| Empty duo stack | No matches | Lower K threshold; widen blend |
| TMDB rate limits | Sync fails | Cache; incremental sync |
| Bad availability data | User frustration | Disclaimer; multi-source phase 3 |
| Gesture overlap UX | Mis-swipes | Tutorial; adjustable sensitivity |
| Social privacy leaks | Trust loss | Strict aggregation; audit APIs |
| LLM cost / hallucination | Wrong titles | Ground to TMDB search only |

---

## 16. MVP definition of done

**Solo MVP (Phase 1) is done when:**

1. User onboards with taste picks and sees a non-empty personalized deck.
2. All six interactions work and persist to correct lists.
3. Must Visit appears pinned on itinerary.
4. Undecided re-surfaces per cooldown rules.
5. Flip panel answers core Q&A and shows similar titles.
6. “Watch in India” opens correct Google search for the title.
7. After liking a crime procedural, subsequent cards measurably skew similar (QA test script or manual test checklist).

**Relational MVP (Phase 2) add-on:**

8. Two authenticated users complete a duo session and receive at least one match notification when both accept the same title.
9. User can send a title recommendation to a friend.

---

## 17. Appendix

### 17.1 Environment variables (`.env.example`)

```env
DATABASE_URL=postgresql+asyncpg://movieswipe:movieswipe@localhost:5432/movieswipe
REDIS_URL=redis://localhost:6379/0
TMDB_API_KEY=
JWT_SECRET=
APP_REGION_DEFAULT=IN
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### 17.2 Sample swipe request

```json
POST /swipe
{
  "media_id": "550e8400-e29b-41d4-a716-446655440000",
  "action": "watchlist",
  "idempotency_key": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "session_id": null
}
```

### 17.3 Sample feed response (abbreviated)

```json
{
  "cards": [
    {
      "media_id": "...",
      "title": "Psych",
      "type": "tv",
      "year": 2006,
      "poster_url": "https://image.tmdb.org/t/p/w500/...",
      "match_percent": 89,
      "because": "Because you liked The Mentalist",
      "badges": ["crime", "comedy"]
    }
  ],
  "cursor": "next-page-token"
}
```

### 17.4 Legal & product disclaimers (ship text)

- Streaming availability varies; verify on the provider’s site.
- MovieSwipe does not host video content.
- TMDB data attribution required.

---

## Quick start

Requires Python 3.11+ and Node 18+.

```bash
# Backend (from the project root)
python -m venv .venv
.venv/Scripts/activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -e "backend[dev]"
uvicorn app.main:app --app-dir backend --reload --port 8000
```

```bash
# Frontend (second terminal) — dev server with hot reload, proxies /api to :8000
cd frontend
npm install
npm run dev
```

Open http://localhost:5175. On startup the API runs the database migrations (`alembic upgrade head`) and seeds
the bundled catalog, so a fresh SQLite file at `backend/movieswipe.db` is ready with no extra steps. A database
created by an older build (before migrations) is adopted automatically at the initial revision.

**Live testing on your phone:** start the backend with `--host 0.0.0.0` (see *Android app* below), run `npm run dev`,
and open `http://<your-PC-IP>:5175` (e.g. http://192.168.0.9:5175) in the phone's browser on the same Wi-Fi. Every code
change appears on the phone instantly — nothing to install. When you're happy, run `npm run apk` to bake the changes
into the APK.

**Single process:** `npm run build` in `frontend/`, then the API at http://localhost:8000 serves the app too.

**Postgres without Docker:** `pip install -e "backend[postgres]"` and set
`DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/movieswipe` in `.env`.

**Migrations** (Alembic, run from `backend/`; the URL comes from `DATABASE_URL`/`.env`, SQLite by default):

```bash
cd backend
alembic upgrade head                                  # what startup does
alembic revision --autogenerate -m "add foo column"   # after changing app/models.py; review the file in migrations/versions/
alembic check                                         # fails if models and migrations have drifted
```

### Docker

The `Dockerfile` builds the frontend (Node 22) and runs uvicorn on Python 3.12, serving `frontend/dist` and `/api`
from one container on port 8000. `docker-compose.yml` adds a Postgres 16 service (data in the `pgdata` volume);
the app waits for it to be healthy, then migrates and seeds it on startup.

```bash
# .env in the project root (Compose reads it); JWT_SECRET is required
echo "JWT_SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" >> .env
docker compose up --build
```

Open http://localhost:8000. Other `.env` settings (`TMDB_API_KEY`, `ADMIN_TOKEN`, …) are passed through;
`DATABASE_URL` is always set by Compose. Optional: `POSTGRES_PASSWORD` (default `movieswipe`, must be URL-safe)
and `APP_PORT` (default 8000). Needs Docker Compose v2.24+ (optional `env_file`).

Without Compose the image uses SQLite in its `/data` volume:

```bash
docker build -t movieswipe .
docker run -p 8000:8000 -e JWT_SECRET=change-me-to-a-long-random-string -v movieswipe-data:/data movieswipe
```

Keep a single uvicorn worker / replica: duo/group session websockets are tracked in process memory, and migrations
run at startup. TMDB scripts work inside the container, e.g. `docker compose exec app python scripts/sync_tmdb.py --pages 5`.

**Optional TMDB:** put `TMDB_API_KEY=...` in `.env` (see `.env.example`), then

```bash
python backend/scripts/sync_tmdb.py --enrich-seed   # posters, trailers, IN providers for bundled titles
python backend/scripts/sync_tmdb.py --pages 5        # import trending + popular Indian titles
```

### Posters & artwork

Without a TMDB key, artwork comes from two official public APIs (no keys needed):

- **TV shows → [TVmaze](https://www.tvmaze.com/api):** proper portrait posters plus a landscape background for the
  details header (all 77 bundled shows).
- **Films → English Wikipedia:** the infobox poster (all 89 films). These files are small (~220–280 px), so the app
  shows them framed over a blurred copy instead of stretching them.

```bash
python backend/scripts/fetch_artwork.py              # artwork for titles missing from artwork.json + cache
python backend/scripts/fetch_artwork.py --type tv    # refresh all TV shows
python backend/scripts/fetch_artwork.py --warm-only  # just (re)download missing images
```

URLs live in `backend/app/data/artwork.json`. Images are downloaded once into `backend/image_cache/` (shrunk to
900 px wide, ~30 MB total) and served to phones by the PC (`/api/img`), so phones never hit the image hosts directly.
For sharp film posters, add a TMDB key and run `python backend/scripts/sync_tmdb.py --enrich-seed`.

### Publish the website

The web app is responsive: phones get the swipe-first layout, and screens 1024 px and wider get a sidebar, a
three-column Discover (filters · deck · live details of the current card), multi-column lists and centred dialogs.
Visitors who aren't signed in see a landing page. One container serves everything: FastAPI hosts the built React
app, the API, websockets and the poster cache.

**Render (recommended, uses `render.yaml`):**

1. Put the project on GitHub (`git init`, commit, push to a new repository).
2. In [Render](https://render.com): **New → Blueprint**, choose the repository. It builds the `Dockerfile`, generates
   `JWT_SECRET`/`ADMIN_TOKEN`, and attaches a 1 GB disk at `/data` (database + image cache). Note: persistent disks
   need a paid instance.
3. Open the `https://…onrender.com` URL; add your own domain under *Settings → Custom domains* (HTTPS is automatic).

**Any other Docker host** (Railway, Fly.io, a VPS): build the `Dockerfile`, mount a volume at `/data`, set
`JWT_SECRET`, expose port 8000, and run a **single** instance (session websockets live in process memory). Use
`docker-compose.yml` if you want Postgres instead of SQLite.

After deploying, point the Android app at the public server so it works anywhere, not just on your Wi-Fi:

```bash
cd frontend
VITE_API_BASE=https://your-domain.example npm run apk
```

### Android app (APK)

`sai.apk` in the project root is a debug build of the same app, wrapped with Capacitor (`frontend/android`).
It talks to the backend running on your PC over Wi-Fi.

1. **Start the server so the phone can reach it** (note `--host 0.0.0.0`):

   ```bash
   .venv/Scripts/python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
   ```

2. **Copy the APK to your phone** — USB cable, Google Drive, or serve it from the PC and open
   `http://192.168.0.9:8080/sai.apk` in the phone's browser:

   ```bash
   python -m http.server 8080
   ```

3. **Install it** — allow "Install unknown apps" for your browser/file manager when Android asks.
4. Open MovieSwipe. The welcome screen shows the server status; if your PC's IP changes, tap **Change**
   (also under Me → Settings). Phone and PC must be on the same Wi-Fi. If it can't connect, allow Python
   through Windows Firewall on private/public networks.

**Rebuild after code changes:** `cd frontend && npm run apk` — builds the web app with your PC's Wi-Fi address as the
default server, syncs it into `frontend/android`, runs Gradle (JDK 21 + Android SDK from `D:\Android`) and copies the
result to `sai.apk` and `apk-share/sai.apk`.

This is a debug-signed APK for sideloading. For the Play Store, deploy the backend to a public HTTPS URL, set it as
`VITE_API_BASE`, and build a signed release (`./gradlew bundleRelease`).

**Tests:** `pytest backend/tests` (25 tests, including every item in §16's definition of done).

API docs: http://localhost:8000/docs
