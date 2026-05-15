FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY python-improved/pyproject.toml python-improved/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY python-improved/seek_words.py python-improved/api.py ./
COPY assets/ ./assets/

ENV ASSETS_ROOT=/app/assets

EXPOSE 8001
CMD [".venv/bin/uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001"]
