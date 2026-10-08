# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A personal learning project implementing the same word-search logic across Python, Java, Go, NestJS, and C# to compare concurrency models under the same algorithm, the same modes and a fair 2-CPU budget. (A C++ version existed and was removed; it is in git history.) Each language exposes the same REST API in its own Docker container. Artillery load tests (`load-tests/artillery.yml`) are container-agnostic — only `--target` changes per language.

## Core Problem

The word search logic filters words from dictionary files (`assets/{lang}/{n}.txt`, where `n` = word length) by available letters, positional hints, and word length. **This logic and the API contract must stay consistent across all language implementations.**

## API Contract (all languages)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/search/file` | Search words of fixed length |
| `POST` | `/search/many` | Search words across all lengths |

## OpenAPI (spec-first)

`openapi.yaml` at the repo root is the **single source of truth** for the API contract. Every
implementation is spec-first: models are **generated** from it and the file is **served
verbatim** — no implementation generates a spec from code or carries hand-written OpenAPI
metadata (no `@Schema`/`@ApiProperty`/`.WithSummary`/route `description=`).

Wire format is camelCase (`wordLength`, `letters`, `hints`, `Hint.position|letter|excluded`,
`ErrorResponse.error`); each language maps it to its own idiom in generated code.

| Implementation | Generator | Output (committed?) | Regenerate |
|---|---|---|---|
| Python | datamodel-code-generator (`[tool.datamodel-codegen]` in pyproject) | `python/generated/models.py` (no) | `uv run --group codegen datamodel-codegen` |
| Java | openapi-generator-maven-plugin, `spring`, `interfaceOnly` | `java/target/generated-sources/openapi` (no) | any Maven build |
| Go | oapi-codegen v2 (models + std-http `ServerInterface`) | `go/api/api.gen.go` (**yes**) | `cd go && go generate ./...` |
| NestJS | openapi-typescript (`--default-non-nullable false`) | `nest/src/generated/api.d.ts` (no) | `npm run generate` (auto on build/test) |
| C# | NSwag.MSBuild (`Net100`), DTOs only | `csharp/Api/obj/Generated/Contracts.g.cs` (no) | any `dotnet build` |

**Rules:**
- Change the contract **only** in `openapi.yaml`, then regenerate; never hand-edit generated code.
  Go's `api.gen.go` must be regenerated and committed with the spec change.
