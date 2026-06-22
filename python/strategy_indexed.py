"""IndexedStrategy — the positional inverted index.

On first use per `(lang, length)`, the **positional index** is built from the shared
base — `pos → char → frozenset(words)`: a pinned hint becomes a set intersection, an
excluded hint a set subtraction. That index is the *only* structure this strategy
caches; everything else (iteration order, letter availability) is derived per query
from `common.load_base` `(word, normalized)`, building a `Counter` on the fly only for
the rare strict path. Caching only the irreducible index keeps the footprint small
enough that two uvicorn workers can hold it alongside the scan path inside the 512 MB
container budget.

This wins when there is a pinned hint to exploit — it seeds a tight candidate set →
O(result). Built from `common.load_base`, so normalization is shared with ScanStrategy
and never repeated.
"""

from collections import Counter
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


def _ensure_index(lang: str, nb_car: int) -> str:
    key = f"{lang}/{nb_car}"
    if key in _pos_index:
        return key

    logger.info("index build (indexed): %s", key)
    pos_idx: dict[int, dict[str, set]] = {pos: {} for pos in range(1, nb_car + 1)}

    for word, _ in load_base(lang, nb_car):
        for pos in range(1, nb_car + 1):
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

    def search_in_file(self, lang="fr", nb_car=0, lst_car: List[str] = None,
                       lst_hint: List[Hint] = None, strict=False):
        lst_car = lst_car or []
        lst_hint = lst_hint or []
        is_empty_hint = is_hint_list_empty_or_full_of_none(lst_hint)
        is_empty_cars = is_list_empty_or_full_of_none(lst_car)
        if nb_car == 0 or (is_empty_cars and is_empty_hint):
            raise Exception("Parameters lstCar et lstHint cannot be empty at the same time")

        key = _ensure_index(lang, nb_car)
        pos_idx = _pos_index[key]
        base = load_base(lang, nb_car)

        # Build candidate set from the positional index.
        candidates: frozenset | None = None
        if not is_empty_hint:
            active_hints = [h for h in lst_hint if h.car]
            for hint in active_hints:
                if hint.inverted:
                    continue
                pos = int(hint.pos)
                if pos > nb_car:
                    return  # pinned hint beyond word length — nothing can match
                hint_set = pos_idx.get(pos, {}).get(hint.car, frozenset())
                candidates = hint_set if candidates is None else candidates & hint_set

            if candidates is None:
                candidates = frozenset(w for w, _ in base)

            for hint in active_hints:
                if not hint.inverted:
                    continue
                pos = int(hint.pos)
                if pos > nb_car:
                    continue  # excluded hint beyond word length — no effect
                excluded = pos_idx.get(pos, {}).get(hint.car, frozenset())
                candidates = candidates - excluded

        # Filter by letter availability. Counts are derived from the normalized word on
        # the fly (a Counter only for the rare strict path) — nothing per-word is cached.
        if not is_empty_cars:
            query_counter = Counter(lst_car) if strict else None
            query_set = set(lst_car)
            for word, normalized in base:
                if candidates is not None and word not in candidates:
                    continue
                if strict:
                    word_counter = Counter(normalized)
                    if not all(word_counter[c] <= query_counter[c] for c in word_counter):
                        continue
                else:
                    if not all(c in query_set for c in normalized):
                        continue
                yield word
        else:
            # Hints only — yield candidates in original word-list (base) order.
            candidate_set = candidates
            for word, _ in base:
                if word in candidate_set:
                    yield word

    def search_in_many_files(self, lang="fr", cars="", lst_hint: List[Hint] = None):
        lst_hint = lst_hint or []
        min_len = max(
            (int(h.pos) for h in lst_hint if h.car and not h.inverted),
            default=1,
        )
        for i in reversed(range(min_len, len(cars) + 1)):
            yield from self.search_in_file(lang=lang, nb_car=i, lst_car=list(cars), lst_hint=lst_hint)
