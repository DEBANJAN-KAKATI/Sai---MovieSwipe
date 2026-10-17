# sai — Tinder for Movies & TV

<p align="center">
  <img src="frontend/public/sai-wordmark.png" alt="sai logo" width="220" />
</p>

<p align="center">
  <strong>A Tinder-style discovery app for movies and TV that learns your taste with every swipe, matches what to watch together in group sessions, and cures decision paralysis.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React_18-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/Capacitor-119EFF?style=for-the-badge&logo=capacitor&logoColor=white" alt="Capacitor" />
  <img src="https://img.shields.io/badge/SQLite_%2F_PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="Database" />
</p>

---

## ✨ Highlights

- 🃏 **Intuitive Gesture Deck** — Swipe Right (Watch List), Swipe Left (Pass), Pull Down (Maybe Later), Swipe Up (Where to Watch), Long-Press (Must Visit), and Already Watched button. Full keyboard shortcuts (`←`, `→`, `↑`, `↓`, `S`, `W`, `Space`, `Z`) with fluid spring physics.
- 👥 **Duo & Group Matching** — Share a 7-character room code or QR code. Swipes are blended in real-time over WebSockets using harmonic mean ranking to find unanimous or top-ranked mutual matches.
- 🧬 **Adaptive Recommender & Taste DNA** — Learns continuously from every interaction using content embeddings, genre/cast affinities, and time-decayed taste centroids. Features explainable tags ("*Because you liked The Mentalist*") and personal archetypes.
- 🎲 **Decide For Me & Tonight's Pick** — Filter by your exact time budget and mood (*"I have 90 minutes and feel cozy"*), with an animated slot-machine reveal.
- 🙈 **Blind Date Mode** — Judge titles purely by their loglines with posters and titles hidden until swiped.
- 🍿 **Social & Watch Parties** — Side-by-side friend taste compatibility %, collaborative lists, and scheduled watch parties with `.ics` calendar exports.
- 📱 **PWA & Android Ready** — Responsive touch-first mobile UI, installable as a Progressive Web App or packaged as an Android APK via Capacitor.
- 🚀 **Zero Setup to Run** — Comes with a pre-seeded multilingual catalog (Hollywood & Indian cinema across 10 languages) and hashed TF-IDF embeddings—runs locally with **no external API keys, Docker, or model downloads required**.

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, Framer Motion, Zustand, TanStack Query |
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| **Mobile & App** | Capacitor 7 (Android build scripts, splash, icon generation), PWA |
| **Database** | SQLite (default for instant local dev) or PostgreSQL via `DATABASE_URL` |
| **Embeddings** | In-process hashed TF-IDF (default) or Sentence-Transformers (`all-MiniLM-L6-v2`) |
| **External APIs** | Optional TMDB v3/v4 integration for dynamic catalog sync, streaming provider links, and posters |

---

## 🚀 Quickstart

### Option 1: Local Development

#### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & `npm`

#### 1. Backend Setup
```bash
# Navigate to backend
cd backend

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -e .

# Run development server (auto-runs migrations and seeds initial catalog)
uvicorn app.main:app --reload --port 8000
```
> The API and interactive Swagger docs will be live at `http://localhost:8000/docs`.

#### 2. Frontend Setup
In a new terminal window:
```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```
> Open `http://localhost:5173` in your browser.

---

### Option 2: Docker Compose

Run the backend and a PostgreSQL database in Docker with a single command:

```bash
# Build and run with Docker Compose
docker compose up --build
```
> Open `http://localhost:8000` to access the full application.

---

### Option 3: Building the Android APK

The project includes pre-configured Capacitor tooling to produce an Android APK:

```bash
cd frontend
npm install
npm run apk
```
> The compiled APK will be output to `apk-share/` and the project root.

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` to configure optional integrations. All settings have sensible local defaults:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///backend/movieswipe.db` |
| `TMDB_API_KEY` | TMDB API Key / Access Token (enables real posters, trailers & dynamic catalog) | *None (uses bundled catalog)* |
| `JWT_SECRET` | Secret key for auth tokens | *Auto-generated in `backend/.jwt_secret`* |
| `EMBEDDING_BACKEND` | Embedding provider (`hash` or `sbert`) | `hash` |
| `APP_REGION_DEFAULT` | Default region for watch providers | `IN` |
| `ADMIN_TOKEN` | Token for `/api/admin/metrics` endpoint | *None* |

---

## 📂 Project Structure

```text
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (auth, feed, lists, parties, sessions, etc.)
│   │   ├── recs/         # Recommendation engine, taste ranking & mood heuristics
│   │   ├── services/     # Business logic, TMDB client, WebSocket manager, ICS export
│   │   ├── models.py     # SQLAlchemy DB schema
│   │   └── main.py       # FastAPI application entrypoint & static PWA mounting
│   ├── migrations/       # Alembic database migrations
│   └── scripts/          # TMDB sync, artwork fetchers, catalog seeders
├── frontend/
│   ├── src/
│   │   ├── components/   # SwipeDeck, MediaSheets, InfoPanel, BrandLogo, etc.
│   │   ├── pages/        # Discover, Together, Lists, Party, Profile, Onboarding
│   │   ├── api/          # Typed API client & hooks
│   │   └── store.ts      # Zustand client-side state
│   └── android/          # Capacitor Android native project
├── branding/             # High-res logos and asset generators
├── docker-compose.yml    # Multi-container Docker deployment (FastAPI + Postgres)
├── Dockerfile            # Multi-stage production container build
└── IMPLEMENTATION_PLAN.md # Comprehensive engineering specification & plan
```

---

## 📖 Detailed Engineering Specs

For the in-depth architectural breakdown, recommendation math, WebSocket protocol specs, and phased roadmap, refer to:
👉 **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)**

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
