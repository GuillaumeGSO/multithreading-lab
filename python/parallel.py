"""Parallel variants of the word search, used by the live API (when
SEARCH_MODE=parallel) and the in-process benchmark.

These reuse the **scan** strategy's per-word data path and predicates — only the
*partitioning* of work across threads differs. A word list is split into ``N``
contiguous chunks scanned on separate threads and merged in index order, so the
output is byte-identical to the sequential search regardless of thread timing.

NOTE (the lesson this module demonstrates): Python threads share one GIL, so this
intra-file split does not speed up the CPU-bound scan — it usually adds overhead.
Python scales at the process/API layer (uvicorn --workers) instead. These modes
deliberately run on the scan path (not the positional index), so they also show why
bolting generic parallelism onto a specialised algorithm throws the specialisation
away.
"""

import os
import threading
from collections import Counter
from typing import List

from common import (
    Hint,
    is_hint_list_empty_or_full_of_none,
    is_list_empty_or_full_of_none,
    is_search_by_hint,
)
from strategy_scan import _load_word_indexes, is_search_by_content


def split_degree() -> int:
    """Chunks per file (axis B). SPLIT_DEGREE env, default 2 ('halves')."""
    try:
        n = int(os.environ.get("SPLIT_DEGREE", "2"))
    except ValueError:
        n = 2
    return max(1, n)


def _matches(entry, avail_set, avail_counter, lst_hint, strict, is_empty_cars, is_empty_hint) -> bool:
    word, normalized, word_chars = entry
    if is_empty_hint:
        return is_search_by_content(word_chars, normalized, avail_set, avail_counter, strict)
    if is_empty_cars:
        return is_search_by_hint(word, lst_hint)
    return (is_search_by_content(word_chars, normalized, avail_set, avail_counter, strict)
            and is_search_by_hint(word, lst_hint))


def _scan(entries, avail_set, avail_counter, lst_hint, strict, is_empty_cars, is_empty_hint) -> List[str]:
    return [
        entry[0] for entry in entries
        if _matches(entry, avail_set, avail_counter, lst_hint, strict, is_empty_cars, is_empty_hint)
    ]


def search_in_file_parallel(
    lang="fr", nb_car=0, lst_car: List[str] = None, lst_hint: List[Hint] = None,
    strict=False, threads: int | None = None,
) -> List[str]:
    """Intra-file split (axis B). Mirrors ``search_in_file`` but scans the word list
    in ``threads`` contiguous chunks. threads=1 runs inline (== baseline)."""
    lst_car = lst_car or []
    lst_hint = lst_hint or []
    is_empty_hint = is_hint_list_empty_or_full_of_none(lst_hint)
    is_empty_cars = is_list_empty_or_full_of_none(lst_car)
    if nb_car == 0 or (is_empty_cars and is_empty_hint):
        raise Exception("Parameters lstCar et lstHint cannot be empty at the same time")

    entries = _load_word_indexes(lang, nb_car)
    # Pool built once and shared read-only across the worker threads.
    avail = [c for c in lst_car if c]
    avail_set = set(avail)
    avail_counter = Counter(avail) if strict else None
    n = threads if threads is not None else split_degree()
    n = max(1, min(n, max(1, len(entries))))

    if n == 1:
        return _scan(entries, avail_set, avail_counter, lst_hint, strict, is_empty_cars, is_empty_hint)

    chunk = (len(entries) + n - 1) // n  # ceil so chunks stay contiguous
    partials: list[list[str] | None] = [None] * n
    workers = []

    def work(idx: int, start: int, end: int) -> None:
        partials[idx] = _scan(
            entries[start:end], avail_set, avail_counter, lst_hint, strict, is_empty_cars, is_empty_hint
        )

    for idx in range(n):
        start = idx * chunk
        end = min(start + chunk, len(entries))
        t = threading.Thread(target=work, args=(idx, start, end))
        workers.append(t)
        t.start()
    for t in workers:
        t.join()

    result: list[str] = []
    for p in partials:
        if p:
            result.extend(p)
    return result


def search_in_many_parallel(
    lang="fr", cars="", lst_hint: List[Hint] = None, threads: int | None = None,
) -> List[str]:
    """Per-length fan-out (axis A). One thread per word length, longest first.

    ``threads`` controls the *inner* intra-file split each length uses:
      - threads=1  → fanout mode (per-length only, no intra-file split)
      - threads=N  → nested mode (threads spawning threads)
    Results are reassembled longest-first, matching ``search_in_many_files``.
    """
    lst_hint = lst_hint or []
    min_len = max(
        (int(h.pos) for h in lst_hint if h.car and not h.inverted),
        default=1,
    )
    lengths = list(reversed(range(min_len, len(cars) + 1)))
    partials: list[list[str] | None] = [None] * len(lengths)
    workers = []

    def work(idx: int, length: int) -> None:
        try:
            partials[idx] = search_in_file_parallel(
                lang=lang, nb_car=length, lst_car=list(cars),
                lst_hint=lst_hint, strict=False, threads=threads,
            )
        except Exception:
            partials[idx] = []

    for idx, length in enumerate(lengths):
        t = threading.Thread(target=work, args=(idx, length))
        workers.append(t)
        t.start()
    for t in workers:
        t.join()

    result: list[str] = []
    for p in partials:
        if p:
            result.extend(p)
    return result
