# Multithreading Lab

The same word search implemented five times, in **Python, Java, Go, Node/NestJS and C#**,
behind one OpenAPI contract. The goal is to see how each runtime expresses and runs
concurrent, CPU-bound work, under conditions kept as equal as possible.

This is a learning lab, not a ranking of languages. The numbers below are useful for
comparing concurrency models on this workload, on one machine. The
[limits](#limits-read-before-quoting-a-number) section says what they cannot tell you.

<!-- RESULTS -->

## The problem

Each service filters a dictionary (`assets/{lang}/{length}.txt`, about 425,000 French and
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
| **Total** | **416,270** | **426,694** |

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
