# 0004. Commit Go's generated code, generate everything else at build time

**Status:** Accepted

## Context

Generated code can be committed or produced at build time. Committing adds review noise and
a drift risk; generating at build time needs the generator in every build environment.

## Decision

- **Go:** `go/api/api.gen.go` is committed. Go tooling expects a module to build with
  `go build` alone (no pre-build hook), and `go generate` is a developer step by convention.
  CI regenerates it and fails on any diff, so it cannot drift from `openapi.yaml`.
- **Everyone else:** generated at build time and git-ignored — Maven plugin, MSBuild target,
  `npm run generate` (prebuild), and a codegen stage in the Python image. Their build tools
  have a natural hook for it.

## Consequences

- `go build` and `go test` work from a fresh clone, with no extra tool installed.
- A spec change must include the regenerated `api.gen.go` in the same commit; CI enforces it.
- The other four can never commit stale generated code, at the cost of needing the
  generator in each build (already true inside their Dockerfiles).
