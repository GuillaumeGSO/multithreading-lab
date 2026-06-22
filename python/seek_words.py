"""Public search surface + the strategy dispatcher.

Two correctness-equivalent algorithms (both return byte-identical results to the
original brute-force reference) live behind one common interface; this module picks
the faster one *per query* from the query shape alone. Because the two strategies
always agree on output, dispatch is a pure performance choice that can never change
results.

Dispatch rule (derived empirically — see the plan / README):

    /search/file :  INDEXED  if  a pinned hint is present   else   SCAN
    /search/many :  SCAN     (always)

`/search/file` uses the positional index only when it has something to exploit: a
**pinned** hint (`inverted=False`) seeds a tight candidate set → O(result). Everything
else (letters-only, excluded-hint-only, and **strict** without a pinned hint) is at best
a tie for the index — both strategies derive letter counts per word on the fly — so the
lean scan, which caches nothing, wins. (`strict` used to flip the no-pinned case to
INDEXED back when it cached per-word Counters; those were dropped to fit the memory
budget, so the rule no longer depends on `strict`.)

`/search/many` always uses SCAN. A pinned `/many` query would otherwise build the
positional index for *every* length `min_len..len(cars)` — the long-length tail alone is
~64 MB/worker — while the index barely beats the scan on `/many` (it re-seeds per length,
so it degenerates toward a full scan with a heavier constant; original benchmark finding).
Scanning `/many` keeps two uvicorn workers comfortably inside the 512 MB budget; the index
is reserved for `/search/file`, where it wins most and costs only one length per query.

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


def choose_strategy(lst_hint: List[Hint] | None) -> SearchStrategy:
    """Strategy for a single-file (`/search/file`) query."""
    return INDEXED if _has_pinned(lst_hint) else SCAN


def search_in_file(lang="fr", nb_car=0, lst_car: List[str] = None,
                   lst_hint: List[Hint] = None, strict=False):
    strategy = choose_strategy(lst_hint)
    yield from strategy.search_in_file(lang, nb_car, lst_car, lst_hint, strict)


def search_in_many_files(lang="fr", cars="", lst_hint: List[Hint] = None):
    # Always SCAN: the index's per-length re-seed barely beats the scan on /many, but
    # would build pos_index for every length — too costly for the 512 MB budget.
    yield from SCAN.search_in_many_files(lang, cars, lst_hint)
