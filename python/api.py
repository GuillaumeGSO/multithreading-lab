import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, Response

from generated.models import (
    ErrorResponse,
    HealthResponse,
    SearchFileRequest,
    SearchManyRequest,
    SearchResponse,
)
from parallel import search_in_file_parallel, search_in_many_parallel
from seek_words import Hint, search_in_file, search_in_many_files

# The live default is the index-aware dispatcher (seek_words): the positional index
# serves pinned-hint queries in O(result), and caching nothing per word keeps two
# uvicorn workers inside the 512 MB budget. SEARCH_MODE=parallel opts into the
# GIL-bound threaded variants (the deliberate "threads don't help a CPU-bound scan
# under the GIL" demo); SEARCH_MODE=baseline is the same dispatcher path.
_PARALLEL = os.environ.get("SEARCH_MODE", "dispatcher").lower() == "parallel"

# The API contract is the repository's openapi.yaml, served verbatim. Request and
# response models in generated/models.py are generated from that same file.
_SPEC_PATH = Path(os.environ.get("OPENAPI_PATH") or Path(__file__).parent.parent / "openapi.yaml")
_SPEC_YAML = _SPEC_PATH.read_text(encoding="utf-8")
_SPEC_JSON = json.dumps(yaml.safe_load(_SPEC_YAML), ensure_ascii=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # uvicorn runs with --log-level warning; keep the index-build INFO logs visible.
    logging.getLogger("search").setLevel(logging.INFO)
    yield


# FastAPI's own spec generation and docs are disabled: /openapi.json and /docs
# below serve the checked-in contract instead.
app = FastAPI(lifespan=lifespan, openapi_url=None, docs_url=None, redoc_url=None)


def _error(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content=ErrorResponse(error=message).model_dump())


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return _error("; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()))


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError) -> JSONResponse:
    return _error(str(exc))


@app.get("/openapi.json", include_in_schema=False)
def openapi_json() -> Response:
    return Response(_SPEC_JSON, media_type="application/json")


@app.get("/openapi.yaml", include_in_schema=False)
def openapi_yaml() -> Response:
    return Response(_SPEC_YAML, media_type="application/yaml")


@app.get("/docs", include_in_schema=False)
def docs() -> HTMLResponse:
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Word Search API")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def _to_hints(hints) -> list[Hint]:
    return [Hint(h.position, h.letter, bool(h.excluded)) for h in hints or []]


@app.post("/search/file", response_model=SearchResponse)
def search_file(req: SearchFileRequest) -> SearchResponse:
    search = search_in_file_parallel if _PARALLEL else search_in_file
    words = list(search(
        lang=req.lang or "fr",
        word_length=req.word_length,
        letters=req.letters or [],
        hints=_to_hints(req.hints),
        strict=bool(req.strict),
    ))
    return SearchResponse(words=words, count=len(words))


@app.post("/search/many", response_model=SearchResponse)
def search_many(req: SearchManyRequest) -> SearchResponse:
    search = search_in_many_parallel if _PARALLEL else search_in_many_files
    words = list(search(
        lang=req.lang or "fr",
        letters=req.letters,
        hints=_to_hints(req.hints),
    ))
    return SearchResponse(words=words, count=len(words))
