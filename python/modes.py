"""SEARCH_MODE: which implementation the live API serves.

Every language in this lab gives the three modes the same meaning, so the HTTP
comparison runs the same algorithm and the same concurrency in each one:

    baseline  single-threaded scan (/many scans the lengths one after another)
    parallel  scan split into SPLIT_DEGREE chunks per file; /many also fans out
              per length (GIL-bound here: threads add overhead, not speed)
    indexed   index dispatcher for /file (positional index when a pinned hint
              exists, scan otherwise); /many is the single-threaded scan

An unknown value raises ValueError, so a typo fails at startup instead of silently
serving a different mode.
"""

import os
from collections.abc import Callable, Iterable
from typing import NamedTuple

from parallel import search_in_file_parallel, search_in_many_parallel
from seek_words import SCAN, search_in_file, search_in_many_files

DEFAULT_MODE = "parallel"


class Mode(NamedTuple):
    name: str
    search_file: Callable[..., Iterable[str]]
    search_many: Callable[..., Iterable[str]]


MODES: dict[str, Mode] = {
    "baseline": Mode("baseline", SCAN.search_in_file, SCAN.search_in_many_files),
    "parallel": Mode("parallel", search_in_file_parallel, search_in_many_parallel),
    "indexed": Mode("indexed", search_in_file, search_in_many_files),
}


def resolve_mode(value: str | None = None) -> Mode:
    """The Mode named by `value` (default: the SEARCH_MODE env var, else parallel)."""
    name = (value if value is not None else os.environ.get("SEARCH_MODE") or DEFAULT_MODE).strip().lower()
    if name not in MODES:
        raise ValueError(f"unknown SEARCH_MODE {name!r}; expected one of {', '.join(MODES)}")
    return MODES[name]
