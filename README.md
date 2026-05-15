# Multithreading Lab

A personal learning project to experiment with multithreading across multiple languages using the **same logic and assets** in each implementation.

## Goal

Implement, then progressively optimize, identical concurrent programs in:

- **Python** ✅ (baseline + improved + indexed)
- **Java** ✅ (virtual threads)
- **Go** _(planned)_
- **C++** _(planned)_

The intent is to observe and compare how each language expresses concurrency, what primitives it provides, and how performance characteristics differ — not to build something production-ready.

## Problem

Each implementation exposes a word-search API over a shared dictionary dataset (`assets/`). Queries filter words by available letters, positional hints, and word length. The workload is CPU-bound filtering over in-memory data — a good fit for observing threading models under load.

## Approach

Each language gets a baseline directory and an improved directory, both wrapping the same search logic behind the same HTTP API:

1. **Baseline** (`*-base`) — straightforward single-threaded solution, used as the reference
2. **Improved** (`*-improved`) — applying language-specific concurrency techniques (thread pools, lock-free structures, async runtimes, etc.)

## Structure

```
multithreading-lab/
├── assets/                  # Shared word lists: assets/{lang}/{nb_letters}.txt
├── load-tests/
│   ├── artillery.yml        # Single test file, environments select the target
│   ├── run-all.sh           # Runs Artillery against all reachable containers
│   ├── compare.py           # Generates compare-report.html from results/
│   └── results/             # Per-run JSON outputs (gitignored)
├── python-base/             # Reference implementation — no concurrency
├── python-improved/         # Python with threading / concurrent.futures
├── python-indexed/          # Python with pre-built positional + frequency indexes
├── java/                    # Spring Boot + virtual threads (Java 21)
├── go/                      # (planned)
├── cpp/                     # (planned)
└── docker-compose.yml       # One service per implementation
```

## API contract

All containers expose the same three endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/search/file` | Search words of a fixed length |
| `POST` | `/search/many` | Search words across all lengths |

See any implementation's README for request/response schemas.

## Running containers

```bash
# Start all implemented containers
docker compose up --build

# Start a specific implementation
docker compose up python-base
docker compose up python-improved
```

| Implementation   | Port |
|-----------------|------|
| python-base     | 8000 |
| python-improved | 8001 |
| Java            | 8002 |
| Go              | 8003 |
| C++             | 8004 |

## Load testing

Artillery runs the same scenarios against every container. Results are collected and compared in a single HTML report: [compare-report.html](load-tests/compare-report.html).

```bash
# Run against all reachable containers and generate the comparative report
cd load-tests && bash run-all.sh
# → load-tests/compare-report.html

# Run against a single implementation
npx artillery run --environment python-base load-tests/artillery.yml
npx artillery run --environment python-improved load-tests/artillery.yml
```

The test mix covers 8 scenarios (6 × `search/file`, 2 × `search/many`) with weights biased toward lighter queries.

## Unit tests

Each implementation has its own pytest suite covering the core search logic:

```bash
cd python-base && .venv/bin/pytest -v
cd python-improved && .venv/bin/pytest -v
```

## Languages & threading models

| Implementation   | Concurrency model |
|-----------------|-------------------|
| python-base     | None (reference) |
| python-improved | `threading`, `concurrent.futures` (GIL-constrained for CPU work) |
| Java            | `Thread`, `ExecutorService`, `java.util.concurrent` |
| Go              | Goroutines + channels |
| C++             | `std::thread`, `std::mutex`, atomics |
