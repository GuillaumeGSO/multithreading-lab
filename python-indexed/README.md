# python-indexed

Same API as `python-base`, with pre-built inverted indexes to accelerate search.

## Approach

On first access per `(lang, word_length)`, two indexes are built from the word list:

- **Positional index** — `pos → char → frozenset of words`  
  Hint filtering becomes set intersection/subtraction instead of per-word iteration.

- **Frequency index** — `list of (word, Counter(normalized_word))`  
  Letter availability check compares pre-computed counters instead of scanning characters one by one.

## How the positional index works

Given a word list, the index pre-groups every word by the character at each position:

```
Word list: sabre, sable, laser, lasse, salir, alise
                                                       
           pos 1       pos 2       pos 3       pos 4  ...
           ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐
      's' →│ sabre │   │       │   │       │   │       │
           │ sable │   │ lasse │   │ sabre │   │ laser │
           │ salir │   │       │   │ sable │   │       │
           └───────┘   └───────┘   └───────┘   └───────┘
      'l' →│ laser │   │ sable │   │ salir │   │ sabre │
           │ lasse │   │ salir │   │ alise │   │ sable │
           │       │   │ alise │   │       │   │ salir │
           └───────┘   └───────┘   └───────┘   └───────┘
      'a' →│ alise │   │ sabre │   │ laser │   │ lasse │
           │       │   │       │   │ lasse │   │ alise │
           └───────┘   └───────┘   └───────┘   └───────┘
```

Query: hints `pos1='s'` AND `pos3='b'`

```
  pos_index[1]['s'] = { sabre, sable, salir }
∩ pos_index[3]['b'] = { sabre, sable }
                     ─────────────────────────
                     → { sabre, sable }          ✓ 2 candidates, no full scan
```

Without the index, python-base checks every word in the file one by one.  
With the index, the result set comes directly from set intersection — O(result) instead of O(vocab).

## Complexity

| Query type | python-base | python-indexed |
|---|---|---|
| Hints only | O(vocab) | O(result) via set intersection |
| Letters only | O(vocab × length) | O(vocab) counter comparison |
| Hints + letters | O(vocab × length) | O(hint_candidates) counter comparison |

The first request for a given word length pays the index build cost (~same as loading the file). All subsequent requests are faster.

## Parallel modes bypass the index (a deliberate contrast)

The index powers the **single-threaded** `search_in_file`. The threaded
`split`/`nested` modes in the shared `parallel.py` (used by the in-process
benchmark and by the API under `SEARCH_MODE=parallel`) do a **brute-force chunked
scan** — they do *not* consult the positional/frequency index. So python-indexed:

- is the **fastest** baseline (index = O(result)), and on the throughput test
  (which uses the baseline path per request);
- is the **slowest** in `fanout`/`nested`, because those abandon the index for
  the O(vocabulary) brute force *and* add GIL-bound thread overhead.

The lesson: bolting generic parallelism onto a specialized algorithm discards the
specialization. If you want the index under load, keep `SEARCH_MODE=baseline`.
Run: `docker compose run --rm --entrypoint .venv/bin/python python-indexed bench.py`.

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_MODE` | `parallel` | `parallel` uses the brute-force threaded variants; `baseline` keeps the index |
| `SPLIT_DEGREE` | `2` | Intra-file chunk count for `split`/`nested` |

## Port

Runs on **8005**.

## Local dev

```bash
uv sync
uv run pytest -v
uv run uvicorn api:app --port 8005
```

## Docker

```bash
docker compose up python-indexed
```
