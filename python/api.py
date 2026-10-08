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
from starlette.exceptions import HTTPException as StarletteHTTPException

from generated.models import (
    ErrorResponse,
    HealthResponse,
    SearchFileRequest,
    SearchManyRequest,
    SearchResponse,
)
from modes import resolve_mode
from seek_words import Hint

# SEARCH_MODE (baseline | parallel | indexed, default parallel) picks the
# implementation; see modes.py. An unknown value fails here, at startup.
_MODE = resolve_mode()

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

# 64 KiB is far above any valid request (≤ 32 letters, ≤ 31 hints).
MAX_BODY_BYTES = 64 * 1024


class BodyTooLarge(StarletteHTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=413, detail="request body is too large")


class BodySizeLimit:
    """ASGI middleware: refuses bodies over MAX_BODY_BYTES with 413. A declared
    Content-Length is checked up front; a chunked body is counted as it is read,
    so an oversized body is never buffered in full."""

    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        length = dict(scope.get("headers", [])).get(b"content-length")
        if length is not None and length.isdigit() and int(length) > self.max_bytes:
            response = JSONResponse(status_code=413, content={"error": "request body is too large"})
            return await response(scope, receive, send)
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise BodyTooLarge()
            return message

        await self.app(scope, limited_receive, send)


app.add_middleware(BodySizeLimit)


def _error(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content=ErrorResponse(error=message).model_dump())


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return _error("; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()))


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    # 404/405/413 and the like keep their status, in the contract's error shape.
    return JSONResponse(status_code=exc.status_code,
                        content=ErrorResponse(error=str(exc.detail)).model_dump())


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
    words = list(_MODE.search_file(
        lang=req.lang or "fr",
        word_length=req.word_length,
        letters=req.letters or [],
        hints=_to_hints(req.hints),
        strict=bool(req.strict),
    ))
    return SearchResponse(words=words, count=len(words))


@app.post("/search/many", response_model=SearchResponse)
def search_many(req: SearchManyRequest) -> SearchResponse:
    words = list(_MODE.search_many(
        lang=req.lang or "fr",
        letters=req.letters,
        hints=_to_hints(req.hints),
    ))
    return SearchResponse(words=words, count=len(words))
