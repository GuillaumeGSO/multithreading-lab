# C# / .NET 9 implementation

ASP.NET Core 9 Minimal API. Uses `Task.WhenAll` + `Task.Run` (ThreadPool) for CPU-bound
parallelism — the C# equivalent of Go goroutines. Same strategy dispatcher as Python/Java
(positional index ↔ lean scan per query), same API contract, same concurrency modes.

Port: **8005**

## Local dev

```bash
cd csharp/Api
dotnet run          # starts on http://localhost:8005 (launchSettings.json sets env vars)
dotnet watch run    # auto-reload on file changes
```

`launchSettings.json` pre-sets `ASSETS_ROOT=../../assets`, `PORT=8005`,
`SEARCH_MODE=parallel`, `SPLIT_DEGREE=2` — no env vars to type.

## Tests

```bash
cd csharp
ASSETS_ROOT=../assets dotnet test Tests/Tests.csproj -v normal
```

## Docker

```bash
# From repo root
docker compose build csharp
docker compose up csharp -d
curl http://localhost:8005/health
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ASSETS_ROOT` | `../../assets` (local) / `/app/assets` (Docker) | Word list directory |
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
