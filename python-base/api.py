from fastapi import FastAPI
from pydantic import BaseModel

from seek_words import Hint, search_in_file, search_in_many_files

app = FastAPI()


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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/search/file", response_model=SearchResponse)
def search_file(req: SearchFileRequest):
    hints = [Hint(h.pos, h.car, h.inverted) for h in req.lst_hint]
    words = list(search_in_file(
        lang=req.lang,
        nb_car=req.nb_car,
        lst_car=req.lst_car,
        lst_hint=hints,
        strict=req.strict,
    ))
    return SearchResponse(words=words, count=len(words))


@app.post("/search/many", response_model=SearchResponse)
def search_many(req: SearchManyRequest):
    hints = [Hint(h.pos, h.car, h.inverted) for h in req.lst_hint]
    words = list(search_in_many_files(
        lang=req.lang,
        cars=req.cars,
        lst_hint=hints,
    ))
    return SearchResponse(words=words, count=len(words))
