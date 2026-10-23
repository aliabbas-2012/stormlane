# One image serves both the API and the built React app (same origin, no CORS).

# --- Frontend build -------------------------------------------------------------------
FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# VITE_API_BASE_URL stays empty: the app calls /api on its own origin.
RUN npm run build

# --- Backend runtime ------------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv
WORKDIR /app/backend

# Dependencies first so code changes don't invalidate this layer.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev

COPY backend/ ./
COPY --from=frontend /app/frontend/dist ./frontend_dist
# Pre-compress the app bundle so WhiteNoise can serve gzip/brotli without doing it per request.
RUN python -m whitenoise.compress frontend_dist && mkdir -p staticfiles

RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
CMD ["./start.sh"]
