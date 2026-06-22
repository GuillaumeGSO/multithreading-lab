"""IndexedStrategy — the positional + frequency inverted index (from python-indexed).

On first use per `(lang, length)`, two indexes are built from the shared base:

- **positional index** — `pos → char → frozenset(words)`: a pinned hint becomes a
  set intersection, an excluded hint a set subtraction.
- **frequency index** — `list[(word, Counter(normalized))]`: the letter-availability
  check compares pre-computed counters instead of scanning characters per request.

This wins when there is something to exploit: a pinned hint (which seeds a tight
candidate set → O(result)), or strict mode (the precomputed Counters beat the scan's
per-word Counter rebuild). Built from `common.load_base`, so normalization is shared
with ScanStrategy and never repeated.
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
# freq_index[key] → list of (original_word, Counter(normalized_word)), in base order
_freq_index: dict[str, list[tuple[str, Counter]]] = {}


def _ensure_index(lang: str, nb_car: int) -> str:
    key = f"{lang}/{nb_car}"
    if key in _pos_index:
        return key

    logger.info("index build (indexed): %s", key)
    pos_idx: dict[int, dict[str, set]] = {pos: {} for pos in range(1, nb_car + 1)}
    freq_idx: list[tuple[str, Counter]] = []

    for word, normalized in load_base(lang, nb_car):
        freq_idx.append((word, Counter(normalized)))
        for pos in range(1, nb_car + 1):
            char = word[pos - 1]
            if char not in pos_idx[pos]:
                pos_idx[pos][char] = set()
            pos_idx[pos][char].add(word)

    _pos_index[key] = {
        pos: {c: frozenset(s) for c, s in chars.items()}
        for pos, chars in pos_idx.items()
    }
    _freq_index[key] = freq_idx
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
        freq_idx = _freq_index[key]

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
                candidates = frozenset(w for w, _ in freq_idx)

            for hint in active_hints:
                if not hint.inverted:
                    continue
                pos = int(hint.pos)
                if pos > nb_car:
                    continue  # excluded hint beyond word length — no effect
                excluded = pos_idx.get(pos, {}).get(hint.car, frozenset())
                candidates = candidates - excluded

        # Filter by letter availability.
        if not is_empty_cars:
            query_counter = Counter(lst_car)
            query_set = set(lst_car)
            for word, word_counter in freq_idx:
                if candidates is not None and word not in candidates:
                    continue
                if strict:
                    if not all(word_counter[c] <= query_counter[c] for c in word_counter):
                        continue
                else:
                    if not all(c in query_set for c in word_counter):
                        continue
                yield word
        else:
            # Hints only — yield candidates in original word-list (base) order.
            candidate_set = candidates
            for word, _ in freq_idx:
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
