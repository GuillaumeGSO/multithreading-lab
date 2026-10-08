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

The search algorithm itself is a plain brute-force scan — no indexing — so the
concurrency model is the only variable.

### Parallel modes & in-process benchmark

Beyond per-length fan-out, `search` adds an **intra-file split** (`InFileSplit` —
goroutines over contiguous word-list chunks) and a **nested** mode
(`InManyFilesNested` — fan-out where each length is also split, i.e. goroutines
spawning goroutines). Selected by `SEARCH_MODE` (`parallel` default routes
`/search/file` → split and `/search/many` → nested; `baseline` restores the
original). `GOMAXPROCS` is pinned to **2** (via `docker-compose.yml`) to match the
CPU budget — otherwise it defaults to the *host* core count and ignores the cgroup
limit — so the runtime multiplexes the per-length × split goroutines onto 2 OS
threads for a fair 2-core comparison. Output is identical to baseline
(`search_test.go` asserts it).

```bash
# Cross-language chart (from repo root)
cd benchmarks && bash run-all.sh
# This implementation's runner, inside its container:
docker compose run --rm --entrypoint /app/bench go
```

## Structure

```
go/
├── go.mod
├── go.sum
├── Dockerfile
├── main.go               # HTTP server: implements api.ServerInterface, serves the spec + /docs
├── api/
│   ├── generate.go       # go:generate directive (pinned oapi-codegen version)
│   ├── oapi-codegen.yaml # generator configuration
│   └── api.gen.go        # GENERATED from ../openapi.yaml — committed, never edited
├── bench/
│   └── main.go           # in-process benchmark runner
└── search/
    ├── search.go         # Hint type, word-list cache, search algorithm
    └── search_test.go    # unit + integration tests
```

## API contract (spec-first)

The repository's [`openapi.yaml`](../openapi.yaml) is the only definition of the API.
[oapi-codegen](https://github.com/oapi-codegen/oapi-codegen) (v2.8.0, pinned in
`api/generate.go`) turns it into `api/api.gen.go`:

- **Models** — `SearchFileRequest`, `SearchManyRequest`, `SearchResponse`, `Hint`,
  `HealthResponse`, `ErrorResponse`, with the spec's descriptions as doc comments and
  its camelCase names as JSON tags.
- **Server interface** — `api.ServerInterface` (`Health`, `SearchFile`, `SearchMany`).
  `main.go` implements it and `api.HandlerFromMux` registers the routes, so paths and
  methods come from the spec too.

Optional fields are plain values, not pointers (`prefer-skip-optional-pointer`), and
oapi-codegen does not apply schema defaults, so the handlers fill in `lang = "fr"`.

Following Go convention, **`api.gen.go` is committed** (`go build` never runs
generators). After any change to `openapi.yaml`:

```bash
cd go && go generate ./...   # regenerate api/api.gen.go
git diff --exit-code         # CI-style drift check: fails if the committed file is stale
```

The spec itself is served unchanged: `main.go` reads `openapi.yaml` (`OPENAPI_PATH`) at
startup and serves it at `/openapi.yaml`, converted to JSON at `/openapi.json`, with
Swagger UI at `/docs`.

## Local development

Requires Go 1.23+.

```bash
# From the go/ directory — run the API locally
cd go && ASSETS_ROOT=../assets OPENAPI_PATH=../openapi.yaml go run .

# The API starts on http://localhost:8003 (Swagger UI at /docs)
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

Unit tests for content/hint matching plus integration tests against the real
asset files. `TestMain` points
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

An invalid request answers `400` with the contract's `ErrorResponse`. That covers
malformed JSON, a wrong field type, any value outside the bounds in `openapi.yaml`
(`lang` other than `fr`/`en`, `wordLength` or a hint `position` outside 1–31, more
than 32 letters or 31 hints), and a request with neither `letters` nor `hints`:

```json
{"error": "letters and hints cannot both be empty"}
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ASSETS_ROOT` | `assets` (relative) | Path to the word list directory |
| `SEARCH_MODE` | `parallel` | `parallel` routes the API through split/nested; `baseline` restores the original fan-out |
| `SPLIT_DEGREE` | `2` | Intra-file chunk count for `split`/`nested` |
| `OPENAPI_PATH` | `/app/openapi.yaml` | API contract served at `/openapi.yaml` and `/openapi.json` |
