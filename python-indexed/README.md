# python-indexed

Same API as `python-base`, with pre-built inverted indexes to accelerate search.

## Approach

On first access per `(lang, word_length)`, two indexes are built from the word list:

- **Positional index** — `pos → char → frozenset of words`  
  Hint filtering becomes set intersection/subtraction instead of per-word iteration.
  A query like "position 1 = s, position 3 = a" resolves via `index[1]['s'] & index[3]['a']`.

- **Frequency index** — `list of (word, Counter(normalized_word))`  
  Letter availability check compares pre-computed counters instead of scanning characters one by one.

## Complexity

| Query type | python-base | python-indexed |
|---|---|---|
| Hints only | O(vocab) | O(result) via set intersection |
| Letters only | O(vocab × length) | O(vocab) counter comparison |
| Hints + letters | O(vocab × length) | O(hint_candidates) counter comparison |

The first request for a given word length pays the index build cost (~same as loading the file). All subsequent requests are faster.

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
