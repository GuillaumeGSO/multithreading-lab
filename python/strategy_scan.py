"""ScanStrategy — the lean on-load scan.

The scan iterates the shared `common.load_base` `(word, normalized)` tuples directly —
it stores **no** per-word superstructure of its own. The per-request scan is
O(vocabulary) but with a cheap per-word predicate derived on the fly from the
normalized string: a membership test for the non-strict content check (strict rebuilds
a Counter on demand — the rare path). Deriving instead of caching keeps the scan's
memory footprint at ≈ the base, which is what lets two uvicorn workers + the indexed
strategy coexist inside the 512 MB container budget. This wins when the index has
nothing to seed from: letters-only or excluded-hint-only, non-strict queries.

The module-level `is_search_by_content` is also imported by `parallel.py` (the GIL-demo
threaded modes run on this scan data path).
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


def is_search_by_content(normalized_word: str, avail_set: set,
                         avail_counter: Counter | None = None, strict=False):
    """Does the word fit the available pool? Pure predicate, no cached per-word data.

    Non-strict: every letter of the normalized word must be in the pool (membership).
    Strict: the pool must hold at least as many of each letter as the word needs
    (rebuilds a Counter from the normalized word — the rare path).
    """
    if not normalized_word:
        return False
    if not avail_set:
        return False
    if strict:
        word_counter = Counter(normalized_word)
        return all(word_counter[char] <= avail_counter[char] for char in word_counter)
    return all(char in avail_set for char in normalized_word)


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

        for word, normalized_word in load_base(lang, nb_car):
            if is_empty_hint:  # cars non-empty here (guaranteed by the guard above)
                if is_search_by_content(normalized_word, avail_set, avail_counter, strict):
                    yield word
            elif is_empty_cars:
                if is_search_by_hint(word, lst_hint):
                    yield word
            elif (is_search_by_content(normalized_word, avail_set, avail_counter, strict)
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
