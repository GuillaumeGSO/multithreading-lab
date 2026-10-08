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
   concatenating the results longest-first.

The word-list cache lives inside each worker, so it is **per-thread**. Each
worker warms its own cache over its lifetime; no cache is shared across threads
and no `SharedArrayBuffer` is used.

The search algorithm itself is a plain scan, with no index. Each worker loads a word list
once into parallel arrays: the words, their accent-free forms, and one flat byte array of
a–z letter counts. A query prepares its letter pool once, and the per-word check allocates
nothing.

### Parallel modes & in-process benchmark

A worker task can scan a contiguous **chunk** of a file (`inFileRange` +
`chunkIndex`/`chunkCount` on the task), enabling an **intra-file split** and a
**nested** mode (per-length × per-chunk tasks). `SEARCH_MODE=parallel` (default)
routes `/search/file` → split (`SPLIT_DEGREE` chunks) and `/search/many` →
nested; `SEARCH_MODE=baseline` runs one task at a time per request: one whole-file
task for `/search/file`, and the lengths one after another for `/search/many`. There
is no index here, so any other value, including `indexed`, stops the server at
startup. No thread is ever
spawned per task: the extra `nested` tasks just **queue on the fixed pool**
rather than oversubscribing. Output is identical to baseline (`worker-pool.spec.ts` asserts it).

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
│   ├── main.ts               # bootstrap: FastifyAdapter, port 8006, serves the spec + /docs
│   ├── app.module.ts
│   ├── generated/
│   │   └── api.d.ts          # GENERATED from ../openapi.yaml (gitignored)
│   ├── common/
│   │   └── error.filter.ts   # maps failures to ErrorResponse {"error": "..."}
│   ├── health/               # GET /health
│   └── search/
│       ├── search.ts         # pure brute-force algorithm + word cache
│       ├── search.types.ts   # aliases onto the generated request/response types
│       ├── search.worker.ts  # worker_threads entry — one length scan per task
│       ├── worker-pool.ts    # WorkerPool — N persistent workers, task queue
│       ├── search.controller.ts
│       ├── search.validation.ts # runtime checks of bodies against the spec's bounds
│       └── search.service.ts # orchestrates file / many across the pool
└── test/
    ├── search.spec.ts        # pure-logic unit tests (no workers)
    ├── worker-pool.spec.ts   # pool + fan-out integration tests
    └── api.spec.ts           # HTTP request validation (built app, Fastify inject)
```

## API contract (spec-first)

The repository's [`openapi.yaml`](../openapi.yaml) is the only definition of the API;
there are no DTO classes or `@Api*` decorators.

- **Types** — [openapi-typescript](https://openapi-ts.dev) generates
  `src/generated/api.d.ts` from the spec. `search.types.ts` exposes
  `components['schemas'][…]` as `SearchFileRequest`, `SearchManyRequest`,
  `SearchResponse`, `HealthResponse`, `ErrorResponse` and `HintRequest`, used by the
  controllers, the service, the exception filter and the benchmark. Generation uses
  `--default-non-nullable false`, so fields with a spec `default` stay optional in the
  request types. TypeScript types carry no runtime values, so the service applies those
  defaults (`lang = "fr"`, empty lists, `excluded = false`).
- **Spec and docs** — `main.ts` loads `openapi.yaml` with `js-yaml` and hands it to
  `SwaggerModule.setup`, which serves Swagger UI at `/docs`, the document at
  `/openapi.json` and `/openapi.yaml`. `@nestjs/swagger` (+ `@fastify/static`) is used
  only for the UI, never to build the document.
- **Status codes** — both search routes use `@HttpCode(200)`, as the contract
  specifies (Nest's POST default is 201).

`src/generated/` is **gitignored**. `npm run generate` rebuilds it, and runs
automatically before `npm run build` (`prebuild`) and `npm test` (`pretest`), so a
spec change is picked up by the next build or test run.

## Local development

Requires Node 22+.

> The repo lives on an exFAT volume; `npm install` into `nest/node_modules` may
> be slow or emit warnings there. The Docker build installs dependencies inside
> the container and is unaffected.

```bash
# From the nest/ directory
cd nest && npm install
npm run generate                       # src/generated/api.d.ts from ../openapi.yaml
ASSETS_ROOT=../assets PORT=8006 npm run start:dev

# The API starts on http://localhost:8006 (Swagger UI at /docs)
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

Two suites:

- `search.spec.ts` — pure algorithm: content/hint matching plus integration
  assertions against the real asset files. No worker threads.
- `worker-pool.spec.ts` — the pool itself: task dispatch, concurrent fan-out,
  parity with the pure algorithm, and clean teardown. It runs against the
  compiled `dist/`, so it builds first.
- `api.spec.ts` — the HTTP layer: invalid bodies answer `400`, valid ones `200`.
  It also runs against `dist/`.

```bash
cd nest
npm test               # pure-logic suite
npm run test:integration   # builds, then the worker-pool and HTTP suites
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

An invalid request answers `400` with the contract's `ErrorResponse`. That covers
malformed JSON, a wrong field type, any value outside the bounds in `openapi.yaml`
(`lang` other than `fr`/`en`, `wordLength` or a hint `position` outside 1–31, more
than 32 letters or 31 hints), and a request with neither `letters` nor `hints`:

```json
{"error": "letters and hints cannot both be empty"}
```

## Environment variables

| Variable           | Default             | Description                                  |
|--------------------|---------------------|----------------------------------------------|
| `ASSETS_ROOT`      | `assets` (relative) | Path to the word list directory              |
| `PORT`             | `8006`              | HTTP port to listen on                       |
| `WORKER_POOL_SIZE` | `2`                 | Number of persistent search worker threads   |
| `SEARCH_MODE`      | `parallel`          | `baseline` or `parallel` (see [Parallel modes](#parallel-modes--in-process-benchmark)) |
| `SPLIT_DEGREE`     | `2`                 | Intra-file chunk count for `split`/`nested`  |
| `OPENAPI_PATH`     | `../openapi.yaml` (relative to `dist/`, i.e. the repo root) | API contract served at `/openapi.json`, `/openapi.yaml`, `/docs` |
