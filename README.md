# Multithreading Lab

[![CI](https://github.com/GuillaumeGSO/multithreading-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/GuillaumeGSO/multithreading-lab/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

The same word search implemented five times, in **Python, Java, Go, Node/NestJS and C#**,
behind one OpenAPI contract. The goal is to see how each runtime expresses and runs
concurrent, CPU-bound work, under conditions kept as equal as possible.

This is a learning lab, not a ranking of languages. The numbers below are useful for
comparing concurrency models on this workload, on one machine. The
[limits](#limits-read-before-quoting-a-number) section says what they cannot tell you.

## Results

Measured on 2026-10-08 on a 4-core, 8 GB laptop, with Docker Desktop given 3 CPUs and 4 GB.
Every service ran alone under its 2-CPU limit. Full reports:
[in-process benchmark](benchmarks/compare.html)
([rendered](https://htmlpreview.github.io/?https://github.com/GuillaumeGSO/multithreading-lab/blob/master/benchmarks/compare.html),
[summary](benchmarks/summary.md)) and
[load test](load-tests/compare-report.html)
([rendered](https://htmlpreview.github.io/?https://github.com/GuillaumeGSO/multithreading-lab/blob/master/load-tests/compare-report.html),
[summary](load-tests/summary.md)).

### In-process: the search itself, no HTTP

Geometric mean over all benchmark cases, in ms (lower is better). Each value is the median of
3 rounds. The spread between rounds is real: for these averages the slowest round is a median
of 17% slower than the fastest, and up to twice as slow when one round was disturbed. The
[summary](benchmarks/summary.md) gives every range. Below, a difference only counts as a
finding when the two ranges do not overlap.

| Language | file, `baseline` | file, `split` | many, `baseline` | many, `fanout` | many, `nested` | throughput (ops/s) |
|---|---:|---:|---:|---:|---:|---:|
| Python | 33.2 | 42.5 | 115.9 | 144.4 | 157.6 | 3.8 |
| Java | 0.54 | 0.71 | 2.00 | 1.68 | 1.97 | 270 |
| Go | 0.43 | 0.40 | 1.45 | 1.10 | 1.01 | 822 |
| Node/NestJS | 0.61 | 0.97 | 2.04 | 2.43 | 3.54 | 401 |
| C# | 0.50 | 0.72 | 2.34 | 2.03 | 1.45 | 470 |

All five return the same number of words for every one of the 122 cases.

### Over HTTP: Artillery at a constant 10 requests per second

Median and 95th-percentile latency, in ms, for `/search/many`, the heavier endpoint. This is
one round per mode, so treat the differences as indicative; `ROUNDS=3` gives ranges.

| Language | `baseline` p50 | `baseline` p95 | `parallel` p50 | `parallel` p95 | failed requests (`parallel`) |
|---|---:|---:|---:|---:|---:|
| Python | 5,168 | 12,460 | 1,064 | 15,219 | 600 |
| Java | 10.9 | 74.4 | 7.0 | 18.0 | 0 |
| Go | 4.0 | 10.1 | 4.0 | 8.9 | 0 |
| Node/NestJS | 7.9 | 22.9 | 7.9 | 22.9 | 0 |
| C# | 7.0 | 19.9 | 5.0 | 12.1 | 0 |

### What it shows

- **Splitting a short search does not pay.** A single-file scan takes about half a millisecond
  in the compiled and JIT runtimes. Splitting it in two makes Java and Node clearly slower,
  and probably C#, because starting and joining the work costs more than it saves. Go comes
  out about even.
- **Fanning out across word lengths does pay, if starting work is cheap.** `/search/many`
  does 1.4–2.3 ms of work. Go and C# gain clearly, with `nested` 30–38% faster than
  `baseline`. Java's gain is within the noise. Node gets slower with each level, because every
  task is a message to a worker thread.
- **The GIL makes Python threads a cost, not a gain.** Python's threaded modes are 25–36%
  slower than its single-threaded scan: the threads cannot run the scan in parallel, so they
  only add switching.
- **Interpreted Python is far slower on this loop.** Its scan is 60–70 times slower than the
  others. Under HTTP load it cannot keep up with 10 requests per second: latencies reach
  seconds, and in `parallel` mode 600 requests time out.
- **Per-request parallelism mostly helps the tail under load.** At 10 requests per second the
  other four answer `/search/many` in 4–11 ms at the median, which is mostly framework and
  JSON work on top of a 1–2 ms search. `parallel` cuts Java's p95 from 74 to 18 ms and C#'s
  from 20 to 12 ms; Go and Node barely change.
- **The positional index only pays off where the scan is slow.** With a pinned hint, Python's
  index is 5–24 times faster than its scan. In Java and C# it is about 2–5 times slower: all three
  implementations still walk every word to keep results in order, which costs more than the
  compiled scan's own check.


## The problem

Each service filters a dictionary (`assets/{lang}/{length}.txt`, about 427,000 French and
416,000 English words) by available letters, positional hints and word length.

- **`POST /search/file`** searches one word length.
- **`POST /search/many`** searches every length up to the number of letters, longest first.
- **`GET /health`** is a liveness check.

Each search is a CPU-bound filter over in-memory data. Work splits naturally two ways,
across word lengths and within one word list, which makes it a good subject for
comparing concurrency models.

## How the comparison is kept fair

- **One contract.** [`openapi.yaml`](openapi.yaml) defines the API, including input bounds.
  Every implementation generates its models from it and serves it unchanged.
- **One algorithm.** Every implementation runs the same scan. Each word's accent-free form
  and a–z letter counts are computed once when a word list loads. A query prepares its
  letter pool once, and only the checks the query needs are run. Python's scan is the
  reference.
- **One meaning per mode.** `SEARCH_MODE` selects the same strategy everywhere, and every
  service defaults to `parallel`:

  | `SEARCH_MODE` | `/search/file` | `/search/many` |
  |---|---|---|
  | `baseline` | single-threaded scan | single-threaded scan, lengths one after another |
  | `parallel` | scan split into 2 chunks on 2 threads | one thread or task per length, each also split |
  | `indexed` | positional index when a hint pins a letter, scan otherwise | single-threaded scan |

  `indexed` exists only in Python, Java and C#. It is reported separately, as an algorithm
  comparison, and never mixed into the concurrency results. An unknown mode stops the
  server at startup.
- **One CPU budget.** Every container is limited to 2 CPUs and 512 MB. Several runtimes
  size their thread pools from the host's core count rather than the container's limit, so
  each is also pinned explicitly in [`docker-compose.yml`](docker-compose.yml):

  | Implementation | Concurrency in `parallel` mode | Pin |
  |---|---|---|
  | Python | `threading` (the GIL lets one thread run Python code at a time) | `uvicorn --workers 2` |
  | Java | virtual threads | `-XX:ActiveProcessorCount=2` |
  | Go | goroutines + `sync.WaitGroup` | `GOMAXPROCS=2` |
  | Node/NestJS | a fixed pool of 2 `worker_threads` | `WORKER_POOL_SIZE=2` |
  | C# | `Task.Run` on the ThreadPool + `Task.WhenAll` | `DOTNET_PROCESSOR_COUNT=2` |

- **One set of inputs.** Every benchmark runs the same generated
  [`benchmarks/cases.json`](benchmarks/cases.json), and every load test the same
  [`load-tests/queries.csv`](load-tests/queries.csv). The benchmark report checks that every
  language returns the same number of words for every case.

## Limits: read before quoting a number

- **HTTP results measure the whole stack.** A search takes a few milliseconds, so the web
  framework, JSON handling and request scheduling are a large share of each request. The
  load test compares FastAPI/uvicorn, Spring/Tomcat, `net/http`, Fastify and Kestrel as much
  as it compares languages.
- **The code reflects its author.** I know some of these languages better than others. None
  of the implementations was tuned by an expert in that language.
- **Accent stripping differs slightly.** Python, Go and Node use a `unidecode` library;
  Java and C# use Unicode decomposition. The cross-language word-count check catches any case
  where this changes a result.
- **The machine is shared.** On macOS, Docker Desktop runs containers in a virtual machine,
  and the load generator runs on the same host. Numbers vary between runs; the reports show
  the spread across rounds.
- **The 2-CPU budget is a ceiling, not a reservation.** Each container may use up to 2 CPUs,
  but they all share the Docker VM's CPUs. Both runners measure one service at a time; keep
  everything else on Docker idle while they run. The results above used a 3-CPU VM, so the
  load generator, on the host, still competed with the service for the laptop's 4 cores.
- **One machine, one dataset.** The results compare models on this workload. They are not a
  general statement about the languages.
- **Python's `parallel` mode is slower than its `baseline` on purpose.** It runs the same mode
  as everyone else, so the GIL's effect is visible rather than hidden behind a different
  default.

## Repository layout

```
multithreading-lab/
├── openapi.yaml          # API contract, single source of truth (spec-first)
├── assets/               # Word lists: assets/{lang}/{length}.txt
├── benchmarks/           # In-process benchmark (no HTTP): rounds → compare.html, summary.md
├── load-tests/           # Artillery load test per SEARCH_MODE → compare-report.html, summary.md
├── python/               # FastAPI + uvicorn --workers 2 (Python 3.13)
├── java/                 # Spring Boot 4 + virtual threads (Java 25)
├── go/                   # net/http + goroutines
├── nest/                 # NestJS/Fastify + worker_threads pool (Node 22)
├── csharp/               # ASP.NET Core Minimal API + ThreadPool (.NET 10)
└── docker-compose.yml    # One service per implementation, 2 CPUs / 512 MB each
```

Each implementation has its own README: [Python](python/README.md), [Java](java/README.md),
[Go](go/README.md), [Node/NestJS](nest/README.md), [C#](csharp/README.md).

## Running it

```bash
docker compose up --build                      # all five services, SEARCH_MODE=parallel
SEARCH_MODE=baseline docker compose up -d go   # one service in another mode
```

| Implementation | Service | Port | API docs |
|---|---|---|---|
| Python | `python` | 8007 | [Swagger UI](http://localhost:8007/docs) |
| Java | `java` | 8002 | [Swagger UI](http://localhost:8002/docs) |
| Go | `go` | 8003 | [Swagger UI](http://localhost:8003/docs) |
| Node/NestJS | `nest` | 8006 | [Swagger UI](http://localhost:8006/docs) |
| C# | `csharp` | 8005 | [Scalar](http://localhost:8005/docs) |

Every service also serves the contract at `/openapi.yaml` and `/openapi.json`.

## Measuring

```bash
cd benchmarks && bash run-all.sh   # in-process, 3 rounds → compare.html + summary.md
cd load-tests && bash run-all.sh   # HTTP, baseline then parallel → compare-report.html + summary.md
```

The [benchmark README](benchmarks/README.md) and the [load-test README](load-tests/README.md)
describe the cases, the options and how to read the charts.

## API contract (spec-first)

The root [`openapi.yaml`](openapi.yaml) is the single source of truth. Each implementation
generates its models from it, serves it unchanged, and contains no hand-written OpenAPI
metadata. The wire format is camelCase JSON (`wordLength`, `letters`, `hints[].position`).
The contract also bounds every input: `lang` is `fr` or `en`, `wordLength` and hint
positions are 1–31, and requests carry at most 32 letters and 31 hints. Anything else is
answered with `400` and `{"error": "..."}`.

| Implementation | Model generation | Generated output | Committed? |
|---|---|---|---|
| Python | datamodel-code-generator → Pydantic v2 (enforces the bounds) | `python/generated/models.py` | no |
| Java | openapi-generator (`spring`, bean validation) | `java/target/generated-sources/openapi` | no |
| Go | oapi-codegen (models + `ServerInterface`) | `go/api/api.gen.go` | **yes** |
| Node/NestJS | openapi-typescript → TS types | `nest/src/generated/api.d.ts` | no |
| C# | NSwag (MSBuild) → DTOs with data annotations | `csharp/Api/obj/Generated/Contracts.g.cs` | no |

## Tests

Each implementation has a unit suite for the search logic, HTTP-level tests for request
validation, and tests asserting that every `SEARCH_MODE` returns exactly the baseline's
words. The Python suite is the correctness reference.

| Implementation | Command |
|---|---|
| Python | `cd python && uv run pytest` |
| Java | `cd java && mvn test` |
| Go | `cd go && go test ./...` |
| Node/NestJS | `cd nest && npm test && npm run test:integration` |
| C# | `cd csharp && dotnet test Tests/Tests.csproj` |

## Dataset

The word lists live in `assets/{lang}/{length}.txt` — one word per line, grouped by
length. Every implementation reads these same files, so the columns below are the
**dictionary languages**, not the implementation languages. Counts are words (lines)
per file; this is why the brute-force scan cost peaks around lengths 8–13 (each holds
50k–65k words) and the in-process benchmark leans on those lengths.

The English list comes from [dwyl/english-words](https://github.com/dwyl/english-words)
(`words.txt`, released into the public domain under the
[Unlicense](https://github.com/dwyl/english-words/blob/master/LICENSE.md)), lowercased,
deduplicated and split by word length. The French list was collected from a public GitHub
repository years ago and split the same way; its original source and license could not be
traced.

| Word length | en | fr |
|--:|--:|--:|
| 1 | 1 | 7 |
| 2 | 569 | 111 |
| 3 | 4,364 | 582 |
| 4 | 10,408 | 2,473 |
| 5 | 21,952 | 8,146 |
| 6 | 38,214 | 19,054 |
| 7 | 50,475 | 34,728 |
| 8 | 58,188 | 51,493 |
| 9 | 57,289 | 63,074 |
| 10 | 48,590 | 65,834 |
| 11 | 39,362 | 59,723 |
| 12 | 30,259 | 46,869 |
| 13 | 21,640 | 32,573 |
| 14 | 14,584 | 19,920 |
| 15 | 9,075 | 11,271 |
| 16 | 5,321 | 5,743 |
| 17 | 3,042 | 2,762 |
| 18 | 1,504 | 1,268 |
| 19 | 772 | 577 |
| 20 | 363 | 276 |
| 21 | 169 | 117 |
| 22 | 73 | 62 |
| 23 | 30 | 18 |
| 24 | 11 | 8 |
| 25 | 7 | 4 |
| 26 | — | 1 |
| 27 | 3 | — |
| 28 | 2 | — |
| 29 | 2 | — |
| 31 | 1 | — |
| **Total** | **416,269** | **426,687** |

Regenerate after changing the word lists:

```bash
for l in assets/*/; do for f in "$l"*.txt; do printf '%s\t%s\n' "$f" "$(wc -l < "$f")"; done; done
```

## History

A C++ implementation (cpp-httplib, `std::thread`) was part of the project and was removed:
I could not review it with the same confidence as the others. It remains in the git history (tag v1.1.0)

Earlier versions compared each language "at its best path": Python and Java served queries
from a positional index while the others scanned, and the scan itself was optimised in some
languages and not others. Those results mostly measured the algorithm differences. The
current setup runs the same algorithm and mode everywhere, and reports the index separately.

## Possible next steps

- Run the unit suites, spec linting ([Spectral](https://github.com/stoplightio/spectral)) and a
  `docker compose` smoke test in CI.
- Contract-test every service against `openapi.yaml` with
  [Schemathesis](https://schemathesis.readthedocs.io).
- Detect breaking spec changes on pull requests with [oasdiff](https://github.com/oasdiff/oasdiff).
- Run the load generator on a separate machine, to remove it from the measurement.
