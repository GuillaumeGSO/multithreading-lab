# 0006. Remove the C++ implementation

**Status:** Accepted (supersedes the original six-language scope)

## Context

A C++ implementation (cpp-httplib, `std::thread`) was part of the lab. Its numbers were
competitive, but its author could not review it with the same confidence as the other five:
memory safety, request parsing and thread-safety questions would have needed an expert
reviewer, and a benchmark is only as credible as its least-understood participant.

## Decision

Remove it. It stays in the git history (tag `v1.1.0`).

## Consequences

- Every remaining implementation is one the author can defend line by line.
- The comparison loses a manual-memory, native-threads data point. Adding it back is
  welcome under the same rules (spec-first models, the reference scan, the same modes, the
  2-CPU budget, the contract fuzz).
