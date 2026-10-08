"""Shared substrate for the two search strategies.

Holds the pieces that are genuinely common to both strategies: the `Hint` value
object, the hint / list predicates, and — crucially — the **shared base loader**.

`load_base(lang, n)` reads each word file once and runs `unidecode` once per word,
caching `list[(word, normalized, freq)]` per `(lang, length)`. `freq` is a 26-byte
letter-frequency array computed at load time so the strict-mode predicate pays zero
per-word allocation at query time. Both strategies build their specialized indexes
*from this base*, so the dominant index-build cost (file IO + normalization) is paid
once per length total, not once per strategy.
"""

import logging
import os
import re
from pathlib import Path
from typing import List

import unidecode

logger = logging.getLogger("search")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

_ASSETS_ROOT = Path(os.environ.get("ASSETS_ROOT") or str(Path(__file__).parent.parent / "assets"))

# Shared base: (word, normalized, freq) per (lang, length). File read once, unidecode once.
# freq is bytes(26): freq[i] = count of chr(i + ord('a')) in the normalized word.
_base_cache: dict[str, list[tuple[str, str, bytes]]] = {}

# A language code is a plain directory name under assets/. Anything else (``..``,
# ``/``, an absolute path) would let `lang` escape the assets directory.
_LANG_RE = re.compile(r"[a-z]{2,8}")


def check_lang(lang: str) -> None:
    """Raise ValueError unless `lang` is a safe dictionary directory name."""
    if not isinstance(lang, str) or not _LANG_RE.fullmatch(lang):
        raise ValueError(f"invalid lang: {lang!r}")


def load_base(lang: str, word_length: int) -> list[tuple[str, str, bytes]]:
    """Words of length `word_length` as `(word, normalized, freq)` tuples, cached per key.
    freq is a 26-byte letter-frequency array for the normalized form, computed once at
    load time so the strict-mode predicate needs no per-word Counter at query time.
    Missing file → []. Accent-free words share one string for word and normalized."""
    check_lang(lang)
    key = f"{lang}/{word_length}"
    if key not in _base_cache:
        logger.info("base load: %s", key)
        file_name = _ASSETS_ROOT / lang / f"{word_length}.txt"
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                base: list[tuple[str, str, bytes]] = []
                for line in f:
                    word = line.strip()
                    if word:
                        normalized = unidecode.unidecode(word)
                        if normalized == word:
                            normalized = word  # share one string for accent-free words
                        arr = [0] * 26
                        for c in normalized:
                            i = ord(c) - 97
                            if 0 <= i < 26:
                                arr[i] += 1
                        base.append((word, normalized, bytes(arr)))
        except FileNotFoundError:
            base = []
        _base_cache[key] = base
    return _base_cache[key]


class Hint:
    position: int
    letter: str | None = None
    excluded: bool = False

    def __init__(self, position, letter=None, excluded=False):
        # Positions are 1-indexed; 0 or below would silently index from the end.
        if int(position) < 1:
            raise ValueError(f"hint position must be >= 1, got {position}")
        self.position = position
        self.letter = letter
        self.excluded = excluded

    def __repr__(self):
        return f"position:{self.position}, letter:{self.letter}, excluded:{self.excluded}"


def is_list_empty_or_full_of_none(lst):
    if not lst:
        return True
    return all(x is None or not x for x in lst)


def is_hint_list_empty_or_full_of_none(lst: List[Hint]):
    if not lst:
        return True
    return all(not x.letter for x in lst)


def is_search_by_hint(word: str, hint_list: List[Hint] = None):
    """Returns False if word is empty; True if no hints; otherwise every pinned hint
    must match its position and every excluded hint must not match its position."""
    if not word:
        return False
    hint_list = hint_list or []
    if is_hint_list_empty_or_full_of_none(hint_list):
        return True
    for hint in (x for x in hint_list if x.letter):
        if int(hint.position) > len(word):
            if not hint.excluded:
                return False
        elif hint.excluded:
            if word[int(hint.position) - 1] == hint.letter:
                return False
        else:
            if word[int(hint.position) - 1] != hint.letter:
                return False
    return True
