# C# / .NET 10 implementation

ASP.NET Core 10 Minimal API. Uses `Task.WhenAll` + `Task.Run` (ThreadPool) for CPU-bound
parallelism, with a per-query strategy dispatcher (positional index ↔ lean scan) for the
single-threaded path.

Port: **8005**

## Local dev

Requires the .NET 10 SDK.

```bash
cd csharp/Api
dotnet run          # starts on http://localhost:8005 — Scalar API reference at /docs
dotnet watch run    # auto-reload on file changes
```

`launchSettings.json` pre-sets `ASSETS_ROOT=../../assets`, `PORT=8005`,
`SEARCH_MODE=parallel`, `SPLIT_DEGREE=2` — no env vars to type. The first build generates
the API contracts (see below).

## API contract (spec-first)

The repository's [`openapi.yaml`](../openapi.yaml) is the only definition of the API.
Nothing about the contract is hand-written here: no model classes, no `.WithSummary` /
`.WithDescription`, no `AddOpenApi` document generation.

- **DTOs** — [NSwag](https://github.com/RicoSuter/NSwag) (`NSwag.MSBuild` 14.7.1, its
  `Net100` tool) runs as the `GenerateContracts` MSBuild target before every build in
  which the spec changed. It writes `obj/Generated/Contracts.g.cs` (namespace
  `WordSearch.Api.Contracts`): `SearchFileRequest`, `SearchManyRequest`,
  `SearchResponse`, `Hint`, `HealthResponse`, `ErrorResponse`. Properties are PascalCase
  with `[JsonPropertyName]` carrying the spec's camelCase names, and defaults such as
  `Lang = "fr"` come from the schema.
- **Documentation in code** — NSwag copies every spec `description` into `/// <summary>`
  on the generated DTOs. `GenerateDocumentationFile` stays on, so IntelliSense shows the
  contract text. In short, the spec documents the API and the generated XML docs
  document the code. Hand-written members are not required to carry XML docs
  (`CS1591` is suppressed).
- **Endpoints** — `Program.cs` binds the generated request DTOs and returns
  `TypedResults` (`Ok<SearchResponse>` / `BadRequest<ErrorResponse>`). The generated
  `Hint` is mapped onto the algorithm's own `Search.Hint` record.
- **Validation** — NSwag runs with `GenerateDataAnnotations`, so the spec's bounds become
  `[Range]` / `[MaxLength]` / `[StringLength]` / `[Required]`. `RequestValidation`
  checks them, including each hint, and an unknown `lang` fails JSON binding. Both answer
  `400` with `ErrorResponse`. Unreadable JSON also answers `400` (`ThrowOnBadRequest` +
  a small middleware), bodies over 64 KiB `413`, and any other failure a generic `500`.
- **Spec and docs** — `OpenApiSpec` loads `openapi.yaml` (`OPENAPI_PATH`) once at
  startup. It is served unchanged at `/openapi.yaml`, converted to JSON (YamlDotNet) at
  `/openapi.json`, and the Scalar API reference at `/docs` reads `/openapi.json`.

`obj/` is never committed. The generated file is rebuilt automatically, so after changing
`openapi.yaml` just build again (`dotnet build`, `dotnet test`, `dotnet run`). The
target reads the spec from `../../openapi.yaml` relative to `Api/`, so build from inside
the repository (the Dockerfile mirrors that layout).

## Tests

```bash
cd csharp
dotnet test Tests/Tests.csproj -v normal
```

`ASSETS_ROOT` defaults to the repository's `assets/` (resolved from the test binaries'
location), so no env var is needed. `InternalsVisibleTo` exposes the internal scan
helpers to the test assembly.

## Docker

```bash
# From repo root
docker compose build csharp
docker compose up csharp -d
curl http://localhost:8005/health
```

The runtime image installs `icu-libs` and disables globalization-invariant mode:
accent stripping (`é` → `e`) relies on Unicode normalization (`FormD`), which needs ICU.

## API

The contract is the repository's [`openapi.yaml`](../openapi.yaml); browse it at
`/docs` (Scalar) or fetch it from `/openapi.json` / `/openapi.yaml`.

| Method | Path | Request | Response |
|--------|------|---------|----------|
| `GET` | `/health` | — | `HealthResponse` `{"status": "ok"}` |
| `POST` | `/search/file` | `SearchFileRequest` `{"wordLength": 5, "letters": ["e","l","i","s","a"], "hints": [{"position": 1, "letter": "s"}]}` | `SearchResponse` `{"words": ["saisi", …], "count": 20}` |
| `POST` | `/search/many` | `SearchManyRequest` `{"letters": "guillaume", "hints": []}` | `SearchResponse` `{"words": ["aiguillai", …], "count": 494}` |

An invalid request (malformed JSON, `wordLength` of 0, or neither `letters` nor `hints`)
answers `400` with `ErrorResponse` `{"error": "letters and hints cannot both be empty"}`.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ASSETS_ROOT` | repo `assets/` (local) / `/app/assets` (Docker) | Word list directory |
| `OPENAPI_PATH` | repo `openapi.yaml` (local) / `/app/openapi.yaml` (Docker) | API contract served at `/openapi.*` and `/docs` |
| `PORT` | `8005` | HTTP listen port |
| `SEARCH_MODE` | `parallel` | `parallel` = Task.WhenAll fan-out; `baseline` = strategy dispatcher |
| `SPLIT_DEGREE` | `2` | Chunks per file for intra-file split (axis B) |
| `DOTNET_PROCESSOR_COUNT` | host CPUs | Pin thread pool to N cores (set to `2` in docker-compose) |

## Concurrency modes

| Mode | Axis | Description |
|------|------|-------------|
| `baseline` | — | Strategy dispatcher: IndexedStrategy (pinned hints) or ScanStrategy |
| `split` | B | Intra-file split into `SPLIT_DEGREE` contiguous chunks, each scanned on a thread pool task |
| `fanout` | A | Per-length fan-out for `/search/many`, one `Task.Run` per word length |
| `nested` | A+B | Fan-out + per-length split (default for `SEARCH_MODE=parallel`) |

Output is byte-identical across all modes (chunks and lengths merged in order).
