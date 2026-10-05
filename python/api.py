import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from parallel import search_in_file_parallel, search_in_many_parallel
from seek_words import Hint, search_in_file, search_in_many_files

# The live default is the index-aware dispatcher (seek_words) — Python's best path:
# the positional index serves pinned-hint queries in O(result), and caching nothing
# per word keeps two uvicorn workers inside the 512 MB budget. SEARCH_MODE=parallel
# opts into the GIL-bound threaded variants (the deliberate "threads don't help a
# CPU-bound scan under the GIL" demo); SEARCH_MODE=baseline is the same dispatcher path.
# (Unlike the real-thread languages, whose `parallel` IS their idiomatic best path,
# Python threads are pure overhead here — so python alone defaults off `parallel`.)
_PARALLEL = os.environ.get("SEARCH_MODE", "dispatcher").lower() == "parallel"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # uvicorn runs with --log-level warning; keep the index-build INFO logs visible.
    logging.getLogger("search").setLevel(logging.INFO)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Word Search API",
    description=(
        "Filters words from dictionary files by available letters, positional hints, "
        "and word length. Python implementation — strategy dispatcher (positional index "
        "⟷ lean scan) backed by FastAPI + Uvicorn."
    ),
    version="1.0.0",
)


class HintModel(BaseModel):
    pos: int
    car: str | None = None
    inverted: bool = False


class SearchFileRequest(BaseModel):
    lang: str = "fr"
    nb_car: int
    lst_car: list[str] = []
    lst_hint: list[HintModel] = []
    strict: bool = False


class SearchManyRequest(BaseModel):
    lang: str = "fr"
    cars: str
    lst_hint: list[HintModel] = []


class SearchResponse(BaseModel):
    words: list[str]
    count: int


@app.get("/health", summary="Liveness check")
def health():
    return {"status": "ok"}


@app.post(
    "/search/file",
    response_model=SearchResponse,
    summary="Search words of a fixed length",
    description="Returns words of exactly `nb_car` characters that can be formed from the available letter pool and satisfy every positional hint.",
)
def search_file(req: SearchFileRequest):
    hints = [Hint(h.pos, h.car, h.inverted) for h in req.lst_hint]
    if _PARALLEL:
        words = search_in_file_parallel(
            lang=req.lang,
            nb_car=req.nb_car,
            lst_car=req.lst_car,
            lst_hint=hints,
            strict=req.strict,
        )
    else:
        words = list(search_in_file(
            lang=req.lang,
            nb_car=req.nb_car,
            lst_car=req.lst_car,
            lst_hint=hints,
            strict=req.strict,
        ))
    return SearchResponse(words=words, count=len(words))


@app.post(
    "/search/many",
    response_model=SearchResponse,
    summary="Search words across all lengths",
    description="Returns words for every length from 1 up to len(cars), ordered longest-first.",
)
def search_many(req: SearchManyRequest):
    hints = [Hint(h.pos, h.car, h.inverted) for h in req.lst_hint]
    if _PARALLEL:
        words = search_in_many_parallel(
            lang=req.lang,
            cars=req.cars,
            lst_hint=hints,
        )
    else:
        words = list(search_in_many_files(
            lang=req.lang,
            cars=req.cars,
            lst_hint=hints,
        ))
    return SearchResponse(words=words, count=len(words))
