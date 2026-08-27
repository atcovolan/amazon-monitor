# ---------- Stage 1: build the React frontend ----------
FROM node:20-alpine AS frontend
WORKDIR /frontend

# Install deps (use lockfile for reproducible builds)
COPY frontend/package*.json ./
RUN npm ci || npm install

# Build
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Python backend serving API + frontend ----------
FROM python:3.11-slim AS runtime
WORKDIR /app

# System deps kept minimal; curl_cffi ships manylinux wheels.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Backend source (imports use the `backend.app...` package path)
COPY backend/ ./backend/

# Compiled frontend from stage 1
COPY --from=frontend /frontend/dist ./frontend_dist

# Persistent data location (mount a Railway volume here)
ENV DATA_DIR=/app/data
ENV HOST=0.0.0.0
RUN mkdir -p /app/data

EXPOSE 8000

# Railway provides $PORT; fall back to 8000 for local runs.
CMD uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
