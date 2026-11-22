# 0003. A uniform 2-CPU budget, pinned per runtime

**Status:** Accepted

## Context

A `cpus: "2.0"` limit alone is not enough: several runtimes size their parallelism from the
*host* core count and ignore the cgroup quota. Go's `GOMAXPROCS`, the .NET thread pool and
the JVM's view of available processors would all be sized for the whole machine, so on a
many-core host a service would schedule more parallel work than its quota allows and be
throttled. The comparison would depend on the host, not on the runtime.

## Decision

Every service runs under `cpus: "2.0"` and `memory: 512m`, and each runtime is pinned
**explicitly** in `docker-compose.yml`:

| Runtime | Pin |
|---|---|
| Go | `GOMAXPROCS=2` |
| JVM | `JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2` |
| .NET | `DOTNET_PROCESSOR_COUNT=2` |
| Node | `WORKER_POOL_SIZE=2` |
| Python | `uvicorn --workers 2` (threads are GIL-bound) |

The pins apply to both `docker compose up` (HTTP load tests) and `docker compose run` (the
in-process benchmark).

## Consequences

- Each runtime sees the same parallelism it is allowed to use; quota throttling no longer
  skews results.
- The budget is a ceiling, not a reservation: services share the Docker VM's CPUs, so the
  runners measure one service at a time and the README warns to keep Docker idle.
- Newer runtime versions may become cgroup-aware by default; the explicit pins stay so the
  setup does not depend on a version detail.
