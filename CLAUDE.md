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
├── python-improved/    # Python with threading/concurrent.futures
├── python-indexed/     # Python with pre-built positional + frequency indexes
├── docker-compose.yml  # python-base=8000, python-improved=8001, python-indexed=8005, Java=8002, Go=8003, C++=8004
└── CLAUDE.md
```

## Per-implementation READMEs

Each directory has its own README covering local dev, Docker, and API details:
- [`python-base/README.md`](python-base/README.md)
- [`python-improved/README.md`](python-improved/README.md)
- [`python-indexed/README.md`](python-indexed/README.md)

## Load testing

`load-tests/artillery.yml` is the single test file for all implementations. Environments map names to ports — do not create per-language YAML files.

```bash
# Run all reachable containers and generate compare-report.html
cd load-tests && bash run-all.sh

# Run a single environment manually (requires npm install in load-tests/ first)
cd load-tests && npm run run:python-base
```

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
| python-improved | `threading`, `concurrent.futures` (GIL-constrained for CPU work) |
| python-indexed  | Pre-built positional + frequency indexes; O(result) search instead of O(vocabulary) |
| Java            | `Thread`, `ExecutorService`, `java.util.concurrent` |
| Go              | Goroutines + channels |
| C++             | `std::thread`, `std::mutex`, atomics |
