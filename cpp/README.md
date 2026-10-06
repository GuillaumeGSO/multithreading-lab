# C++ — search service

C++ implementation of the multithreading lab word-search API.

**Stack**: C++17 · [cpp-httplib](https://github.com/yhirose/cpp-httplib) · [nlohmann/json](https://github.com/nlohmann/json) · CMake · Python 3 + PyYAML (build-time model generation)

## Concurrency model

The word cache is a global `std::unordered_map` protected by a single `std::mutex`.
Multiple HTTP handler threads call `loadWords()` concurrently; the mutex serialises
the first write per key and allows subsequent reads without blocking (lock is held
only long enough to read or insert).

The `/search/many` endpoint fans out one task per word length onto a **bounded
`SearchPool`** (a fixed set of worker threads shared across all requests, so total
OS threads stay bounded under load). Each task writes to its own `partials[idx]`
slot so no mutex is needed for the results vector; results are concatenated
**longest-first** after all tasks complete.

The cache uses `std::mutex` rather than a lock-free atomic pattern because
double-check locking with `std::atomic` is subtle and offers no meaningful gain
here (word lists are loaded once and then purely read).

### Parallel modes & in-process benchmark

`search.cpp` also adds an **intra-file split** (`inFileSplit` — raw `std::thread`s
over contiguous word-list chunks) and a **nested** mode (`inManyFilesNested` —
the per-length pool fan-out where each task also runs a raw-thread split).
`SEARCH_MODE=parallel` (default) routes `/search/file` → split and
`/search/many` → nested; `SEARCH_MODE=baseline` restores the original.

> Note: under the in-process benchmark the parallel modes can run *slower* than
> the single-threaded baseline here — the `SearchPool` future machinery plus raw
> thread creation outweighs the gain on these short tasks, and `matchesContent`
> copies the letter pool per word. A genuine, measured characteristic of this
> implementation. Output stays identical to baseline (`test_search.cpp` asserts it).

```bash
# Cross-language chart (from repo root)
cd benchmarks && bash run-all.sh
# This implementation's runner, inside its container:
docker compose run --rm --entrypoint /app/bench cpp
```

## Structure

```
cpp/
├── CMakeLists.txt           # FetchContent deps + the codegen steps below
├── Dockerfile
├── codegen/
│   ├── gen_models.py        # openapi.yaml -> build/generated/models.gen.h
│   └── spec_to_json.py      # openapi.yaml -> build/openapi.json
├── src/
│   ├── main.cpp             # HTTP handlers + main(), port 8004
│   ├── search.h             # algorithm declarations
│   └── search.cpp           # brute-force algorithm + word cache
└── test/
    └── test_search.cpp      # doctest suite
```

## API contract (spec-first)

The repository's [`openapi.yaml`](../openapi.yaml) is the only definition of the API.
No mainstream OpenAPI generator targets cpp-httplib + nlohmann/json, so the models
come from a small in-repo generator, [`codegen/gen_models.py`](codegen/gen_models.py),
run by CMake on every build where the spec changed:

- **Models** — one struct per schema in `namespace api` (`api::SearchFileRequest`,
  `api::SearchManyRequest`, `api::SearchResponse`, `api::Hint`, `api::HealthResponse`,
  `api::ErrorResponse`), with nlohmann `from_json` / `to_json`. The spec's descriptions
  become comments and `api::kVersion` holds its `info.version`. Mapping rules:
  required → plain member (parsing throws when it is absent), optional with a `default`
  → member initialised to that default, otherwise `std::optional<T>`.
- **Handlers** — `main.cpp` parses bodies with `json::parse(body).get<api::…>()`.
  Malformed JSON, a missing required field or a wrong type answers `400` with
  `api::ErrorResponse`. The generated `api::Hint` is mapped onto the algorithm's
  own `Hint`.
- **Spec and docs** — `codegen/spec_to_json.py` writes `build/openapi.json`. The server
  serves `openapi.yaml` (`OPENAPI_PATH`) at `/openapi.yaml`, the JSON file
  (`OPENAPI_JSON_PATH`) at `/openapi.json`, and Swagger UI at `/docs`.

Both outputs live in the build tree (`cpp/build/`, gitignored) and are never committed.
The generator needs Python 3 with PyYAML. CMake checks for it at configure time and
prefers the `python3` on `PATH`; pass `-DPython3_EXECUTABLE=/path/to/python3` to pick
another interpreter.

## Local development

Requires CMake 3.14+, a C++17 compiler, and Python 3 with PyYAML
(`python3 -m pip install pyyaml`) for the model generator. The CMake build downloads
dependencies (cpp-httplib, nlohmann/json, doctest) via FetchContent on first configure.

```bash
# From the repo root
cmake -S cpp -B cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build cpp/build -j$(nproc)

# Run tests
cd cpp/build && ASSETS_ROOT=../../assets ctest -V

# Run the server
ASSETS_ROOT=assets OPENAPI_PATH=openapi.yaml OPENAPI_JSON_PATH=cpp/build/openapi.json \
  ./cpp/build/search
# API starts on http://localhost:8004 (Swagger UI at /docs)
```

## Docker

```bash
# Build and run (from repo root — build context must be root for assets/)
docker compose up cpp --build

# Or build the image directly
docker build -f cpp/Dockerfile -t seek-words-cpp .
docker run -p 8004:8004 seek-words-cpp
```

## Unit tests

`test/test_search.cpp` uses [doctest](https://github.com/doctest/doctest) and covers:

- `utf8Split` / `unidecode` helpers
- `matchesContent`: basic match, missing letter, strict mode, accent (`île`)
- `matchesHints`: match, excluded, out-of-range, null letter, multiple hints
- `inFile` integration: 8 / 8 / 11 results against real `assets/fr/5.txt`
- `inManyFiles` integration: 494 results for "guillaume", longest-first order
- Error cases: empty params throw, missing file returns `[]`

```bash
cd cpp/build && ASSETS_ROOT=../../assets ctest -V
```

## API

The contract is the repository's [`openapi.yaml`](../openapi.yaml); browse it at
`/docs` (Swagger UI) or fetch it from `/openapi.json` / `/openapi.yaml`.

### `GET /health`

```json
{"status": "ok"}
```

### `POST /search/file`

Words of exactly `wordLength` characters built from `letters` and/or matching the
positional `hints`.

```json
// Request
{
  "lang": "fr",
  "wordLength": 5,
  "letters": ["e","l","i","s","a"],
  "hints": [
    {"position": 1, "letter": "s", "excluded": false}
  ],
  "strict": false
}

// Response
{"words": ["saisi", "salai", "salas", ...], "count": 20}
```

### `POST /search/many`

Words of every length up to the number of `letters`, ordered longest-first.

```json
// Request
{"lang": "fr", "letters": "guillaume", "hints": []}

// Response
{"words": ["aiguillai", "aiguillee", ...], "count": 494}
```

### Errors

An invalid request (malformed JSON, `wordLength` of 0, or neither `letters` nor
`hints`) answers `400` with the contract's `ErrorResponse`:

```json
{"error": "letters and hints cannot both be empty"}
```

## Environment variables

| Variable      | Default    | Description                                                      |
|---------------|------------|------------------------------------------------------------------|
| `ASSETS_ROOT` | `assets`   | Path to the word list directory                                  |
| `PORT`        | `8004`     | HTTP port to listen on                                           |
| `SEARCH_MODE` | `parallel` | `parallel` routes the API through split/nested; `baseline` the original |
| `SPLIT_DEGREE`| `2`        | Intra-file chunk count for `split`/`nested`                      |
| `OPENAPI_PATH`| `/app/openapi.yaml` | API contract served at `/openapi.yaml`                  |
| `OPENAPI_JSON_PATH` | `OPENAPI_PATH` with `.json` | JSON copy of the contract served at `/openapi.json` |
