FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY python-base/pyproject.toml python-base/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY python-base/seek_words.py python-base/api.py python-base/parallel.py ./
COPY benchmarks/python_bench.py ./bench.py
COPY benchmarks/cases.json ./cases.json
COPY assets/ ./assets/

ENV ASSETS_ROOT=/app/assets

EXPOSE 8000
CMD [".venv/bin/uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"]
