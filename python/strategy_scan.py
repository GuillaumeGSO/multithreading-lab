"""ScanStrategy — the lean on-load scan.

The scan iterates the shared `common.load_base` `(word, normalized, freq)` tuples
directly — it stores **no** per-word superstructure of its own. The per-request scan is
O(vocabulary) but with a cheap per-word predicate: a membership test for non-strict
queries, or a 26-integer array comparison for strict queries (no Counter allocation —
the frequency array is precomputed in load_base). This wins when the index has nothing
to seed from: letters-only or excluded-hint-only queries.

The module-level `is_search_by_content` is also imported by `parallel.py` (the GIL-demo
threaded modes run on this scan data path).
"""

from typing import List

from common import (
    Hint,
    is_hint_list_empty_or_full_of_none,
    is_list_empty_or_full_of_none,
    is_search_by_hint,
    load_base,
)


def is_search_by_content(normalized_word: str, avail_set: set,
                         avail_arr: list[int] | None = None, strict: bool = False,
                         word_freq: bytes | None = None):
    """Does the word fit the available pool? Pure predicate, zero per-word allocation.

    Non-strict: every letter of the normalized word must be in the pool (membership).
    Strict: membership check first (fast early-exit for non-pool chars), then a
    fixed-cost 26-integer frequency comparison against the precomputed `word_freq`.
    """
    if not normalized_word:
        return False
    if not avail_set:
        return False
    if not all(char in avail_set for char in normalized_word):
        return False
    if strict:
        return all(wf <= af for wf, af in zip(word_freq, avail_arr))
    return True


def _build_avail_arr(avail: list[str]) -> list[int]:
    """26-int letter-frequency array for the query pool, built once per search call."""
    arr = [0] * 26
    for c in avail:
        i = ord(c) - 97
        if 0 <= i < 26:
            arr[i] += 1
    return arr


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

        # Build the available-letter pool once for the whole scan.
        avail = [c for c in lst_car if c]
        avail_set = set(avail)
        avail_arr = _build_avail_arr(avail) if strict else None

        for word, normalized_word, word_freq in load_base(lang, nb_car):
            if is_empty_hint:  # cars non-empty here (guaranteed by the guard above)
                if is_search_by_content(normalized_word, avail_set, avail_arr, strict, word_freq):
                    yield word
            elif is_empty_cars:
                if is_search_by_hint(word, lst_hint):
                    yield word
            elif (is_search_by_content(normalized_word, avail_set, avail_arr, strict, word_freq)
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
