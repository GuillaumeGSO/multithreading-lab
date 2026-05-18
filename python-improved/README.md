# python-improved

Same brute-force search algorithm as `python-base`, but with the correct Python concurrency model for CPU-bound web work: **multiple OS worker processes**.

## Why not threads?

The original implementation used `ThreadPoolExecutor` to parallelize searches across word lengths. It performed *worse* than python-base because Python's GIL (Global Interpreter Lock) serializes CPU-bound bytecode execution across threads — threads add scheduling overhead without achieving real parallelism.

## The fix: uvicorn --workers 2

Two separate OS processes serve HTTP requests. Each process has its own Python interpreter and its own GIL, so they genuinely run in parallel on separate CPU cores. Concurrent requests are handled by different workers simultaneously, with no GIL contention between them.

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
