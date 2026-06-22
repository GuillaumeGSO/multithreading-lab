# Node/NestJS — search service

NestJS implementation of the multithreading lab word-search API.

**Stack**: NestJS 11 · Fastify · `worker_threads` pool · Node 22

## Concurrency model

Concurrency appears at two independent levels:

1. **HTTP layer** — Fastify serves requests on Node's single event loop. The
   loop never runs the brute-force scan itself: all CPU work is handed to the
   worker pool, so the loop stays free to accept and reply to requests.
2. **Search layer** — a fixed pool of persistent `worker_threads`
   (`WorkerPool`) executes the scans. `/search/file` submits one task;
   `/search/many` submits one task per word length and `await`s them all,
   concatenating the results longest-first. This is the Node analog of Go's
   goroutine fan-out and Java's `ExecutorService`.

The word-list cache lives inside each worker, so it is **per-thread** — a
deliberate contrast with Go's single shared `sync.Map`. Each worker warms its
own cache over its lifetime; no cache is shared across threads and no
`SharedArrayBuffer` is used (the word lists are strings).

The search algorithm itself is the same brute-force scan as Python's scan strategy
and `go` — no indexing. This isolates the concurrency model as the only variable.

### Parallel modes & in-process benchmark

A worker task can scan a contiguous **chunk** of a file (`inFileRange` +
`chunkIndex`/`chunkCount` on the task), enabling an **intra-file split** and a
**nested** mode (per-length × per-chunk tasks). `SEARCH_MODE=parallel` (default)
routes `/search/file` → split (`SPLIT_DEGREE` chunks) and `/search/many` →
nested; `SEARCH_MODE=baseline` keeps one task per length. Unlike Go/C++'s raw
threads, the extra `nested` tasks just **queue on the fixed pool** rather than
oversubscribing. Output is identical to baseline (`worker-pool.spec.ts` asserts it).

```bash
# Cross-language chart (from repo root)
cd benchmarks && bash run-all.sh
# This implementation's runner, inside its container:
docker compose run --rm --entrypoint node nest dist/bench.js
```

## Structure

```
nest/
├── Dockerfile
├── package.json
├── tsconfig.json
├── nest-cli.json
├── src/
│   ├── main.ts               # bootstrap: FastifyAdapter, port 8006
│   ├── app.module.ts
│   ├── common/
│   │   └── error.filter.ts   # maps failures to {"error": "..."}
│   ├── health/               # GET /health
│   └── search/
│       ├── search.ts         # pure brute-force algorithm + word cache
│       ├── search.worker.ts  # worker_threads entry — one length scan per task
│       ├── worker-pool.ts    # WorkerPool — N persistent workers, task queue
│       ├── search.controller.ts
│       ├── search.service.ts # orchestrates file / many across the pool
│       └── dto/
└── test/
    ├── search.spec.ts        # pure-logic unit tests (no workers)
    └── worker-pool.spec.ts   # pool + fan-out integration tests
```

## Local development

Requires Node 22+.

> The repo lives on an exFAT volume; `npm install` into `nest/node_modules` may
> be slow or emit warnings there. The Docker build installs dependencies inside
> the container and is unaffected.

```bash
# From the nest/ directory
cd nest && npm install
ASSETS_ROOT=../assets PORT=8006 npm run start:dev

# The API starts on http://localhost:8006
```

## Docker

```bash
# Build and run (from repo root)
docker compose up nest --build

# Or build the image directly (build context must be the repo root)
docker build -f nest/Dockerfile -t seek-words-nest .
docker run -p 8006:8006 seek-words-nest
```

## Unit tests

Two suites mirror the Python / go suites:

- `search.spec.ts` — pure algorithm: content/hint matching plus integration
  assertions against the real asset files. No worker threads.
- `worker-pool.spec.ts` — the pool itself: task dispatch, concurrent fan-out,
  parity with the pure algorithm, and clean teardown. It runs against the
  compiled `dist/`, so it builds first.

```bash
cd nest
npm test               # pure-logic suite
npm run test:integration   # builds, then the worker-pool suite
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
{"words": [...], "count": 494}
```

## Environment variables

| Variable           | Default             | Description                                  |
|--------------------|---------------------|----------------------------------------------|
| `ASSETS_ROOT`      | `assets` (relative) | Path to the word list directory              |
| `PORT`             | `8006`              | HTTP port to listen on                       |
| `WORKER_POOL_SIZE` | `2`                 | Number of persistent search worker threads   |
| `SEARCH_MODE`      | `parallel`          | `parallel` routes the API through split/nested; `baseline` is one task per length |
| `SPLIT_DEGREE`     | `2`                 | Intra-file chunk count for `split`/`nested`  |
