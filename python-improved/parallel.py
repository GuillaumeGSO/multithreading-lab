"""Parallel variants of the word search, used by both the live API (when
SEARCH_MODE=parallel) and the in-process benchmark.

These functions reuse the exact per-word predicates from ``seek_words`` — only
the *partitioning* of work across threads differs. A word list is split into
``N`` contiguous chunks scanned on separate threads and merged in index order,
so the output is byte-identical to the sequential ``search_in_file`` regardless
of thread timing.

NOTE (the lesson this module demonstrates): Python threads share one GIL, so
this intra-file split does not speed up the CPU-bound scan — it usually adds
overhead. Python scales at the process/API layer (uvicorn --workers) instead,
which is exactly why python-improved differs from python-base only under HTTP
load, not here.

This file is identical across python-base / python-improved / python-indexed
(all three expose the same predicate helpers and ``_load_words``).
"""

import os
import threading
from typing import List

from seek_words import (
    Hint,
    _load_words,
    is_hint_list_empty_or_full_of_none,
    is_list_empty_or_full_of_none,
    is_search_by_content,
    is_search_by_hint,
)


def split_degree() -> int:
    """Chunks per file (axis B). SPLIT_DEGREE env, default 2 ('halves')."""
    try:
        n = int(os.environ.get("SPLIT_DEGREE", "2"))
    except ValueError:
        n = 2
    return max(1, n)


def _matches(word: str, lst_car, lst_hint, strict, is_empty_cars, is_empty_hint) -> bool:
    by_content = is_search_by_content(word, list(lst_car), strict)
    by_hint = is_search_by_hint(word, lst_hint)
    if by_content and is_empty_hint:
        return True
    if is_empty_cars and by_hint:
        return True
    return by_content and by_hint


def _scan(words, lst_car, lst_hint, strict, is_empty_cars, is_empty_hint) -> List[str]:
    return [
        w for w in words
        if _matches(w, lst_car, lst_hint, strict, is_empty_cars, is_empty_hint)
    ]


def search_in_file_parallel(
    lang="fr", nb_car=0, lst_car: List[str] = [], lst_hint: List[Hint] = [],
    strict=False, threads: int | None = None,
) -> List[str]:
    """Intra-file split (axis B). Mirrors ``search_in_file`` but scans the word
    list in ``threads`` contiguous chunks. threads=1 runs inline (== baseline).
    """
    is_empty_hint = is_hint_list_empty_or_full_of_none(lst_hint)
    is_empty_cars = is_list_empty_or_full_of_none(lst_car)
    if nb_car == 0 or (is_empty_cars and is_empty_hint):
        raise Exception("Parameters lstCar et lstHint cannot be empty at the same time")

    words = _load_words(lang, nb_car)
    n = threads if threads is not None else split_degree()
    n = max(1, min(n, max(1, len(words))))

    if n == 1:
        return _scan(words, lst_car, lst_hint, strict, is_empty_cars, is_empty_hint)

    chunk = (len(words) + n - 1) // n  # ceil so chunks stay contiguous
    partials: list[list[str] | None] = [None] * n
    workers = []

    def work(idx: int, start: int, end: int) -> None:
        partials[idx] = _scan(
            words[start:end], lst_car, lst_hint, strict, is_empty_cars, is_empty_hint
        )

    for idx in range(n):
        start = idx * chunk
        end = min(start + chunk, len(words))
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
    lang="fr", cars="", lst_hint: List[Hint] = [], threads: int | None = None,
) -> List[str]:
    """Per-length fan-out (axis A). One thread per word length, longest first.

    ``threads`` controls the *inner* intra-file split each length uses:
      - threads=1  → fanout mode (per-length only, no intra-file split)
      - threads=N  → nested mode (threads spawning threads)
    Results are reassembled longest-first, matching ``search_in_many_files``.
    """
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
