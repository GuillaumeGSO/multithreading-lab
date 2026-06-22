# python

The consolidated Python implementation. It holds **both** word-search algorithms as
explicit strategies and picks the faster one **per query**, from the query shape alone.

> The single Python implementation. It consolidates three earlier experiments — a
> brute-force baseline, an on-load index, and a positional/frequency index — into one
> dispatcher. Runs on **8007**.

## The two strategies

| Strategy | Data structure | Per-word cost | Best at |
|---|---|---|---|
| **ScanStrategy** ([strategy_scan.py](strategy_scan.py)) | `(word, normalized, char_set)` per word | cheap frozenset subset (strict rebuilds a Counter on demand) | letters-only / excluded-hint-only, **non-strict** |
| **IndexedStrategy** ([strategy_indexed.py](strategy_indexed.py)) | positional index `pos→char→frozenset(words)` + frequency index `(word, Counter)` | set intersection to seed, precomputed Counter to filter | a **pinned** hint to seed from, or **strict** mode |

Both return **byte-identical** results to the original brute-force reference (guarded by
`test_seek_words.py` and the cross-strategy equivalence checks in `test_dispatch.py`).
That equivalence is what makes per-query dispatch *safe*: it only changes speed, never
output.

## Dispatch rule

```python
# seek_words.py
def _has_pinned(hints):   # ≥1 pinned (non-inverted) hint carrying a letter
    return any(h.car and not h.inverted for h in (hints or []))

strategy = INDEXED if (strict or _has_pinned(lst_hint)) else SCAN
```

Use INDEXED only when it has something to exploit — a **pinned** hint
(`inverted=False`, which seeds a tight candidate set → O(result)) or **strict** mode
(its precomputed Counters beat the scan's per-word Counter rebuild). Everything else is
faster with the lean SCAN. `strict` exists only on `/search/file`, so `/search/many`
reduces to the pinned-hint check.

This rule was derived empirically from a balanced, realistic 122-case benchmark
(one seed word per length × {none, pinned, excluded, mixed} hint shapes, plus
strict/Scrabble, crossword/no-pool, and large-pool cases). Measured winners — zero
misclassifications:

| Query shape | Winner | Margin |
|---|---|---|
| letters-only / excluded-only, non-strict | scan | 1.4–2.4× |
| any **pinned** hint | indexed | 3–38× |
| any **strict** (even with no pinned hint) | indexed | 2.7–4.4× |

Terms: a **pinned** hint says *the letter IS at this position* (`inverted=False`); an
**excluded** hint says *the letter is NOT at this position* (`inverted=True`).

## Shared base, specialised lazily

Both strategies read each word file once and `unidecode`-normalise it once, via the
shared `common.load_base` (`(word, normalized)` cached per `(lang, length)`). Each
strategy then builds *only its own* specialised index from that base, lazily on first
use. So the dominant build cost (IO + normalisation) is paid once per length total, and
an index a strategy never needs for a given length is never built.

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
| `SEARCH_MODE` | `parallel` | `parallel` uses the threaded variants; `baseline` the single-threaded dispatcher |
| `SPLIT_DEGREE` | `2` | Intra-file chunk count for `split`/`nested` |

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
