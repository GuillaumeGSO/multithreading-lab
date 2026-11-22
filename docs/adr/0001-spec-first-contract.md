# 0001. One OpenAPI file is the contract

**Status:** Accepted

## Context

Five implementations expose the same API. Earlier, each framework produced its own spec from
hand-written DTOs and annotations (FastAPI from Pydantic models, springdoc from `@Schema`,
`@nestjs/swagger` from decorators, and so on). The contract was then five documents kept in
step by hand, with no guarantee that field names, bounds, defaults or error shapes matched.

## Decision

`openapi.yaml` at the repository root is the single source of truth.

- Every implementation **generates** its request/response models from it (Pydantic,
  openapi-generator, oapi-codegen, openapi-typescript, NSwag) and **serves it verbatim** at
  `/openapi.yaml`, `/openapi.json` and `/docs`.
- No implementation carries hand-written OpenAPI metadata or generates a spec from code.
- The contract encodes the input bounds (`lang` enum, 1–31 lengths and positions, at most 32
  letters and 31 hints), so validation comes from the generated models wherever the
  generator supports it.
- Spectral lints the file in CI, failing on warnings.

## Consequences

- Any backend can replace any other behind the same port, with no tooling change.
- A contract change is one edit plus a regeneration; reviewers see it in one diff.
- Generators differ in what they enforce at runtime (oapi-codegen and openapi-typescript
  produce types only), so Go and Nest validate the bounds by hand. Cross-field rules
  ("letters and hints cannot both be empty") are not expressible in the schema and are
  documented in the 400 description instead.
- Contract fuzzing ([0005](0005-contract-fuzzing.md)) is what keeps the hand-written parts
  honest.
