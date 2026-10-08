# Codegen stage — generate the Pydantic models from the API contract.
FROM python:3.13-slim AS codegen
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /build/python
COPY python/pyproject.toml python/uv.lock ./
RUN uv sync --frozen --only-group codegen --no-install-project
COPY openapi.yaml /build/openapi.yaml
RUN uv run --frozen --no-sync datamodel-codegen

FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY python/pyproject.toml python/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --from=codegen /build/python/generated ./generated
COPY python/common.py python/strategy_indexed.py python/strategy_scan.py \
     python/seek_words.py python/api.py python/parallel.py python/modes.py ./
COPY benchmarks/python_bench.py ./bench.py
COPY benchmarks/cases.json ./cases.json
COPY assets/ ./assets/
COPY openapi.yaml ./openapi.yaml

ENV ASSETS_ROOT=/app/assets
ENV OPENAPI_PATH=/app/openapi.yaml

EXPOSE 8007
# Check SEARCH_MODE before starting: with --workers, uvicorn's supervisor keeps
# running even when every worker fails to import, so a bad value would otherwise
# leave a live container that never serves.
CMD ["sh", "-c", ".venv/bin/python -c 'import modes; modes.resolve_mode()' && exec .venv/bin/uvicorn api:app --host 0.0.0.0 --port 8007 --workers 2 --log-level warning"]
