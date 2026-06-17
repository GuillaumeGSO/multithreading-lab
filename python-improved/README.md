# python-improved

Two changes over `python-base`, both about *throughput without changing the search semantics*:

1. **The correct Python concurrency model for CPU-bound web work** — multiple OS worker processes (`uvicorn --workers 2`).
2. **A word index built on load.** Each word file is parsed once into `(word, normalized, Counter)` tuples (see `_load_word_indexes` in [`seek_words.py`](seek_words.py)), so per-request scans reuse the precomputed unidecode-normalized form and character `Counter` instead of recomputing them every time `is_search_by_content` runs.

The scan is still O(vocabulary) — this is *not* python-indexed's positional/frequency index (which is O(result)). It is a lighter "index on load" variant: same candidate set, cheaper per-word work. Results stay byte-identical to `python-base` (guarded by the shared integration tests).

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
| python-base | brute force O(vocab), normalize per scan | none |
| python-improved | brute force O(vocab), per-word `(normalized, Counter)` indexed on load | 2 uvicorn OS workers |
| python-indexed | positional + frequency index O(result) | none |

python-indexed vs python-base isolates the *algorithmic* (O(result)) gain. python-improved
mixes two cheaper wins — the on-load per-word index and process-level scaling — so it sits
between the two: faster than base in-process from the index alone, and faster again under
concurrent HTTP load from the extra worker.

## In-process benchmark

The cross-language in-process benchmark ([`../benchmarks/`](../benchmarks/)) calls the
search functions directly, with no HTTP. The `--workers 2` advantage is **process-level**
and exists only under concurrent HTTP load, so it does not show up here — but the **on-load
index does**: per-request scans skip re-normalizing each word, so in-process python-improved
runs faster than python-base while returning identical results.

`parallel.py` consumes that same on-load index (`_load_word_indexes`): its threaded
`split`/`nested` modes (selected by `SEARCH_MODE=parallel` / `SPLIT_DEGREE`) demonstrate the
GIL wall this README is about — they add thread overhead without CPU parallelism. Run via
`docker compose run --rm --entrypoint .venv/bin/python python-improved bench.py`.

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_MODE` | `parallel` | `parallel` uses the threaded variants; `baseline` the single-threaded path |
| `SPLIT_DEGREE` | `2` | Intra-file chunk count for `split`/`nested` |

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
