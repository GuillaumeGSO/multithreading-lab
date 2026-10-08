# Java — search service

Java implementation of the multithreading lab word-search API.

**Stack**: Spring Boot 4.0 · Java 25 (LTS) · Maven · virtual threads (Project Loom) · Jackson 3

## Concurrency model

Virtual threads are used at two independent levels:

1. **HTTP layer** — `spring.threads.virtual.enabled=true` makes Tomcat dispatch each incoming request on its own virtual thread, so all endpoints handle concurrent requests without a fixed thread pool
2. **Search layer** — `WordSearchService.searchInManyFiles` spawns one virtual thread per word length via `Executors.newVirtualThreadPerTaskExecutor()`, so all file scans for a single `/search/many` request run in parallel and results are collected in longest-first order

### Algorithm dispatch (baseline mode)

`SEARCH_MODE=baseline` also selects the search algorithm per request:

- **`IndexedStrategy`** — builds a positional inverted index (`position → letter → Set<word>`) per `(lang, wordLength)` on first use. For queries with at least one pinned hint (non-excluded, non-null `letter`), it seeds a tight candidate set by intersecting index buckets — O(result) instead of O(vocabulary). Wins 3–38× over scan when pinned hints are present.
- **`ScanStrategy`** — iterates the full word list on every query. Wins 1.4–2.4× when no pinned hints are present (no index overhead, zero caching).

The dispatch rule: `IndexedStrategy` is chosen when any `Hint` has `letter != null && !excluded`; `ScanStrategy` otherwise. `/search/many` always uses scan (building an index per length would be wasteful).

### Parallel modes & in-process benchmark

`WordSearchService` also adds an **intra-file split** (`fileSplit` — virtual
threads over contiguous chunks) and a **nested** mode (`manyNested` — per-length
fan-out where each length is also split). `SEARCH_MODE=parallel` (default) routes
`/search/file` → split and `/search/many` → nested; `SEARCH_MODE=baseline`
restores the original fan-out with algorithm dispatch. Virtual threads are cheap,
so `nested` is absorbed by the carrier pool rather than exploding. Output is
identical to baseline (`WordSearchServiceTest` asserts it).

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
│   │   ├── BenchmarkRunner.java
│   │   ├── controller/
│   │   │   ├── SearchController.java     # implements the generated HealthApi + SearchApi
│   │   │   └── OpenApiController.java    # serves openapi.yaml/.json and the /docs page
│   │   └── service/
│   │       ├── Hint.java                 # the algorithm's hint record
│   │       ├── WordSearchService.java
│   │       └── strategy/
│   │           ├── SearchStrategy.java   # interface
│   │           ├── ScanStrategy.java     # flat scan (stateless)
│   │           └── IndexedStrategy.java  # positional index (self-cached)
│   └── test/java/com/lab/search/
│       └── service/WordSearchServiceTest.java
├── src/main/resources/application.properties
├── target/generated-sources/openapi/   # GENERATED at build time (never committed)
├── Dockerfile
└── pom.xml
```

## API contract (spec-first)

The repository's [`openapi.yaml`](../openapi.yaml) is the only definition of the API;
no OpenAPI annotation is written by hand.

- **Interfaces and models** — the
  [openapi-generator](https://openapi-generator.tech) Maven plugin (`spring` generator,
  7.25.0) runs in the `generate-sources` phase and writes `com.lab.search.api.HealthApi`,
  `com.lab.search.api.SearchApi` and the `com.lab.search.api.model.*` classes to
  `target/generated-sources/openapi`. Spec descriptions become Javadoc.
  `SearchController` implements both interfaces, so routes, HTTP methods, request bodies
  and response types are all taken from the contract. The controller maps the
  generated `Hint` model onto the algorithm's own `service.Hint` record.
- **Generator options** (`pom.xml`): `interfaceOnly`, `useSpringBoot4`, `useJakartaEe`,
  `useTags`, `useBeanValidation`, no nullable wrapper, no documentation annotations.
  The spec's constraints become `@NotNull` / `@Min` / `@Max` / `@Size` on the models
  and `@Valid` on the request bodies, enforced by `spring-boot-starter-validation`.
  `JsonConfig` turns off Jackson's lenient coercions (number → string, 5.5 → 5).
- **Spec and docs** — `maven-resources-plugin` copies `openapi.yaml` onto the classpath.
  `OpenApiController` serves it unchanged at `/openapi.yaml`, converts it to JSON at
  `/openapi.json`, and serves a Swagger UI page at `/docs`. The UI assets come from the
  `swagger-ui` webjar, so `/docs` works offline.
- **Errors** — constraint violations, unreadable bodies (including an unknown `lang`)
  and `IllegalArgumentException` answer `400` with the generated `ErrorResponse`.
  Parser messages are not echoed. Any other failure is logged and answered with a
  generic `500` `ErrorResponse`.

Nothing generated is committed: any Maven build (`mvn compile`, `mvn test`,
`mvn package`) regenerates from `../openapi.yaml`, so a spec change takes effect on the
next build. The pom reads the spec from one directory up, so build from inside the
repository (the Dockerfile mirrors that layout).

## Local development

Requires Java 25+ and Maven 3.9+.

```bash
# From repo root — run the API locally
ASSETS_ROOT=assets mvn -f java/pom.xml spring-boot:run

