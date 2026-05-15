# Multithreading Lab

A personal learning project to experiment with multithreading across multiple languages using the **same logic and assets** in each implementation.

## Goal

Implement, then progressively optimize, identical concurrent programs in:

- **Python** ✅
- **Java** _(planned)_
- **Go** _(planned)_
- **C++** _(planned)_

The intent is to observe and compare how each language expresses concurrency, what primitives it provides, and how performance characteristics differ — not to build something production-ready.

## Problem

Each implementation exposes a word-search API over a shared dictionary dataset (`assets/`). Queries filter words by available letters, positional hints, and word length. The workload is CPU-bound filtering over in-memory data — a good fit for observing threading models under load.

## Approach

Each language gets its own directory with a self-contained HTTP API wrapping the same search logic. Implementations go through two phases:

1. **Baseline** — a straightforward multithreaded solution
2. **Optimized** — applying language-specific techniques (thread pools, lock-free structures, async runtimes, etc.)

## Structure

```
multithreading-lab/
├── assets/              # Shared word lists: assets/{lang}/{nb_letters}.txt
├── load-tests/
│   └── artillery.yml    # Language-agnostic load test (change --target per container)
├── python/              # Python implementation (FastAPI + uvicorn)
├── java/                # (planned)
├── go/                  # (planned)
├── cpp/                 # (planned)
└── docker-compose.yml   # One service per language
```

## API contract

All containers expose the same three endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/search/file` | Search words of a fixed length |
| `POST` | `/search/many` | Search words across all lengths |

See any language's README for request/response schemas.

## Running containers

```bash
# Start all implemented containers
docker compose up --build

# Start a specific language
docker compose up python
```

| Language | Port |
|----------|------|
| Python   | 8000 |
| Java     | 8001 |
| Go       | 8002 |
| C++      | 8003 |

## Load testing

Artillery is used to load test each container with identical scenarios.

```bash
# Install Artillery (one-time)
npm install -g artillery

# Run against Python
artillery run --target http://localhost:8000 load-tests/artillery.yml

# Run against Java (once implemented)
artillery run --target http://localhost:8001 load-tests/artillery.yml
```

The test mix covers 7 scenarios (6 × `search/file`, 1 × `search/many`) with weights biased toward lighter queries. The heavy multi-length query (`search/many`) has weight 1 vs. weight 4 for the others.

## Languages & threading models

| Language | Primary concurrency model |
|----------|--------------------------|
| Python   | `threading`, `concurrent.futures`, GIL constraints |
| Java     | `Thread`, `ExecutorService`, `java.util.concurrent` |
| Go       | Goroutines + channels |
| C++      | `std::thread`, `std::mutex`, atomics |
