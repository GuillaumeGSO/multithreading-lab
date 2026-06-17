# Python — seek_words

Python implementation of the multithreading lab word-search API.

**Stack**: FastAPI · uvicorn · uv · Python 3.13

## Structure

```
python/
├── seek_words.py   # Core search logic (no HTTP dependency)
├── api.py          # FastAPI HTTP layer
├── main.py         # Integration runner — generates report.html
├── Dockerfile
└── pyproject.toml
```

## Local development

```bash
# Install dependencies
uv sync

# Run the API locally (from repo root)
uv run --project python uvicorn python.api:app --reload

# Or from the python/ directory
cd python && uv run uvicorn api:app --reload
```

The API starts on `http://localhost:8000`. Swagger UI is available at `http://localhost:8000/docs`.

> **Note**: the server must be started from the repo root, or `ASSETS_ROOT` must point to the `assets/` directory.

## Docker

```bash
# Build and run (from repo root)
docker compose up python --build

# Or build the image directly
docker build -f python/Dockerfile -t seek-words-python .
docker run -p 8000:8000 seek-words-python
```

## Integration tests

`main.py` runs all search scenarios against the real asset files and writes an HTML report.

```bash
# From repo root
uv run --project python python python/main.py
# → prints results and writes python/report.html
```

## Parallel modes & in-process benchmark

`parallel.py` adds threaded variants of the search used by the cross-language
in-process benchmark in [`../benchmarks/`](../benchmarks/) and, when
`SEARCH_MODE=parallel` (the default), by the live API:

- **split** — `/search/file` scans the word list in `SPLIT_DEGREE` contiguous
  chunks across `threading` threads.
- **nested** — `/search/many` fans out per length, each length also split.

Because of the GIL these rarely beat the single-threaded baseline — that is the
intended lesson (Python scales at the process layer, see `python-improved`).
Output is byte-identical to baseline (`test_parallel.py` asserts this).

```bash
# Cross-language chart (from repo root)
cd benchmarks && bash run-all.sh
# This implementation's runner, inside its container:
docker compose run --rm --entrypoint .venv/bin/python python-base bench.py
```

## API

### `GET /health`

```json
{"status": "ok"}
```

### `POST /search/file`

Search words of a fixed length using available letters and/or positional hints.

```json
// Request
{
  "lang": "fr",          // language code (matches assets/{lang}/)
  "nb_car": 5,           // word length
  "lst_car": ["e","l","i","s","a"],   // available letters (optional)
  "lst_hint": [          // positional constraints (optional)
    {"pos": 1, "car": "s", "inverted": false}
  ],
  "strict": false        // if true, each letter in lst_car is consumed once
}

// Response
{"words": ["ailes", "alise", ...], "count": 8}
```

### `POST /search/many`

Search words across all lengths up to `len(cars)`.

```json
// Request
{"lang": "fr", "cars": "guillaume", "lst_hint": []}

// Response
{"words": [...], "count": 494}
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ASSETS_ROOT` | `../assets` relative to `seek_words.py` | Path to the word list directory |
| `SEARCH_MODE` | `parallel` | `parallel` routes the API through the threaded variants; `baseline` uses the single-threaded path |
| `SPLIT_DEGREE` | `2` | Intra-file chunk count for the `split`/`nested` modes |
