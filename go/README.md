# Go — search service

Go implementation of the multithreading lab word-search API.

**Stack**: net/http (standard library) · Go 1.23 · goroutines + `sync.WaitGroup`

## Concurrency model

Concurrency appears at two independent levels:

1. **HTTP layer** — `net/http` serves every incoming request on its own
   goroutine automatically, so all endpoints handle concurrent requests with no
   explicit thread pool.
2. **Search layer** — `search.InManyFiles` spawns one goroutine per word length
   via a `sync.WaitGroup`. Each goroutine scans one length and writes into its
   own slot of a pre-sized slice, so all file scans for a single `/search/many`
   request run in parallel and results stay longest-first with no locking.

The word-list cache is a `sync.Map`, safe for the concurrent requests above.

The search algorithm itself is the same brute-force scan as `python-base` — no
indexing. This isolates the concurrency model as the only variable.

## Structure

```
go/
├── go.mod
├── go.sum
├── Dockerfile
├── main.go            # HTTP server, routing, request/response structs, handlers
└── search/
    ├── search.go      # Hint type, word-list cache, search algorithm
    └── search_test.go # unit + integration tests
```

## Local development

Requires Go 1.23+.

```bash
# From the go/ directory — run the API locally
cd go && ASSETS_ROOT=../assets go run .

# The API starts on http://localhost:8003
```

## Docker

```bash
# Build and run (from repo root)
docker compose up go --build

# Or build the image directly
docker build -f go/Dockerfile -t seek-words-go .
docker run -p 8003:8003 seek-words-go
```

## Unit tests

Tests mirror the python-base pytest suite — unit tests for content/hint matching
plus integration tests against the real asset files. `TestMain` points
`ASSETS_ROOT` at the repo-root `assets/` directory automatically.

```bash
cd go && go test ./...
```

### Race detector

`InManyFiles` fans out one goroutine per word length, each writing into its own
slot of a shared slice with no lock. Run the suite under the race detector to
verify that concurrent access stays data-race free:

```bash
cd go && go test -race ./...
```

A clean run is the proof that the lock-free `partials[idx]` writes and the
shared read-only `letters` slice are safe — keep this passing after any change
to the `InManyFiles` fan-out.

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
  "lang": "fr",
  "nb_car": 5,
  "lst_car": ["e","l","i","s","a"],
  "lst_hint": [
    {"pos": 1, "car": "s", "inverted": false}
  ],
  "strict": false
}

// Response
{"words": ["ailes", "alise", ...], "count": 8}
```

### `POST /search/many`

Search words across all lengths up to `len(cars)`, results ordered longest-first.

```json
// Request
{"lang": "fr", "cars": "guillaume", "lst_hint": []}

// Response
{"words": [...], "count": 498}
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ASSETS_ROOT` | `assets` (relative) | Path to the word list directory |
