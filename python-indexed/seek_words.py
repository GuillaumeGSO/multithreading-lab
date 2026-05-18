import logging
import os
from collections import Counter
from pathlib import Path
from typing import List

import unidecode

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

_ASSETS_ROOT = Path(os.environ.get("ASSETS_ROOT") or str(Path(__file__).parent.parent / "assets"))

_word_cache: dict[str, list[str]] = {}
# pos_index[key][pos][char] → frozenset of words with that char at that 1-based position
_pos_index: dict[str, dict[int, dict[str, frozenset]]] = {}
# freq_index[key] → list of (original_word, Counter(normalized_word))
_freq_index: dict[str, list[tuple[str, Counter]]] = {}

_index_calls: dict[str, int] = {}   # total calls per key
_index_hits: dict[str, int] = {}    # hits (index already built) per key
_LOG_EVERY = 50                      # log hit rate every N calls per key


def _load_words(lang: str, nb_car: int) -> list[str]:
    key = f"{lang}/{nb_car}"
    if key not in _word_cache:
        file_name = _ASSETS_ROOT / lang / f"{nb_car}.txt"
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                words = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            words = []
        _word_cache[key] = words
    return _word_cache[key]


def _ensure_index(lang: str, nb_car: int) -> None:
    key = f"{lang}/{nb_car}"
    _index_calls[key] = _index_calls.get(key, 0) + 1
    if key in _pos_index:
        _index_hits[key] = _index_hits.get(key, 0) + 1
        calls = _index_calls[key]
        if calls % _LOG_EVERY == 0:
            pct = _index_hits[key] / calls * 100
            logger.info("index stats [%s] — hit rate %.1f%% (%d hits / %d calls)", key, pct, _index_hits[key], calls)
        return

    logger.info("index build: %s", key)
    words = _load_words(lang, nb_car)
    pos_idx: dict[int, dict[str, set]] = {pos: {} for pos in range(1, nb_car + 1)}
    freq_idx: list[tuple[str, Counter]] = []

    for word in words:
        normalized = unidecode.unidecode(word)
        freq_idx.append((word, Counter(normalized)))
        for pos in range(1, nb_car + 1):
            char = word[pos - 1]
            if char not in pos_idx[pos]:
                pos_idx[pos][char] = set()
            pos_idx[pos][char].add(word)

    _pos_index[key] = {
        pos: {c: frozenset(s) for c, s in chars.items()}
        for pos, chars in pos_idx.items()
    }
    _freq_index[key] = freq_idx


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


def is_search_by_content(word: str, lst_car: List[str] = [], strict=False):
    if not word:
        return False
    if is_list_empty_or_full_of_none(lst_car):
        return False
    word_no_accent = unidecode.unidecode(word)
    for car in word_no_accent:
        if car not in lst_car:
            return False
        if strict:
            lst_car.remove(car)
    return True


def is_search_by_hint(word: str, hint_list: List[Hint] = []):
    if not word:
        return False
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


def search_in_file(lang="fr", nb_car=0, lst_car: List[str] = [], lst_hint: List[Hint] = [], strict=False):
    is_empty_hint = is_hint_list_empty_or_full_of_none(lst_hint)
    is_empty_cars = is_list_empty_or_full_of_none(lst_car)
    if nb_car == 0 or (is_empty_cars and is_empty_hint):
        raise Exception("Parameters lstCar et lstHint cannot be empty at the same time")

    _ensure_index(lang, nb_car)
    key = f"{lang}/{nb_car}"
    pos_idx = _pos_index[key]
    freq_idx = _freq_index[key]

    # Build candidate set from positional index
    candidates: frozenset | None = None
    if not is_empty_hint:
        active_hints = [h for h in lst_hint if h.car]
        for hint in active_hints:
            if hint.inverted:
                continue
            pos = int(hint.pos)
            if pos > nb_car:
                # Normal hint beyond word length — nothing can match
                return
            hint_set = pos_idx.get(pos, {}).get(hint.car, frozenset())
            candidates = hint_set if candidates is None else candidates & hint_set

        if candidates is None:
            candidates = frozenset(w for w, _ in freq_idx)

        for hint in active_hints:
            if not hint.inverted:
                continue
            pos = int(hint.pos)
            if pos > nb_car:
                continue  # inverted hint beyond word length — no effect
            excluded = pos_idx.get(pos, {}).get(hint.car, frozenset())
            candidates = candidates - excluded

    # Filter by letter availability
    if not is_empty_cars:
        query_counter = Counter(lst_car)
        query_set = set(lst_car)
        for word, word_counter in freq_idx:
            if candidates is not None and word not in candidates:
                continue
            if strict:
                if not all(word_counter[c] <= query_counter[c] for c in word_counter):
                    continue
            else:
                if not all(c in query_set for c in word_counter):
                    continue
            yield word
    else:
        # Hints only — yield candidates in original word-list order
        candidate_set = candidates
        for word, _ in freq_idx:
            if word in candidate_set:
                yield word


def search_in_many_files(lang="fr", cars="", lst_hint=[]):
    min_len = max(
        (int(h.pos) for h in lst_hint if h.car and not h.inverted),
        default=1
    )
    for i in reversed(range(min_len, len(cars) + 1)):
        yield from search_in_file(lang=lang, nb_car=i, lst_car=list(cars), lst_hint=lst_hint)
