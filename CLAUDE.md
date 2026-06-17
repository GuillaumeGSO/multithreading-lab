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
├── python-base/        # Reference implementation (no concurrency)
├── python-improved/    # Python, same algorithm as base, uvicorn --workers 2
├── python-indexed/     # Python with pre-built positional + frequency indexes
├── cpp/                # C++17, cpp-httplib, std::thread fan-out
├── nest/               # Node/NestJS, Fastify, worker_threads pool
├── docker-compose.yml  # python-base=8000, python-improved=8001, python-indexed=8005, Java=8002, Go=8003, C++=8004, Nest=8006
└── CLAUDE.md
```

## Per-implementation READMEs

Each directory has its own README covering local dev, Docker, and API details:
- [`python-base/README.md`](python-base/README.md)
- [`python-improved/README.md`](python-improved/README.md)
- [`python-indexed/README.md`](python-indexed/README.md)
- [`cpp/README.md`](cpp/README.md)
- [`nest/README.md`](nest/README.md)

## Load testing (API/HTTP)

`load-tests/artillery.yml` is the single test file for all implementations. Environments map names to ports — do not create per-language YAML files.

```bash
# Run all reachable containers and generate compare-report.html
cd load-tests && bash run-all.sh

# Run a single environment manually (requires npm install in load-tests/ first)
cd load-tests && npm run run:python-base
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

The same parallel paths are **wired into the live API** via `SEARCH_MODE` (default `parallel`;
`baseline` restores original behavior) and `SPLIT_DEGREE`. See [`benchmarks/README.md`](benchmarks/README.md).

## Unit tests

Each implementation has a `test_seek_words.py` pytest suite. Run with:

```bash
cd python-base && .venv/bin/pytest -v
```

The test suite must pass before and after any change to `seek_words.py`. The `python-base` suite is the correctness reference — `python-improved` and `python-indexed` must produce identical results.

## Concurrency models by implementation

| Implementation   | Model |
|-----------------|-------|
| python-base     | None (single-threaded reference) |
| python-improved | Process-level scaling — `uvicorn --workers 2`; same brute-force algorithm as python-base |
| python-indexed  | Pre-built positional + frequency indexes; O(result) search instead of O(vocabulary) |
| Java            | `Thread`, `ExecutorService`, `java.util.concurrent` |
| Go              | Goroutines + `sync.WaitGroup` (per-length fan-out in `/search/many`) |
| C++             | `std::thread` fan-out per length + `std::mutex` for word cache |
| Node/NestJS     | `worker_threads` pool — N persistent workers; per-length fan-out in `/search/many` |

Each implementation additionally exposes an **intra-file split** (axis B) and a **nested** mode
(see the in-process benchmark section). The split uses each language's native primitive
(Python `threading` — GIL-bound; Go goroutines; C++ `std::thread`; Java virtual threads; Nest
worker-pool tasks). `nested` deliberately stacks A+B: raw-thread languages (Go/C++) oversubscribe,
while pool/virtual-thread languages (Nest/Java) queue or absorb the extra work.
