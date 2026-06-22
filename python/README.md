# python

The consolidated Python implementation. It holds **both** word-search algorithms as
explicit strategies and picks the faster one **per query**, from the query shape alone.

> The single Python implementation. It consolidates three earlier experiments — a
> brute-force baseline, an on-load index, and a positional/frequency index — into one
> dispatcher. Runs on **8007**.

## The two strategies

| Strategy | Cached structure | Per-word cost | Best at |
|---|---|---|---|
| **ScanStrategy** ([strategy_scan.py](strategy_scan.py)) | **none** — iterates the shared base | derive membership from the normalized string (strict builds a `Counter` on demand) | letters-only / excluded-hint-only, and **strict** without a pinned hint |
| **IndexedStrategy** ([strategy_indexed.py](strategy_indexed.py)) | positional index `pos→char→frozenset(words)` only | set intersection to seed candidates; availability derived from the base per query | a **pinned** hint to seed from |

Both return **byte-identical** results to the original brute-force reference (guarded by
`test_seek_words.py` and the cross-strategy equivalence checks in `test_dispatch.py`).
That equivalence is what makes per-query dispatch *safe*: it only changes speed, never
output.

Neither strategy caches anything *per word*: both derive what they need from the shared
`common.load_base` `(word, normalized)`, and `IndexedStrategy` additionally caches the
**positional index** (its whole reason to exist). This keeps the footprint small enough
that two `uvicorn` workers fit inside the 512 MB container budget — the property that
makes the dispatcher viable as the live default (see [Memory](#memory-why-nothing-is-cached-per-word)).

## Dispatch rule

```python
# seek_words.py
def _has_pinned(hints):   # ≥1 pinned (non-inverted) hint carrying a letter
    return any(h.car and not h.inverted for h in (hints or []))

# /search/file
strategy = INDEXED if _has_pinned(lst_hint) else SCAN
# /search/many
strategy = SCAN          # always
```

For `/search/file`, use INDEXED only when it has something to exploit — a **pinned** hint
(`inverted=False`), which seeds a tight candidate set → O(result). Everything else
(letters-only, excluded-only, and **strict** without a pinned hint) is at best a tie for
the index — both strategies derive letter counts on the fly — so the lean SCAN, which
caches nothing, wins.

`/search/many` **always** scans: a pinned `/many` query would otherwise build `pos_index`
for *every* length `min_len..len(cars)` (the long-length tail alone is ~64 MB/worker),
while the index barely beats the scan on `/many` anyway — it re-seeds per length, so it
degenerates toward a full scan with a heavier constant. Scanning `/many` keeps the
workers comfortably inside the budget; the index is reserved for `/search/file`, where it
wins most and costs only one length per query.

This was derived empirically from a balanced, realistic 122-case benchmark (one seed word
per length × {none, pinned, excluded, mixed} hint shapes, plus strict/Scrabble,
crossword/no-pool, and large-pool cases). Measured winners — zero misclassifications:

| Query shape | Winner | Margin |
|---|---|---|
| letters-only / excluded-only / strict-without-pinned | scan | 1.4–2.4× |
| any **pinned** hint (`/file`) | indexed | 3–38× |

> Historical note: an earlier version also routed **strict-without-pinned** to indexed,
> because indexed then cached a `Counter` per word that beat the scan's per-word rebuild.
> Those Counters were dropped to fit the memory budget (below), so strict no longer tips
> the rule — both strategies rebuild the `Counter` on demand now.

Terms: a **pinned** hint says *the letter IS at this position* (`inverted=False`); an
**excluded** hint says *the letter is NOT at this position* (`inverted=True`).

## Memory: why nothing is cached per word

The live API runs **2 `uvicorn` workers** in a **512 MB** container, so per-worker memory
is the binding constraint. Both strategies read each word file once and `unidecode`-normalise
it once, via the shared `common.load_base` (`(word, normalized)` cached per `(lang, length)`).
From there:

- **ScanStrategy caches nothing** — it iterates the base and derives letter membership
  from the normalized string per query (≈ base, ~74 MB for all FR lengths).
- **IndexedStrategy caches only `pos_index`** — the positional inverted index it cannot
  derive cheaply — and gets iteration order + letter availability from the base, building
  a `Counter` on the fly only for the rare strict path.

Caching only the irreducible index (and only for the `/file` lengths that actually receive
a pinned query) keeps each worker well under its share of the 512 MB budget. The earlier
design cached a `frozenset` *and* a `Counter` per word in two parallel structures
(~490 MB in one process); under 2 workers that thrashed against the cap and made even
`/health` time out under load. Deriving on the fly fixed it.

## Files

- `common.py` — shared base loader, `Hint`, hint/list predicates.
- `strategy_scan.py` / `strategy_indexed.py` — the two strategies.
- `seek_words.py` — `SearchStrategy` Protocol, the dispatcher, public `search_in_file` /
  `search_in_many_files` (same signatures the API and benchmark expect).
- `parallel.py` — threaded `split`/`fanout`/`nested` modes (GIL demo; runs on the scan
  path), selected by `SEARCH_MODE=parallel` and `SPLIT_DEGREE`.
- `api.py` — FastAPI: `/health`, `/search/file`, `/search/many`.

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_MODE` | *(dispatcher)* | unset → the index-aware dispatcher (Python's best path, below); `parallel` → the GIL-bound threaded variants; `baseline` → the same single-threaded dispatcher |
| `SPLIT_DEGREE` | `2` | Intra-file chunk count for `split`/`nested` |

Unlike the real-thread languages — whose `parallel` mode *is* their idiomatic best path —
Python threads are GIL-bound overhead, so **python alone defaults off `parallel`** and
serves via the dispatcher. (`SEARCH_MODE=parallel` is kept as the deliberate "threads
don't help a CPU-bound scan under the GIL" demonstration.)

## Port

Runs on **8007**.

## Local dev

```bash
uv sync
uv run pytest -v
uv run uvicorn api:app --port 8007
```

## Docker

```bash
docker compose up python
```
