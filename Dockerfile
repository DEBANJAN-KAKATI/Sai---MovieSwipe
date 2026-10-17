# syntax=docker/dockerfile:1
# MovieSwipe: one image that builds the React frontend and serves it from the FastAPI app.
#   docker build -t movieswipe .
#   docker run -p 8000:8000 -e JWT_SECRET=... -v movieswipe-data:/data movieswipe   # SQLite in /data
# For Postgres see docker-compose.yml.

# ---------------------------------------------------------------- frontend build
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- runtime
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATABASE_URL=sqlite:////data/movieswipe.db \
    IMAGE_CACHE_DIR=/data/image_cache
WORKDIR /app/backend

# Dependencies first (cached until pyproject.toml changes): core + the postgres extra.
COPY backend/pyproject.toml ./
RUN python -c "import tomllib; p = tomllib.load(open('pyproject.toml', 'rb'))['project']; \
print('\n'.join(p['dependencies'] + p['optional-dependencies']['postgres']))" > /tmp/requirements.txt \
 && pip install -r /tmp/requirements.txt

# Run from source: app.config resolves frontend/dist relative to backend/, i.e. /app/frontend/dist.
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY --from=frontend /app/frontend/dist /app/frontend/dist

RUN useradd --system --uid 10001 --home-dir /app movieswipe \
 && mkdir -p /data && chown movieswipe /data
USER movieswipe
VOLUME ["/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

# Migrations (alembic upgrade head) and catalog seeding run on startup. Keep a single worker:
# duo/group session websockets are tracked in process memory.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
