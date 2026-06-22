FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY python/pyproject.toml python/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY python/common.py python/strategy_indexed.py python/strategy_scan.py \
     python/seek_words.py python/api.py python/parallel.py ./
COPY benchmarks/python_bench_shared.py ./bench.py
COPY benchmarks/cases.json ./cases.json
COPY assets/ ./assets/

ENV ASSETS_ROOT=/app/assets

EXPOSE 8007
CMD [".venv/bin/uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8007", "--workers", "2", "--log-level", "warning"]
