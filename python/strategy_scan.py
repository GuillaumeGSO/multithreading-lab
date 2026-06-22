"""ScanStrategy — the lean on-load scan (from python-improved).

Each word file is turned, on first use, into `(word, normalized, char_set)` tuples
(built from the shared `common.load_base`, so normalization is not repeated). The
per-request scan is O(vocabulary) but with a cheap per-word predicate: a frozenset
subset test for the non-strict content check (strict rebuilds a Counter on demand —
the rare path). This wins when the index has nothing to seed from: letters-only or
excluded-hint-only, non-strict queries.

The module-level `_load_word_indexes` / `is_search_by_content` are also imported by
`parallel.py` (the GIL-demo threaded modes run on this scan data path).
"""

from collections import Counter
from typing import List

from common import (
    Hint,
    is_hint_list_empty_or_full_of_none,
    is_list_empty_or_full_of_none,
    is_search_by_hint,
    load_base,
)

# Scan index: (word, normalized, char_set) per (lang, length), built from the base.
_scan_cache: dict[str, list[tuple[str, str, frozenset]]] = {}


def _load_word_indexes(lang: str, nb_car: int) -> list[tuple[str, str, frozenset]]:
    """`(word, normalized, char_set)` per word, where char_set is the frozenset of
    unique normalized characters. Built lazily from the shared base."""
    key = f"{lang}/{nb_car}"
    cached = _scan_cache.get(key)
    if cached is None:
        cached = [(w, n, frozenset(n)) for (w, n) in load_base(lang, nb_car)]
        _scan_cache[key] = cached
    return cached


def is_search_by_content(word_chars: frozenset, normalized_word: str, avail_set: set,
                         avail_counter: Counter | None = None, strict=False):
    """Does the word fit the available pool? Pure predicate, no per-word allocation
    in the common (non-strict) path.

    Non-strict: every distinct letter of the word must be in the pool (frozenset subset).
    Strict: the pool must hold at least as many of each letter as the word needs
    (rebuilds a Counter from the normalized word — the rare path).
    """
    if not word_chars:
        return False
    if not avail_set:
        return False
    if strict:
        word_counter = Counter(normalized_word)
        return all(word_counter[char] <= avail_counter[char] for char in word_counter)
    return word_chars <= avail_set


class ScanStrategy:
    name = "scan"

    def search_in_file(self, lang="fr", nb_car=0, lst_car: List[str] = None,
                       lst_hint: List[Hint] = None, strict=False):
        lst_car = lst_car or []
        lst_hint = lst_hint or []
        is_empty_hint = is_hint_list_empty_or_full_of_none(lst_hint)
        is_empty_cars = is_list_empty_or_full_of_none(lst_car)
        if nb_car == 0 or (is_empty_cars and is_empty_hint):
            raise Exception("Parameters lstCar et lstHint cannot be empty at the same time")

        # Build the available-letter pool once for the whole scan; counts only when strict.
        avail = [c for c in lst_car if c]
        avail_set = set(avail)
        avail_counter = Counter(avail) if strict else None

        for word, normalized_word, word_chars in _load_word_indexes(lang, nb_car):
            if is_empty_hint:  # cars non-empty here (guaranteed by the guard above)
                if is_search_by_content(word_chars, normalized_word, avail_set, avail_counter, strict):
                    yield word
            elif is_empty_cars:
                if is_search_by_hint(word, lst_hint):
                    yield word
            elif (is_search_by_content(word_chars, normalized_word, avail_set, avail_counter, strict)
                  and is_search_by_hint(word, lst_hint)):
                yield word

    def search_in_many_files(self, lang="fr", cars="", lst_hint: List[Hint] = None):
        lst_hint = lst_hint or []
        min_len = max(
            (int(h.pos) for h in lst_hint if h.car and not h.inverted),
            default=1,
        )
        for i in reversed(range(min_len, len(cars) + 1)):
            yield from self.search_in_file(lang=lang, nb_car=i, lst_car=list(cars), lst_hint=lst_hint)
