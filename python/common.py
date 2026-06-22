"""Shared substrate for the two search strategies.

Holds the pieces that are genuinely common: the `Hint` value object, the hint /
list predicates (identical across the old python-base / improved / indexed), and —
crucially — the **shared base loader**.

`load_base(lang, n)` reads each word file once and runs `unidecode` once per word,
caching `list[(word, normalized)]` per `(lang, length)`. Both strategies build their
specialized indexes *from this base*, so the dominant index-build cost (file IO +
normalization) is paid once per length total, not once per strategy. See the plan's
"Index building: share the base, specialize lazily".
"""

import logging
import os
from pathlib import Path
from typing import List

import unidecode

logger = logging.getLogger("search")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

_ASSETS_ROOT = Path(os.environ.get("ASSETS_ROOT") or str(Path(__file__).parent.parent / "assets"))

# Shared base: (word, normalized) per (lang, length). File read once, unidecode once.
_base_cache: dict[str, list[tuple[str, str]]] = {}


def load_base(lang: str, nb_car: int) -> list[tuple[str, str]]:
    """Words of length `nb_car` as `(word, normalized)` tuples, cached per key.
    Missing file → []. Accent-free words share one string for word and normalized."""
    key = f"{lang}/{nb_car}"
    if key not in _base_cache:
        logger.info("base load: %s", key)
        file_name = _ASSETS_ROOT / lang / f"{nb_car}.txt"
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                base: list[tuple[str, str]] = []
                for line in f:
                    word = line.strip()
                    if word:
                        normalized = unidecode.unidecode(word)
                        if normalized == word:
                            normalized = word  # share one string for accent-free words
                        base.append((word, normalized))
        except FileNotFoundError:
            base = []
        _base_cache[key] = base
    return _base_cache[key]


class Hint:
    pos: int
    car: str | None = None
    inverted: bool = False

    def __init__(self, pos, car=None, inverted=False):
        self.pos = pos
        self.car = car
        self.inverted = inverted

    def __repr__(self):
        return f"pos:{self.pos}, car:{self.car}, inverted:{self.inverted}"


def is_list_empty_or_full_of_none(lst):
    if not lst:
        return True
    return all(x is None or not x for x in lst)


def is_hint_list_empty_or_full_of_none(lst: List[Hint]):
    if not lst:
        return True
    return all(not x.car for x in lst)


def is_search_by_hint(word: str, hint_list: List[Hint] = None):
    """Returns False if word is empty; True if no hints; otherwise every pinned hint
    must match its position and every excluded hint must not match its position."""
    if not word:
        return False
    hint_list = hint_list or []
    if is_hint_list_empty_or_full_of_none(hint_list):
        return True
    for hint in (x for x in hint_list if x.car):
        if int(hint.pos) > len(word):
            if not hint.inverted:
                return False
        elif hint.inverted:
            if word[int(hint.pos) - 1] == hint.car:
                return False
        else:
            if word[int(hint.pos) - 1] != hint.car:
                return False
    return True
