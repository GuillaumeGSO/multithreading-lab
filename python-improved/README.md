# python-improved

Same brute-force search algorithm as `python-base`, but with the correct Python concurrency model for CPU-bound web work: **multiple OS worker processes**.

## Why not threads?

The original implementation used `ThreadPoolExecutor` to parallelize searches across word lengths. It performed *worse* than python-base because Python's GIL (Global Interpreter Lock) serializes CPU-bound bytecode execution across threads — threads add scheduling overhead without achieving real parallelism.

## The fix: uvicorn --workers 2

Two separate OS processes serve HTTP requests. Each process has its own Python interpreter and its own GIL, so they genuinely run in parallel on separate CPU cores. Concurrent requests are handled by different workers simultaneously, with no GIL contention between them.

> **Note:** This is configured with **2 CPUs and 2 workers** — the container is
> given `cpus: "2.0"` in `docker-compose.yml` to match `--workers 2`. The worker
> count and the CPU limit must match: extra workers on a 1-CPU container only
> add context-switching overhead, while extra CPUs with one worker go unused
> (the GIL keeps a single process on a single core for CPU-bound work).
> `python-base` stays at 1 CPU / 1 worker, so `python-improved` vs `python-base`
> is a clean 2-core-vs-1-core comparison.

## How each implementation isolates one variable

| Implementation | Algorithm | Concurrency model |
|---|---|---|
| python-base | brute force O(vocab) | none |
| python-improved | brute force O(vocab) | 2 uvicorn OS workers |
| python-indexed | index O(result) | none |

This makes the load test results directly comparable: python-improved vs python-base measures the concurrency gain; python-indexed vs python-base measures the algorithm gain.

## Port

Runs on **8001**.

## Local dev

```bash
uv sync
uv run pytest -v
uv run uvicorn api:app --port 8001
```

## Docker

```bash
docker compose up python-improved
```
