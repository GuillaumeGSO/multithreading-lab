"""Public search surface + the strategy dispatcher.

Two correctness-equivalent algorithms (both return byte-identical results to the
old python-base reference) live behind one common interface; this module picks the
faster one *per query* from the query shape alone. Because the two strategies always
agree on output, dispatch is a pure performance choice that can never change results.

Dispatch rule (derived empirically — see the plan / README):

    INDEXED  if  (strict OR a pinned hint is present)   else   SCAN

The positional index only pays off when it has something to exploit: a **pinned** hint
(`inverted=False`) seeds a tight candidate set, and **strict** mode reuses its
precomputed per-word Counters. Everything else (letters-only, excluded-hint-only,
non-strict) is faster with the lean scan. `strict` exists only on `/search/file`, so
`/search/many` reduces to the pinned-hint check.

`api.py`, `parallel.py` and the in-process `bench.py` import `Hint`,
`search_in_file`, `search_in_many_files` from here unchanged.
"""

from typing import Iterable, List, Protocol

# Re-exported public surface (shared, identical across the old impls).
from common import (
    Hint,
    is_hint_list_empty_or_full_of_none,
    is_list_empty_or_full_of_none,
    is_search_by_hint,
)
from strategy_indexed import IndexedStrategy
from strategy_scan import ScanStrategy

__all__ = [
    "Hint",
    "is_list_empty_or_full_of_none",
    "is_hint_list_empty_or_full_of_none",
    "is_search_by_hint",
    "search_in_file",
    "search_in_many_files",
]


class SearchStrategy(Protocol):
    name: str
    def search_in_file(self, lang: str, nb_car: int, lst_car: List[str],
                       lst_hint: List[Hint], strict: bool) -> Iterable[str]: ...
    def search_in_many_files(self, lang: str, cars: str,
                             lst_hint: List[Hint]) -> Iterable[str]: ...


INDEXED: SearchStrategy = IndexedStrategy()
SCAN: SearchStrategy = ScanStrategy()


def _has_pinned(lst_hint: List[Hint] | None) -> bool:
    """True iff there is at least one pinned (non-inverted) hint carrying a letter —
    the only hint kind the positional index can seed a candidate set from."""
    return any(h.car and not h.inverted for h in (lst_hint or []))


def choose_strategy(lst_hint: List[Hint] | None, strict: bool) -> SearchStrategy:
    return INDEXED if (strict or _has_pinned(lst_hint)) else SCAN


def search_in_file(lang="fr", nb_car=0, lst_car: List[str] = None,
                   lst_hint: List[Hint] = None, strict=False):
    strategy = choose_strategy(lst_hint, strict)
    yield from strategy.search_in_file(lang, nb_car, lst_car, lst_hint, strict)


def search_in_many_files(lang="fr", cars="", lst_hint: List[Hint] = None):
    # /search/many has no strict, so the rule reduces to the pinned-hint check.
    strategy = choose_strategy(lst_hint, strict=False)
    yield from strategy.search_in_many_files(lang, cars, lst_hint)
