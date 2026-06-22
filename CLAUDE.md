# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A personal learning project implementing the same word-search logic across Python, Java, Go, and C++ to compare concurrency models and performance under HTTP load. Each language exposes the same REST API in its own Docker container. Artillery load tests (`load-tests/artillery.yml`) are container-agnostic — only `--target` changes per language.

## Core Problem

The word search logic filters words from dictionary files (`assets/{lang}/{n}.txt`, where `n` = word length) by available letters, positional hints, and word length. **This logic and the API contract must stay consistent across all language implementations.**

## API Contract (all languages)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/search/file` | Search words of fixed length |
| `POST` | `/search/many` | Search words across all lengths |

## Structure

```
multithreading-lab/
├── assets/             # Shared word lists
├── load-tests/
│   └── artillery.yml   # Single test file, environments select the target
├── python/             # Python — strategy dispatcher (positional index ⟷ lean scan, both derive per-word data on the fly), uvicorn --workers 2
├── cpp/                # C++17, cpp-httplib, std::thread fan-out
├── nest/               # Node/NestJS, Fastify, worker_threads pool
├── docker-compose.yml  # Python=8007, Java=8002, Go=8003, C++=8004, Nest=8006
└── CLAUDE.md
```

## Per-implementation READMEs

Each directory has its own README covering local dev, Docker, and API details:
- [`python/README.md`](python/README.md)
- [`cpp/README.md`](cpp/README.md)
- [`nest/README.md`](nest/README.md)

## Load testing (API/HTTP)

`load-tests/artillery.yml` is the single test file for all implementations. Environments map names to ports — do not create per-language YAML files.

```bash
# Run all reachable containers and generate compare-report.html
cd load-tests && bash run-all.sh

# Run a single environment manually (requires npm install in load-tests/ first)
cd load-tests && npm run run:python
```

## In-process benchmark (algorithm + concurrency)

Artillery measures HTTP handling; [`benchmarks/`](benchmarks/) measures the language
implementation itself by calling the search functions directly **inside each container**
(no HTTP). All languages run the shared [`benchmarks/cases.json`](benchmarks/cases.json)
with warmup + median-of-N timing, per concurrency mode, and `aggregate.py` builds `compare.html`.

```bash
cd benchmarks && bash run-all.sh        # build images, bench every service, build compare.html
```

Two concurrency axes, exposed as named modes: **A** = per-length fan-out (`/search/many`),
**B** = intra-file split into `SPLIT_DEGREE` contiguous chunks (default 2). Modes: `baseline`
(neither), `split` (B, `/file`), `fanout` (A), `nested` (A+B). All modes return byte-identical
output to baseline (chunks/lengths merged in order — guarded by each impl's parallel unit tests).

The same parallel paths are **wired into the live API** via `SEARCH_MODE` and `SPLIT_DEGREE`.
Go/C++/Java/Nest default to `parallel` (real threads = their best path); `baseline` restores
original behavior. **Python is the exception:** its threads are GIL-bound, so it defaults to
the **index-aware dispatcher** (not `parallel`) — serving each language via its best path keeps
the HTTP comparison fair, and the dispatcher caches nothing per word so two `uvicorn` workers
fit the 512 MB budget. See [`benchmarks/README.md`](benchmarks/README.md).

## Unit tests

Each implementation has a `test_seek_words.py` pytest suite. Run the Python suite with:

```bash
cd python && uv run pytest -v
```

The suite must pass before and after any change to `seek_words.py`. The `python` suite is
the correctness reference; its `test_dispatch.py` additionally asserts the two strategies
return byte-identical output (so per-query dispatch can never change results) and the other
languages mirror these expected results.

## Concurrency models by implementation

| Implementation   | Model |
|-----------------|-------|
| Python          | Strategy dispatcher: `/search/file` runs the faster of a positional index (O(result) — used when a pinned hint can seed candidates) or a lean scan (O(vocabulary), cheap per-word); `/search/many` always scans (the index barely helps it but would cost pos_index for every length). Both strategies cache nothing per word — they derive letter data on the fly from the shared base — so two `uvicorn --workers 2` processes fit the 512 MB budget. Threads are GIL-bound (the `split`/`nested` modes demonstrate this) |
| Java            | `Thread`, `ExecutorService`, `java.util.concurrent` |
| Go              | Goroutines + `sync.WaitGroup` (per-length fan-out in `/search/many`) |
| C++             | `std::thread` fan-out per length + `std::mutex` for word cache |
| Node/NestJS     | `worker_threads` pool — N persistent workers; per-length fan-out in `/search/many` |

Each implementation additionally exposes an **intra-file split** (axis B) and a **nested** mode
(see the in-process benchmark section). The split uses each language's native primitive
(Python `threading` — GIL-bound; Go goroutines; C++ `std::thread`; Java virtual threads; Nest
worker-pool tasks). `nested` deliberately stacks A+B, producing more concurrent work than cores;
each runtime caps it differently (C++ a permit pool, Go the `GOMAXPROCS` scheduler, Nest a fixed
worker pool, Java the virtual-thread carrier pool).

### Fair 2-CPU budget

Every container runs under a uniform **2-CPU budget** so the cross-language comparison is
apples-to-apples. Beyond the `cpus: "2.0"` cgroup limit, each runtime is pinned **explicitly**
(in `docker-compose.yml`), because several size their parallelism from the *host* core count and
ignore the cgroup: `GOMAXPROCS=2` (Go — the key one), `CPU_BUDGET=2` (C++), `WORKER_POOL_SIZE=2`
(Nest), `JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2` (Java). Python is already pinned via
`uvicorn --workers 2` (and threads are GIL-bound). These env vars apply to both `docker compose up`
(live API) and `docker compose run` (the in-process benchmark).
