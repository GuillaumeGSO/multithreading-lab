# In-process concurrency benchmark

The Artillery suite in [`../load-tests/`](../load-tests/) measures **API/HTTP
handling**. This benchmark measures the other half: the **language
implementation** — the search algorithm and its in-process concurrency — by
calling the search functions directly inside each container, with no HTTP.

Every language runs the same canonical cases from [`cases.json`](cases.json)
(ported from `python-base/main.py`) and times each one per concurrency mode
with **warmup + median-of-N**, emitting a JSON report. [`aggregate.py`](aggregate.py)
combines the reports into `compare.html`.

## Run it

All commands assume you are in `benchmarks/`:

```bash
cd benchmarks
```

**Everything** — build all images, bench every service, build `compare.html`:

```bash
bash run-all.sh
```

**One service** (valid names: `python-base` `python-improved` `python-indexed` `go` `cpp` `java` `nest`):

```bash
bash run-all.sh go
```

**A subset** — only the languages you care about:

```bash
bash run-all.sh go cpp java
```

**More iterations** for a stabler median (default warmup 20 / iters 100):

```bash
BENCH_WARMUP=50 BENCH_ITERS=500 bash run-all.sh
```

**Higher split degree** — push axis B harder (default 2 = "halves"; 4 = quarters):

```bash
SPLIT_DEGREE=4 bash run-all.sh
```

**Combine knobs and target one service:**

```bash
BENCH_ITERS=500 SPLIT_DEGREE=4 bash run-all.sh go
```

**View the chart** after any run:

```bash
open compare.html
```

**Rebuild the chart only** (re-aggregate existing `results/*.json`, no re-bench):

```bash
python3 aggregate.py && open compare.html
```

Each runner prints **only** its JSON to stdout (logs → stderr); `run-all.sh`
redirects stdout to `results/<lang>.json` and stderr to `results/<lang>.log`.
If a service fails, its `.json` is removed and the error lands in
`results/<lang>.log`.

## Concurrency modes

Two independent axes, exposed as named modes:

| Mode | Axis | Meaning |
|------|------|---------|
| `baseline` | — | single-threaded scan |
| `split` | B | one file scanned in `SPLIT_DEGREE` contiguous chunks across threads |
| `fanout` | A | one thread/task per word length (`/search/many` only) |
| `nested` | A+B | per-length fan-out where each length is *also* split — threads spawning work |

`split` applies to `/search/file`; `fanout`/`nested` apply to `/search/many`.
The split degree is `SPLIT_DEGREE` (default 2 = "first half / second half").

Results are always merged in index/length order, so every mode returns
**byte-identical** output to `baseline` — verified by per-language unit tests.

## What to read in the chart

- **Sub-millisecond searches**: thread-creation/IPC overhead usually dominates,
  so `split`/`nested` rarely beat `baseline`. Push `SPLIT_DEGREE` and harder
  cases to change that.
- **Python** threads share the GIL → `split`/`nested` ≈ `baseline` (or slower).
  This is why **python-improved == python-base here**: its `uvicorn --workers 2`
  edge only exists under concurrent HTTP load, not in-process.
- **Go / C++** use real threads/goroutines → `nested` can oversubscribe the
  2-CPU box.
- **Nest** uses a fixed worker pool and **Java** uses virtual threads → the
  extra `nested` work queues/absorbs rather than exploding.

## Live API

The same parallel paths are wired into the running servers. `SEARCH_MODE`
(default `parallel`) selects them; `SEARCH_MODE=baseline` restores each
language's original endpoint behavior. `SPLIT_DEGREE` controls the chunk count.

## Files

- `cases.json` — canonical case definitions (single source of truth, baked into every image).
- `python_bench.py` — shared Python runner (copied into each python image as `bench.py`).
- Go/C++/Java/Nest runners live in their own trees (`go/bench/`, `cpp/src/bench.cpp`,
  `com.lab.search.BenchmarkRunner`, `nest/src/bench.ts`).
- `run-all.sh` — orchestrator. `aggregate.py` — chart generator. `results/` — output (gitignored).
