# 0005. Fuzz every service against the contract in CI

**Status:** Accepted

## Context

Each implementation had hand-written HTTP validation tests mirroring the same table of
invalid requests. That proves the cases someone thought of. It does not prove the contract:
five generators differ in how they treat nulls, type coercion, defaults and undocumented
statuses, and hand-written tables share the same blind spots.

## Decision

The CI smoke job starts every container and runs [Schemathesis](https://schemathesis.readthedocs.io)
against each one, using the spec the service itself serves. Configuration lives in
`schemathesis.toml`:

- All checks enabled: no 5xx, responses and content types match the schema, only
  documented statuses, schema-invalid requests rejected, 405 carries `Allow`.
- Deterministic generation, so a red build reproduces.
- `positive_data_acceptance` is disabled: the cross-field rule ("letters and hints cannot
  both be empty") rejects some schema-valid requests by design.
- Rejection of invalid input may be 400, 413 or 415, all documented.

## Consequences

The first run found bugs in every implementation that the hand-written suites had missed:

- a 500 in Python (multi-character `letters` element in strict mode) and in Java (multipart
  parsing of a GET's Content-Type);
- explicit `null` accepted as "absent" for non-nullable fields in all five;
- `0` read as `false` and `"lang": 0` read as `fr` (Python, Java, C#); `"lang": ""` defaulted (Go);
- 405 without `Allow` (Python), 404/400 instead of 405 (Nest);
- 413 and 415 returned but not documented.

Each fix shipped with a regression test in that language's suite. The cost is a few
seconds per service in CI, and one more tool to keep pinned.
