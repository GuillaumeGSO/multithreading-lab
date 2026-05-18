# Load Tests

Artillery load tests for comparing all language implementations against the same HTTP API.

## Files

| File | Purpose |
|------|---------|
| `artillery.yml` | Single test file for all implementations — environments select the target port |
| `generate_queries.py` | Generates `queries.csv` with 500 diverse randomized search queries |
| `queries.csv` | Generated payload file consumed by Artillery (do not edit manually) |
| `payload-processor.js` | Artillery hook that builds the JSON request body from a CSV row |
| `run-all.sh` | Runs the test against all reachable containers and produces `compare-report.html` |
| `compare.py` | Aggregates Artillery JSON results into `compare-report.html` |

## Setup

Node.js is required, plus Artillery installed globally:

```bash
npm install -g artillery
```

> Artillery is installed globally rather than as a local `node_modules`
> dependency because this repo lives on an exFAT volume, which cannot host a
> reliable `node_modules` tree (no symlink/hardlink support). On a normal
> filesystem `npm install` of a local dependency would also work.

## Running tests

```bash
# Run against a single implementation
npm run run:python-indexed

# Run against all reachable containers and generate compare-report.html
./run-all.sh
```

Available environments: `python-base`, `python-improved`, `python-indexed`, `java`, `go`, `cpp`.

| npm script | Port |
|---|---|
| `npm run run:python-base` | 8000 |
| `npm run run:python-improved` | 8001 |
| `npm run run:python-indexed` | 8005 |
| `npm run run:java` | 8002 |
| `npm run run:go` | 8003 |
| `npm run run:cpp` | 8004 |

## How randomized payloads work

Each Artillery request picks a random row from `queries.csv`. The row contains:

| Column | Description |
|--------|-------------|
| `nb_car` | Word length to search (4–8) |
| `cars` | Available letters as a string (e.g. `wvebcintz`) |
| `strict` | Whether the word must use only the provided letters |
| `lst_hint` | JSON array of positional hints `[{pos, car, inverted}]` |

`payload-processor.js` is called as a `beforeRequest` hook and converts each row into the correct JSON body per endpoint:

- `/search/file` — splits `cars` into `lst_car: ["w","v","e",...]` and passes `nb_car`
- `/search/many` — passes `cars` as a plain string; `nb_car` is ignored (all lengths are searched)

## Regenerating queries

The CSV is committed so tests are reproducible (`seed=42`). To regenerate:

```bash
python3 generate_queries.py
```

Queries are guaranteed to contain at least one vowel in the available letter set.

## Why randomized queries?

The original test reused the same 6 hardcoded queries. This artificially favoured indexed implementations because:
- The same index paths stayed hot in CPU cache across hundreds of repetitions
- Hit rate reached 99.9% immediately, hiding any real-world variability

With 500 diverse queries, each request exercises a different word length, letter set, and hint combination, giving a more realistic picture of production behaviour.
