# Java — search service

Java implementation of the multithreading lab word-search API.

**Stack**: Spring Boot 4.0 · Java 25 (LTS) · Maven · virtual threads (Project Loom) · Jackson 3

## Concurrency model

Virtual threads are used at two independent levels:

1. **HTTP layer** — `spring.threads.virtual.enabled=true` makes Tomcat dispatch each incoming request on its own virtual thread, so all endpoints handle concurrent requests without a fixed thread pool
2. **Search layer** — in the `parallel` mode, `/search/file` splits the word list into `SPLIT_DEGREE` chunks (`fileSplit`), and `/search/many` runs one virtual thread per word length, each length also split (`manyNested`), all on `Executors.newVirtualThreadPerTaskExecutor()`. Results are merged in word-list and longest-first order.

### Modes (`SEARCH_MODE`)

| Mode | `/search/file` | `/search/many` |
|---|---|---|
| `baseline` | single-threaded scan (`fileBaseline`) | single-threaded scan, lengths one after another (`manyBaseline`) |
| `parallel` (default) | split across virtual threads (`fileSplit`) | per-length fan-out, each length split (`manyNested`) |
| `indexed` | dispatcher (`fileDispatch`): `IndexedStrategy` when a pinned hint exists, `ScanStrategy` otherwise | single-threaded scan (`manyBaseline`) |

`SearchMode` parses the value; anything else stops the application at startup. Every mode
returns the same words in the same order (`SearchModeTest` asserts it).

### Scan and index

- **Scan** — each word list is loaded once into `WordEntry` records (word, accent-free form,
  26-letter count). A query builds one immutable `LetterPool` and tests each entry against
  it, so the per-word check allocates nothing.
- **`IndexedStrategy`** — builds a positional inverted index (`position → letter → Set<word>`) per `(lang, wordLength)` on first use. For queries with at least one pinned hint (non-excluded, non-null `letter`), it seeds a tight candidate set by intersecting index buckets — O(result) instead of O(vocabulary).

Virtual threads are cheap, so `nested` work is absorbed by the carrier pool rather than
exploding.

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
| `SEARCH_MODE` | `parallel` | `baseline`, `parallel` or `indexed` (see [Modes](#modes-search_mode)) |
| `SPLIT_DEGREE` | `2` | Intra-file chunk count for `split`/`nested` |
