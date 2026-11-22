# 0002. Same algorithm and the same named modes everywhere

**Status:** Accepted

## Context

The first comparison ran each language "at its best": Python and Java served queries from a
positional index while others scanned, and some scans were optimised and others not. The
results mostly measured algorithm differences, not concurrency models — which is what the
lab is for.

## Decision

- **One algorithm.** Every scan precomputes, per word at load time, the accent-free form and
  the a–z letter counts; a query prepares its letter pool once; only the predicates a query
  needs are evaluated. Python's scan is the reference. An optimisation goes into all five
  scans or none.
- **One meaning per mode.** `SEARCH_MODE` selects the same strategy everywhere: `baseline`
  (single-threaded), `parallel` (per-length fan-out plus an intra-file split into
  `SPLIT_DEGREE` chunks), and `indexed` (an algorithm comparison, Python/Java/C# only). The
  default is `parallel` everywhere, Python included. An unknown value stops the server at
  startup.
- **Same output.** Every mode returns byte-identical results to `baseline`; mode-equivalence
  tests enforce it in each language, and the benchmark report checks that every language
  returns the same word count for all 122 cases.
- Charts only compare languages within one mode; the index is reported separately.

## Consequences

- Differences in the results can be attributed to the runtime's concurrency model and its
  per-task overhead, not to the algorithm.
- Some implementations are slower than idiomatic, tuned code would be. That is accepted:
  the README's limits section says so.
- Python's `parallel` mode is slower than its `baseline` (the GIL); keeping the same default
  makes that visible rather than hiding it.