- Every implementation serves `/openapi.yaml` (verbatim), `/openapi.json` (converted) and a UI
  at `/docs` (Swagger UI; C# uses Scalar), so swapping the backend requires no tooling changes.
- Generators read `../openapi.yaml`; Dockerfiles mirror the repo layout (`/build/openapi.yaml` +
  `/build/<lang>`) so the same relative path works in images. Runtime images get the spec at
  `/app/openapi.yaml` (`OPENAPI_PATH`).
- Errors are the contract's `ErrorResponse` (`{"error": "..."}`, HTTP 400); search endpoints
  return 200 (Nest needs `@HttpCode(200)`).
- `benchmarks/cases.json` and `load-tests/queries.csv` use the same camelCase names as the wire
  format (`letters` is an array for file cases, a string for many cases).
- Version string must be `1.0.0` in `openapi.yaml`.
- Per-language READMEs and code comments must not reference other languages; cross-language
  comparison belongs in the root README / this file only.

## Structure

```
multithreading-lab/
├── openapi.yaml        # API contract — single source of truth
├── assets/             # Shared word lists
├── benchmarks/         # In-process benchmark (no HTTP), rounds + compare.html + summary.md
├── load-tests/         # Artillery; one artillery.yml, environments select the target
├── python/             # FastAPI/uvicorn --workers 2; scan + positional-index dispatcher
├── java/               # Spring Boot 4, virtual threads; scan + positional-index dispatcher
├── go/                 # net/http, goroutines; scan only
├── nest/               # NestJS/Fastify, worker_threads pool; scan only
├── csharp/             # ASP.NET Core Minimal API, Task.WhenAll/ThreadPool; scan + positional-index dispatcher
├── docker-compose.yml  # Python=8007, Java=8002, Go=8003, Nest=8006, C#=8005
└── CLAUDE.md
```

## Per-implementation READMEs

Each directory has its own README covering local dev, Docker, and API details:
- [`python/README.md`](python/README.md)
- [`java/README.md`](java/README.md)
- [`go/README.md`](go/README.md)
- [`nest/README.md`](nest/README.md)
- [`csharp/README.md`](csharp/README.md)

## Load testing (API/HTTP)

`load-tests/artillery.yml` is the single test file for all implementations. Environments map names to ports — do not create per-language YAML files.

```bash
# Every service under SEARCH_MODE=baseline, then parallel; builds compare-report.html + summary.md
cd load-tests && bash run-all.sh

# Run a single environment manually (requires npm install in load-tests/ first)
cd load-tests && npm run run:python
```

## In-process benchmark (algorithm + concurrency)

Artillery measures HTTP handling; [`benchmarks/`](benchmarks/) measures the language
implementation itself by calling the search functions directly **inside each container**
(no HTTP). All languages run the shared [`benchmarks/cases.json`](benchmarks/cases.json)
with warmup + median-of-N timing, per concurrency mode, repeated for `ROUNDS` rounds (default 3).
`aggregate.py` builds `compare.html` and `summary.md` (median across rounds + min–max range).

```bash
cd benchmarks && bash run-all.sh        # build images, bench every service, build compare.html
```

Two concurrency axes, exposed as named modes: **A** = per-length fan-out (`/search/many`),
**B** = intra-file split into `SPLIT_DEGREE` contiguous chunks (default 2). Modes: `baseline`
(neither), `split` (B, `/file`), `fanout` (A), `nested` (A+B), plus `indexed` (`/file`, an
algorithm comparison, Python/Java/C# only). All modes return byte-identical output to baseline.

### Rules for a fair comparison

- **Same algorithm.** Every implementation's scan precomputes, per word at load time, the
  accent-free form and the a–z letter counts; a query prepares its letter pool once; only the
  predicates a query needs are evaluated. Python's `common.load_base` + `strategy_scan.py` is
  the reference. Never add an optimisation to one language's scan without the others.
- **Same mode.** `SEARCH_MODE` means the same thing everywhere, and the default is `parallel`
  for every implementation (Python included):

  | `SEARCH_MODE` | `/search/file` | `/search/many` |
  |---|---|---|
  | `baseline` | single-threaded scan | single-threaded scan, lengths in sequence |
  | `parallel` | split into `SPLIT_DEGREE` chunks | per-length fan-out, each length split |
  | `indexed` (Python/Java/C#) | index dispatcher (index iff a pinned hint) | single-threaded scan |

  An unknown value must stop the server at startup. Charts and tables only ever compare
  languages within one mode; the index is reported separately as scan-vs-index.

## Unit tests

Each implementation has its own unit suite (Python `pytest`, Go `go test`, Java `mvn test`,
Nest `jest` — `npm test` plus `npm run test:integration` — C# `dotnet test`). Each also has
HTTP-level validation tests and mode-equivalence tests. Run the Python suite with:

```bash
cd python && uv run pytest -v
```

The suite must pass before and after any change to `seek_words.py`. The `python` suite is
the correctness reference; its `test_dispatch.py` additionally asserts the two strategies
return byte-identical output (so per-query dispatch can never change results) and the other
languages mirror these expected results.

## CI

`.github/workflows/ci.yml` runs on pushes and pull requests to `master`:
- Spectral lint of `openapi.yaml`, failing on warnings.
- Each language's suite, plus `ruff check` for Python and `gofmt`, `go vet` and a regenerate-and-diff of
  `go/api/api.gen.go` for Go.
- A Docker smoke test: `docker compose up --wait` on the health checks, then one valid and one
  invalid request per service.

Keep it green: run the matching local command before changing a language, and regenerate Go's
`api.gen.go` whenever `openapi.yaml` changes. Dependabot (`.github/dependabot.yml`) opens weekly
updates for every ecosystem.

`.github/workflows/pages.yml` publishes the committed `benchmarks/compare.html` and
`load-tests/compare-report.html` to GitHub Pages when either changes on `master` (the root
README links to the Pages URLs). Regenerate and commit a report to update its page.

`.github/workflows/images.yml` runs after CI succeeds on `master` (or manually) and pushes
each service image (`linux/amd64`) to `ghcr.io/guillaumegso/multithreading-lab-<service>`,
tagged `latest` and `sha-<short>`.

## Concurrency models by implementation

| Implementation   | `parallel` mode uses |
|-----------------|-------|
| Python          | `threading` — GIL-bound, so it cannot use the second core; `uvicorn --workers 2` is the process-level parallelism under HTTP load |
| Java            | Virtual threads (`Executors.newVirtualThreadPerTaskExecutor`) |
| Go              | Goroutines + `sync.WaitGroup`, scheduled on `GOMAXPROCS=2` |
| Node/NestJS     | A fixed `worker_threads` pool; split and fan-out tasks queue on it |
| C#/.NET         | `Task.Run` on the ThreadPool + `Task.WhenAll`, `DOTNET_PROCESSOR_COUNT=2` |

`nested` deliberately stacks A+B, producing more concurrent work than cores; each runtime
caps it differently (Go the `GOMAXPROCS` scheduler, Nest a fixed worker pool, Java the
virtual-thread carrier pool, C# the ThreadPool with `DOTNET_PROCESSOR_COUNT=2`).

### Fair 2-CPU budget

Every container runs under a uniform **2-CPU budget** so the cross-language comparison is
apples-to-apples. Beyond the `cpus: "2.0"` cgroup limit, each runtime is pinned **explicitly**
(in `docker-compose.yml`), because several size their parallelism from the *host* core count and
ignore the cgroup: `GOMAXPROCS=2` (Go — the key one), `WORKER_POOL_SIZE=2` (Nest), `JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2` (Java), `DOTNET_PROCESSOR_COUNT=2` (C#).
Python is already pinned via `uvicorn --workers 2` (and threads are GIL-bound). These env vars
apply to both `docker compose up` (live API) and `docker compose run` (the in-process benchmark).