# The API starts on http://localhost:8002 (Swagger UI at /docs)
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

41 tests — unit tests for content/hint matching, integration tests against the real asset files, equivalence tests asserting the parallel modes (`fileSplit`, `manyNested`) return byte-identical results to the baseline, and strategy tests verifying that `IndexedStrategy` returns byte-identical output to `ScanStrategy` and that `fileDispatch` routes correctly.

```bash
# From the repo root (the build needs ../openapi.yaml, so mount the whole repo)
docker run --rm -v $(pwd):/workspace -w /workspace/java \
  maven:3.9-eclipse-temurin-25 mvn test
```

## API

The contract is the repository's [`openapi.yaml`](../openapi.yaml); browse it at
`/docs` (Swagger UI) or fetch it from `/openapi.json` / `/openapi.yaml`.

### `GET /health`

```json
{"status": "ok"}
```

### `POST /search/file`

Words of exactly `wordLength` characters built from `letters` and/or matching the
positional `hints`.

```json
// Request
{
  "lang": "fr",
  "wordLength": 5,
  "letters": ["e","l","i","s","a"],
  "hints": [
    {"position": 1, "letter": "s", "excluded": false}
  ],
  "strict": false
}

// Response
{"words": ["saisi", "salai", "salas", ...], "count": 20}
```

### `POST /search/many`

Words of every length up to the number of `letters`, ordered longest-first.

```json
// Request
{"lang": "fr", "letters": "guillaume", "hints": []}

// Response
{"words": ["aiguillai", "aiguillee", ...], "count": 494}
```

### Errors

An invalid request answers `400` with the contract's `ErrorResponse`. That covers
malformed JSON, a wrong field type, any value outside the bounds in `openapi.yaml`
(`lang` other than `fr`/`en`, `wordLength` or a hint `position` outside 1–31, more
than 32 letters or 31 hints), and a request with neither `letters` nor `hints`:

```json
{"error": "letters and hints cannot both be empty"}
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ASSETS_ROOT` | `assets` (relative) | Path to the word list directory |
| `SEARCH_MODE` | `parallel` | `parallel` routes `/search/file` → split and `/search/many` → nested; `baseline` uses algorithm dispatch (indexed or scan based on hints) |
| `SPLIT_DEGREE` | `2` | Intra-file chunk count for `split`/`nested` |

## Load test results (2026-05-15)

| Endpoint | p50 | p95 | p99 |
|----------|-----|-----|-----|
| `/health` | 2 ms | 144 ms | 147 ms |
| `/search/file` | 17 ms | 150 ms | 206 ms |
| `/search/many` | 219 ms | 327 ms | 424 ms |

0 failures across 1880 requests at up to 20 req/s. See [compare-report.html](../load-tests/compare-report.html) for the full comparison.
