# C++ — search service

C++ implementation of the multithreading lab word-search API.

**Stack**: C++17 · [cpp-httplib](https://github.com/yhirose/cpp-httplib) · [nlohmann/json](https://github.com/nlohmann/json) · CMake

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
├── CMakeLists.txt           # FetchContent: httplib, nlohmann/json, doctest
├── Dockerfile
├── src/
│   ├── main.cpp             # HTTP handlers + main(), port 8004
│   ├── search.h             # algorithm declarations
│   └── search.cpp           # brute-force algorithm + word cache
└── test/
    └── test_search.cpp      # doctest suite
```

## Local development

Requires CMake 3.14+ and a C++17 compiler. The CMake build downloads dependencies
(cpp-httplib, nlohmann/json, doctest) via FetchContent on first configure.

```bash
# From the repo root
cmake -S cpp -B cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build cpp/build -j$(nproc)

# Run tests
cd cpp/build && ASSETS_ROOT=../../assets ctest -V

# Run the server
ASSETS_ROOT=assets ./cpp/build/search
# API starts on http://localhost:8004
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
- `matchesHints`: match, inverted, out-of-range, null car, multiple hints
- `inFile` integration: 8 / 8 / 11 results against real `assets/fr/5.txt`
- `inManyFiles` integration: 494 results for "guillaume", longest-first order
- Error cases: empty params throw, missing file returns `[]`

```bash
cd cpp/build && ASSETS_ROOT=../../assets ctest -V
```

## API

### `GET /health`

```json
{"status": "ok"}
```

### `POST /search/file`

```json
// Request
{
  "lang": "fr",
  "nb_car": 5,
  "lst_car": ["e","l","i","s","a"],
  "lst_hint": [{"pos": 1, "car": "s", "inverted": false}],
  "strict": false
}

// Response
{"words": ["ailes", "alise", ...], "count": 8}
```

### `POST /search/many`

```json
// Request
{"lang": "fr", "cars": "guillaume", "lst_hint": []}

// Response
{"words": [...], "count": 498}
```

## Environment variables

| Variable      | Default    | Description                                                      |
|---------------|------------|------------------------------------------------------------------|
| `ASSETS_ROOT` | `assets`   | Path to the word list directory                                  |
| `PORT`        | `8004`     | HTTP port to listen on                                           |
| `SEARCH_MODE` | `parallel` | `parallel` routes the API through split/nested; `baseline` the original |
| `SPLIT_DEGREE`| `2`        | Intra-file chunk count for `split`/`nested`                      |
