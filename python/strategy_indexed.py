"""IndexedStrategy — the positional inverted index.

On first use per `(lang, length)`, the **positional index** is built from the shared
base — `pos → char → frozenset(words)`: a pinned hint becomes a set intersection, an
excluded hint a set subtraction. That index is the *only* structure this strategy
caches; everything else (iteration order, letter availability) is derived per query
from `common.load_base` `(word, normalized, freq)`. The `freq` precomputed array
replaces the old per-word `Counter` build for the strict path — zero allocation at
query time. Caching only the irreducible index keeps the footprint small enough that
two uvicorn workers can hold it alongside the scan path inside the 512 MB budget.

This wins when there is a pinned hint to exploit — it seeds a tight candidate set →
O(result). Built from `common.load_base`, so normalization is shared with ScanStrategy
and never repeated.
"""

from typing import List

from common import (
    Hint,
    is_hint_list_empty_or_full_of_none,
    is_list_empty_or_full_of_none,
    logger,
    load_base,
)

# pos_index[key][pos][char] → frozenset of words with that char at that 1-based position
_pos_index: dict[str, dict[int, dict[str, frozenset]]] = {}


def _ensure_index(lang: str, word_length: int) -> str:
    key = f"{lang}/{word_length}"
    if key in _pos_index:
        return key

    logger.info("index build (indexed): %s", key)
    pos_idx: dict[int, dict[str, set]] = {pos: {} for pos in range(1, word_length + 1)}

    for word, _, _ in load_base(lang, word_length):
        for pos in range(1, word_length + 1):
            char = word[pos - 1]
            if char not in pos_idx[pos]:
                pos_idx[pos][char] = set()
            pos_idx[pos][char].add(word)

    _pos_index[key] = {
        pos: {c: frozenset(s) for c, s in chars.items()}
        for pos, chars in pos_idx.items()
    }
    return key


class IndexedStrategy:
    name = "indexed"

    def search_in_file(self, lang="fr", word_length=0, letters: List[str] = None,
                       hints: List[Hint] = None, strict=False):
        letters = letters or []
        hints = hints or []
        is_empty_hint = is_hint_list_empty_or_full_of_none(hints)
        is_empty_letters = is_list_empty_or_full_of_none(letters)
        if word_length == 0 or (is_empty_letters and is_empty_hint):
            raise ValueError("letters and hints cannot both be empty")

        key = _ensure_index(lang, word_length)
        pos_idx = _pos_index[key]
        base = load_base(lang, word_length)

        # Build candidate set from the positional index.
        candidates: frozenset | None = None
        if not is_empty_hint:
            active_hints = [h for h in hints if h.letter]
            for hint in active_hints:
                if hint.excluded:
                    continue
                pos = int(hint.position)
                if pos > word_length:
                    return  # pinned hint beyond word length — nothing can match
                hint_set = pos_idx.get(pos, {}).get(hint.letter, frozenset())
                candidates = hint_set if candidates is None else candidates & hint_set

            if candidates is None:
                candidates = frozenset(w for w, *_ in base)

            for hint in active_hints:
                if not hint.excluded:
                    continue
                pos = int(hint.position)
                if pos > word_length:
                    continue  # excluded hint beyond word length — no effect
                excluded_words = pos_idx.get(pos, {}).get(hint.letter, frozenset())
                candidates = candidates - excluded_words

        # Filter by letter availability. Non-strict: membership in the pool set.
        # Strict: membership first (cheap early-exit), then 26-int freq comparison
        # against the precomputed word_freq from load_base — no Counter allocation.
        if not is_empty_letters:
            query_set = set(letters)
            query_arr: list[int] | None = None
            if strict:
                query_arr = [0] * 26
                for c in letters:
                    i = ord(c) - 97
                    if 0 <= i < 26:
                        query_arr[i] += 1
            for word, normalized, word_freq in base:
                if candidates is not None and word not in candidates:
                    continue
                if not all(c in query_set for c in normalized):
                    continue
                if strict and not all(wf <= af for wf, af in zip(word_freq, query_arr)):
                    continue
                yield word
        else:
            # Hints only — yield candidates in original word-list (base) order.
            candidate_set = candidates
            for word, _, _ in base:
                if word in candidate_set:
                    yield word

    def search_in_many_files(self, lang="fr", letters="", hints: List[Hint] = None):
        hints = hints or []
        min_len = max(
            (int(h.position) for h in hints if h.letter and not h.excluded),
            default=1,
        )
        for i in reversed(range(min_len, len(letters) + 1)):
            yield from self.search_in_file(lang=lang, word_length=i, letters=list(letters), hints=hints)
