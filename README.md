# Multithreading Lab

A personal learning project to experiment with multithreading across multiple languages using the **same logic and assets** in each implementation.

## Goal

Implement, then progressively optimize, identical concurrent programs in:

- **Python** ✅ (strategy dispatcher: positional/frequency index ⟷ on-load scan)
- **Java** ✅ (virtual threads)
- **Go** ✅ (goroutines)
- **C++** ✅ (`std::thread` + bounded pool)
- **Nest** ✅ (worker_threads pool)
- **C#** ✅ (`Task.WhenAll` + `Task.Run` / ThreadPool)

The intent is to observe and compare how each language expresses concurrency, what primitives it provides, and how performance characteristics differ — not to build something production-ready.

## Problem

Each implementation exposes a word-search API over a shared dictionary dataset (`assets/`). Queries filter words by available letters, positional hints, and word length. The workload is CPU-bound filtering over in-memory data — a good fit for observing threading models under load.

## Approach

Each language has one implementation wrapping the same search logic behind the same HTTP API, applying its own concurrency techniques (thread pools, virtual threads, goroutines, worker pools, etc.). The Python implementation consolidates the project's algorithm experiments — a brute-force scan, an on-load index, and a positional/frequency index — into a single **strategy dispatcher** that runs whichever algorithm is faster for each query.

## Structure

```
multithreading-lab/
├── assets/                  # Shared word lists: assets/{lang}/{nb_letters}.txt
├── load-tests/              # Artillery — measures API/HTTP handling
│   ├── artillery.yml        # Single test file, environments select the target
│   ├── run-all.sh           # Runs Artillery against all reachable containers
│   ├── compare.py           # Generates compare-report.html from results/
│   └── results/             # Per-run JSON outputs (gitignored)
├── benchmarks/              # In-process bench — measures algorithm + concurrency (no HTTP)
│   ├── cases.json           # Shared, generated case set (single source of truth)
│   ├── gen_cases.py         # Deterministic case generator
│   ├── run-all.sh           # Benches every container, builds compare.html
│   └── aggregate.py         # Chart generator
├── python/                  # Python — strategy dispatcher (index ⟷ scan), uvicorn --workers 2
├── java/                    # Spring Boot + virtual threads (Java 21)
├── go/                      # net/http + goroutines (Go 1.23)
├── nest/                    # NestJS + worker_threads pool (Node 22)
├── cpp/                     # C++17 + std::thread + bounded pool (cpp-httplib)
├── csharp/                  # ASP.NET Core 9 + Task.WhenAll / ThreadPool (.NET 9)
└── docker-compose.yml       # One service per implementation
```

## API contract

All containers expose the same three endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/search/file` | Search words of a fixed length |
| `POST` | `/search/many` | Search words across all lengths |

See [`openapi.yaml`](openapi.yaml) for the full schema, or browse the interactive UI for any running container (see table below).

## API Documentation (OpenAPI)

The root [`openapi.yaml`](openapi.yaml) is the **single source of truth** for the API contract — schemas, descriptions, and examples are defined there once.

Each implementation exposes its spec through its ecosystem's idiomatic tooling:

| Implementation | Approach | Swagger UI | Spec endpoint |
|---|---|---|---|
| Python | FastAPI auto-generates from Pydantic models | [`/docs`](http://localhost:8007/docs) | `/openapi.json` |
| NestJS | `@nestjs/swagger` generates from class decorators | [`/docs`](http://localhost:8006/docs) | `/openapi.json` |
| Java | springdoc generates from `@Operation`/`@Schema` | [`/docs`](http://localhost:8002/docs) | `/openapi.json` |
| C# | .NET 9 native + Scalar UI | [`/docs`](http://localhost:8005/docs) | `/openapi.json` |
| Go | Reads root `openapi.yaml`, converts to JSON at startup | [`/docs`](http://localhost:8003/docs) | `/openapi.json` |
| C++ | Reads `openapi.json` pre-converted at build time | [`/docs`](http://localhost:8004/docs) | `/openapi.json` |

All implementations expose `/docs` (Swagger UI) and `/openapi.json` at the same paths — swapping the backend requires no tooling changes. Python, NestJS, Java, and C# generate their specs at runtime from code annotations; Go and C++ read and serve the root file (path overridable via `OPENAPI_PATH`).

## Running containers

```bash
# Start all implemented containers
docker compose up --build

