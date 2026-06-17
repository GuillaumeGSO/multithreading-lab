FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY python-indexed/pyproject.toml python-indexed/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY python-indexed/seek_words.py python-indexed/api.py python-indexed/parallel.py ./
COPY benchmarks/python_bench.py ./bench.py
COPY benchmarks/cases.json ./cases.json
COPY assets/ ./assets/

ENV ASSETS_ROOT=/app/assets

EXPOSE 8005
CMD [".venv/bin/uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8005", "--log-level", "warning"]
