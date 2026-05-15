FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY python/pyproject.toml python/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY python/seek_words.py python/api.py ./
COPY assets/ ./assets/

ENV ASSETS_ROOT=/app/assets

EXPOSE 8000
CMD [".venv/bin/uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