# Start a specific implementation
docker compose up <service-name>
```

| Implementation   | Port |
|-----------------|------|
| Java            | 8002 |
| Go              | 8003 |
| C++             | 8004 |
| C#              | 8005 |
| Nest            | 8006 |
| Python          | 8007 |

## Load testing

Artillery runs the same scenarios against every container. Results are collected and compared in a single HTML report: [compare-report.html](load-tests/compare-report.html).

```bash
# Run against all reachable containers and generate the comparative report
cd load-tests && bash run-all.sh
# → load-tests/compare-report.html

# Run against a single implementation (environment names match service names)
npx artillery run --environment <service-name> load-tests/artillery.yml
```

The scenario mix is weighted `/health` : `search/file` : `search/many` = 1 : 12 : 24, biasing load toward the multi-length `search/many` queries.

## In-process benchmark

Artillery measures **API/HTTP handling**. [`benchmarks/`](benchmarks/) measures the
other half — the **language implementation itself** — by calling the search functions
directly inside each container (no HTTP). Every language runs the same generated
[`benchmarks/cases.json`](benchmarks/cases.json) with warmup + median-of-N timing, per
concurrency mode, plus a concurrent-load throughput test. `aggregate.py` builds `compare.html`.

```bash
cd benchmarks && bash run-all.sh        # build images, bench every service, build compare.html
```

Two concurrency axes are exposed as named modes — **A** per-length fan-out (`/search/many`),
**B** intra-file split into `SPLIT_DEGREE` chunks: `baseline`, `split` (B), `fanout` (A),
`nested` (A+B). All modes return byte-identical output to baseline. The same parallel paths
are wired into the live API via `SEARCH_MODE` (`parallel` default, `baseline` to restore
original). See [`benchmarks/README.md`](benchmarks/README.md).

## Unit tests

Each implementation has its own test suite covering the core search logic. See the implementation's README for how to run them.

## Languages & threading models

| Implementation   | Concurrency model |
|-----------------|-------------------|
| Python          | Strategy dispatcher (index ⟷ scan per query) + `uvicorn --workers 2` (process-level); threaded split/nested available but GIL-bound |
| Java            | Virtual threads (`ExecutorService`) — per-length fan-out + intra-file split |
| Go              | Goroutines + `sync.WaitGroup` — per-length fan-out + intra-file split |
| C++             | `std::thread` (split) + bounded pool (`std::mutex` cache) |
| Nest            | `worker_threads` pool — fan-out + split tasks queue on the fixed pool |
| C#              | `Task.WhenAll` + `Task.Run` (ThreadPool) — per-length fan-out + intra-file split; `DOTNET_PROCESSOR_COUNT=2` |

Each implementation exposes the same `baseline` / `split` / `fanout` / `nested` modes via
`SEARCH_MODE` + `SPLIT_DEGREE`; the in-process benchmark charts them (see above).

## Dataset

The word lists live in `assets/{lang}/{length}.txt` — one word per line, grouped by
length. Every implementation reads these same files, so the columns below are the
**dictionary languages**, not the implementation languages. Counts are words (lines)
per file; this is why the brute-force scan cost peaks around lengths 8–13 (each holds
50k–65k words) and the in-process benchmark leans on those lengths.

| Word length | en | fr |
|--:|--:|--:|
| 1 | 1 | 7 |
| 2 | 569 | 111 |
| 3 | 4,364 | 582 |
| 4 | 10,408 | 2,473 |
| 5 | 21,952 | 8,146 |
| 6 | 38,214 | 19,054 |
| 7 | 50,475 | 34,728 |
| 8 | 58,188 | 51,493 |
| 9 | 57,289 | 63,074 |
| 10 | 48,590 | 65,834 |
| 11 | 39,362 | 59,723 |
| 12 | 30,259 | 46,869 |
| 13 | 21,640 | 32,573 |
| 14 | 14,584 | 19,920 |
| 15 | 9,075 | 11,271 |
| 16 | 5,321 | 5,743 |
| 17 | 3,042 | 2,762 |
| 18 | 1,504 | 1,268 |
| 19 | 772 | 577 |
| 20 | 363 | 276 |
| 21 | 169 | 117 |
| 22 | 73 | 62 |
| 23 | 30 | 18 |
| 24 | 11 | 8 |
| 25 | 7 | 4 |
| 26 | — | 1 |
| 27 | 3 | — |
| 28 | 2 | — |
| 29 | 2 | — |
| 31 | 1 | — |
| **Total** | **416,270** | **426,694** |

Regenerate after changing the word lists:

```bash
for l in assets/*/; do for f in "$l"*.txt; do printf '%s\t%s\n' "$f" "$(wc -l < "$f")"; done; done
```

## TODO — OpenAPI hardening

The `openapi.yaml` at the repo root is declared the single source of truth, but nothing currently enforces it. Below are concrete steps to make that claim verifiable.

### 1. Spec linting in CI

Catch style violations, broken `$ref`s, and missing required fields before they merge.

```bash
npm install -g @stoplight/spectral-cli
spectral lint openapi.yaml
```

Integrate as a CI step; fail the build on any error.

### 2. Contract testing against live containers

[Schemathesis](https://schemathesis.readthedocs.io) generates requests automatically from the spec and validates every response against it. Run it against each container to guarantee the implementation matches the contract.

```bash
pip install schemathesis
st run openapi.yaml --url http://localhost:8007 --checks all
```

Add one `st run` step per service in CI, after `docker compose up`.

### 3. Drift detection for code-first implementations

Python, NestJS, Java, and C# generate their spec at runtime from annotations. If an annotation changes, the generated spec silently diverges from `openapi.yaml`. A diff step in CI would catch this:

```bash
# Fetch the live generated spec and compare against the root canonical spec
curl -s http://localhost:8007/openapi.json | jq --sort-keys . > generated.json
python -c "import sys,yaml,json; print(json.dumps(yaml.safe_load(open('openapi.yaml'))))" \
  | jq --sort-keys . > canonical.json
diff canonical.json generated.json
```

Run after each service starts in CI; a non-zero diff fails the build.

### 4. Breaking-change detection on PRs

Prevent accidental breaking changes when `openapi.yaml` evolves.

```bash
npm install -g @oasdiff/oasdiff
oasdiff breaking openapi-before.yaml openapi.yaml
```

In CI: compare the spec on the PR branch against the spec on `master`; fail on any breaking change (removed field, changed type, removed endpoint).

### 5. Generate models from the spec (eliminate hand-written structs)

Go and C++ currently hand-write their request/response structs. These could be generated from `openapi.yaml` and committed as `*.gen.*` files, making drift structurally impossible.

| Language | Tool | Command |
|---|---|---|
| Go | [oapi-codegen](https://github.com/oapi-codegen/oapi-codegen) | `oapi-codegen --package api openapi.yaml > api/models.gen.go` |
| C++ | [openapi-generator](https://openapi-generator.tech) | `openapi-generator-cli generate -i openapi.yaml -g cpp-restsdk -o cpp/gen` |
| TypeScript client | openapi-generator | `openapi-generator-cli generate -i openapi.yaml -g typescript-fetch -o client/src/api` |

### 6. Mock server for consumer-driven development

Spin up a mock server from the spec so consumers (e.g. a frontend) can develop before any backend is running.

```bash
npx @stoplight/prism-cli mock openapi.yaml
# → mock server on http://localhost:4010
```