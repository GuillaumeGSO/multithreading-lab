# Java — search service

Java implementation of the multithreading lab word-search API.

**Stack**: Spring Boot 4.0 · Java 25 (LTS) · Maven · virtual threads (Project Loom) · Jackson 3

## Concurrency model

Virtual threads are used at two independent levels:

1. **HTTP layer** — `spring.threads.virtual.enabled=true` makes Tomcat dispatch each incoming request on its own virtual thread, so all endpoints handle concurrent requests without a fixed thread pool
2. **Search layer** — `WordSearchService.searchInManyFiles` spawns one virtual thread per word length via `Executors.newVirtualThreadPerTaskExecutor()`, so all file scans for a single `/search/many` request run in parallel and results are collected in longest-first order

### Parallel modes & in-process benchmark

`WordSearchService` also adds an **intra-file split** (`fileSplit` — virtual
threads over contiguous chunks) and a **nested** mode (`manyNested` — per-length
fan-out where each length is also split). `SEARCH_MODE=parallel` (default) routes
`/search/file` → split and `/search/many` → nested; `SEARCH_MODE=baseline`
restores the original fan-out. Virtual threads are cheap, so `nested` is absorbed
by the carrier pool rather than exploding. Output is identical to baseline
(`WordSearchServiceTest` asserts it).

```bash
# Cross-language chart (from repo root)
cd benchmarks && bash run-all.sh
# This implementation's runner (plain main via the Boot jar's PropertiesLauncher):
docker compose run --rm --entrypoint java java \
  -Dloader.main=com.lab.search.BenchmarkRunner -cp /app/app.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher
```

## Structure

```
java/
├── src/
│   ├── main/java/com/lab/search/
│   │   ├── SearchApplication.java
│   │   ├── controller/SearchController.java
│   │   ├── service/WordSearchService.java
│   │   └── model/               # Hint, SearchFileRequest, SearchManyRequest, SearchResponse
│   └── test/java/com/lab/search/
│       └── service/WordSearchServiceTest.java
├── src/main/resources/application.properties
├── Dockerfile
└── pom.xml
```

## Local development

Requires Java 25+ and Maven 3.9+.

```bash
# From repo root — run the API locally
ASSETS_ROOT=assets mvn -f java/pom.xml spring-boot:run

# The API starts on http://localhost:8002
```

## Docker

```bash
# Build and run (from repo root)
docker compose up java --build

# Or build the image directly
docker build -f java/Dockerfile -t seek-words-java .
docker run -p 8002:8002 seek-words-java
```

The runtime image launches with `-XX:+UseCompactObjectHeaders` (a JDK 25 product
flag, JEP 519) to shrink object headers and lower the heap footprint of the
in-memory word lists.

## Unit tests

34 tests mirroring the Python pytest suite — unit tests for content/hint matching, integration tests against the real asset files, and equivalence tests asserting the parallel modes (`fileSplit`, `manyNested`) return byte-identical results to the baseline.

```bash
# Run from the java/ directory (Maven sets the working directory there)
docker run --rm -v $(pwd):/workspace -w /workspace/java \
  maven:3.9-eclipse-temurin-25 mvn test
```

## API

### `GET /health`

```json
{"status": "ok"}
```

### `POST /search/file`

Search words of a fixed length using available letters and/or positional hints.

```json
// Request
{
  "lang": "fr",
  "nb_car": 5,
  "lst_car": ["e","l","i","s","a"],
  "lst_hint": [
    {"pos": 1, "car": "s", "inverted": false}
  ],
  "strict": false
}

// Response
{"words": ["ailes", "alise", ...], "count": 8}
```

### `POST /search/many`

Search words across all lengths up to `len(cars)`, results ordered longest-first.

```json
// Request
{"lang": "fr", "cars": "guillaume", "lst_hint": []}

// Response
{"words": [...], "count": 494}
```

### Errors

A request with neither `lst_car` nor `lst_hint` returns `400` as an
RFC 9457 `application/problem+json` body:

```json
{"type": "about:blank", "title": "Bad Request", "status": 400,
 "detail": "Either lst_car or lst_hint must be provided"}
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ASSETS_ROOT` | `assets` (relative) | Path to the word list directory |
| `SEARCH_MODE` | `parallel` | `parallel` routes the API through split/nested; `baseline` restores the original fan-out |
| `SPLIT_DEGREE` | `2` | Intra-file chunk count for `split`/`nested` |

## Load test results (2026-05-15)

| Endpoint | p50 | p95 | p99 |
|----------|-----|-----|-----|
| `/health` | 2 ms | 144 ms | 147 ms |
| `/search/file` | 17 ms | 150 ms | 206 ms |
| `/search/many` | 219 ms | 327 ms | 424 ms |

0 failures across 1880 requests at up to 20 req/s. See [compare-report.html](../load-tests/compare-report.html) for the full comparison.
