# ─── Stage 1: build the React frontend ──────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps

COPY frontend/ ./
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

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--app-dir", "backend", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2"]
