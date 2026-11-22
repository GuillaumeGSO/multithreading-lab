# Architecture decision records

Short records of the decisions that shape this lab: what was decided, why, and what it
costs. Each one is immutable once accepted; a later record supersedes it rather than
editing it.

| # | Decision | Status |
|---|---|---|
| [0001](0001-spec-first-contract.md) | One OpenAPI file is the contract; every implementation generates from it | Accepted |
| [0002](0002-same-algorithm-same-modes.md) | Same algorithm and the same named modes in every language | Accepted |
| [0003](0003-uniform-cpu-budget.md) | A uniform 2-CPU budget, pinned per runtime | Accepted |
| [0004](0004-commit-go-generated-code.md) | Commit Go's generated code, generate everything else at build time | Accepted |
| [0005](0005-contract-fuzzing.md) | Fuzz every service against the contract in CI | Accepted |
| [0006](0006-remove-cpp.md) | Remove the C++ implementation | Accepted |

Template: **Context** (the forces at play), **Decision**, **Consequences** (good and bad).
