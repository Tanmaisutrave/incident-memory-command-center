# ─── Stage 1: build the React frontend ──────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps

COPY frontend/ ./
# Render passes service env vars as build args. The key is embedded in the
# public bundle, so it only gates casual abuse; rate limits still apply.
ARG VITE_API_KEY=""
ARG VITE_API_BASE_URL=""
ENV VITE_API_KEY=$VITE_API_KEY VITE_API_BASE_URL=$VITE_API_BASE_URL
# node build.mjs calls vite build; output goes to frontend/dist
RUN node build.mjs

# ─── Stage 2: Python runtime ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user
RUN addgroup --gid 1001 appgroup \
 && adduser  --uid 1001 --gid 1001 --no-create-home --disabled-password appuser

WORKDIR /app

# System deps for uvicorn standard (websockets, httptools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev \
 && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY backend/ ./backend/

# Pre-built frontend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Data directory (override with a volume in production)
RUN mkdir -p /app/backend/data && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3   CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/api/health' % os.environ.get('PORT', '8000'))"

# Render (and most PaaS hosts) inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}"]
