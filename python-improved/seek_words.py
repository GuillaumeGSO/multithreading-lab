import logging
import os
from pathlib import Path
import unidecode
from typing import List
from collections import Counter

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

_ASSETS_ROOT = Path(os.environ.get("ASSETS_ROOT") or str(Path(__file__).parent.parent / "assets"))

# Word indexes loaded once per (lang, length) key; subsequent requests skip disk I/O entirely.
# Each entry is (original_word, normalized_word, char_set), where char_set is the set of
# unique normalized characters. The common non-strict search only needs membership of those
# unique chars, so a frozenset is lighter than a Counter and supports a direct subset test;
# strict mode rebuilds a Counter from normalized_word on demand (it is the rare path).
_word_cache: dict[str, list[tuple[str, str, frozenset]]] = {}

def _load_word_indexes(lang: str, nb_car: int) -> list[tuple[str, str, frozenset]]:
    """Load words and build the on-load index in one pass: (word, normalized_word, char_set)."""
    key = f"{lang}/{nb_car}"
    if key not in _word_cache:
        logger.info("index build: %s", key)
        file_name = _ASSETS_ROOT / lang / f"{nb_car}.txt"
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                word_indexes = []
                for line in f:
                    word = line.strip()
                    if word:
                        normalized = unidecode.unidecode(word)
                        if normalized == word:
                            normalized = word  # share one string for accent-free words
                        char_set = frozenset(normalized)
                        word_indexes.append((word, normalized, char_set))
        except FileNotFoundError:
            word_indexes = []
        _word_cache[key] = word_indexes
    return _word_cache[key]


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
    if all(x is None or not x for x in lst):
        return True
    return False

def is_hint_list_empty_or_full_of_none(lst: List[Hint]):
    if not lst:
        return True
    if all(not x.car for x in lst):
        return True
    return False

def is_search_by_content(word_chars: frozenset, normalized_word: str, avail_set: set,
                         avail_counter: Counter | None = None, strict=False):
    """Does the word fit the available pool? Pure predicate, no per-word allocation.

    word_chars     : precomputed set of the word's unique (normalized) characters
    normalized_word: only used to rebuild a Counter when strict
    avail_set      : pool of available letters, built once per scan by the caller
    avail_counter  : pool letter counts, built once per scan, required only when strict

    Returns False if the word is empty or the pool is empty.
    Non-strict: every distinct letter of the word must be in the pool.
    Strict: the pool must hold at least as many of each letter as the word needs.
    """
    if not word_chars:
        return False
    if not avail_set:
        return False
    if strict:
        word_counter = Counter(normalized_word)
        return all(word_counter[char] <= avail_counter[char] for char in word_counter)
    return word_chars <= avail_set


def is_search_by_hint(word: str, hint_list: List[Hint]=None):
    """
    Returns False if word is not provided.
    Returns True if no hints are provided.
    Returns False if the word does not contain the character at the hint position.
    Returns False if the word has the character at the inverted hint position.
    Returns True if the word contains each letter of the hint at the correct position.
    """
    if not word:
        return False
    hint_list = hint_list or []
    if is_hint_list_empty_or_full_of_none(hint_list):
        return True

    for hint in (x for x in hint_list if x.car):
        if hint.pos > len(word):
            if not hint.inverted:
                return False
        elif hint.inverted:
            if word[hint.pos-1] == hint.car:
                return False
        else:
            if word[hint.pos-1] != hint.car:
                return False
    return True


def search_in_file(lang="fr", nb_car=0, lst_car: List[str]=None, lst_hint: List[Hint]=None, strict=False):
    lst_car = lst_car or []
    lst_hint = lst_hint or []
    is_empty_hint = is_hint_list_empty_or_full_of_none(lst_hint)
    is_empty_cars = is_list_empty_or_full_of_none(lst_car)
    if nb_car == 0 or (is_empty_cars and is_empty_hint):
        raise Exception(
            "Parameters lstCar et lstHint cannot be empty at the same time")

    # Build the available-letter pool once for the whole scan (the `if c` keeps the
    # all-None/empty semantics of is_list_empty_or_full_of_none); counts only when strict.
    avail = [c for c in lst_car if c]
    avail_set = set(avail)
    avail_counter = Counter(avail) if strict else None

    for word, normalized_word, word_chars in _load_word_indexes(lang, nb_car):
        if is_empty_hint:  # cars are non-empty here (guaranteed by the guard above)
            if is_search_by_content(word_chars, normalized_word, avail_set, avail_counter, strict):
                yield word
        elif is_empty_cars:
            if is_search_by_hint(word, lst_hint):
                yield word
        elif (is_search_by_content(word_chars, normalized_word, avail_set, avail_counter, strict)
              and is_search_by_hint(word, lst_hint)):
            yield word


def search_in_many_files(lang="fr", cars="", lst_hint=None):
    lst_hint = lst_hint or []
    min_len = max(
        (int(h.pos) for h in lst_hint if h.car and not h.inverted),
        default=1
    )
    for i in reversed(range(min_len, len(cars) + 1)):
        yield from search_in_file(lang=lang, nb_car=i, lst_car=list(cars), lst_hint=lst_hint)
