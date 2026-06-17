import os
from pathlib import Path
import unidecode
from typing import List
from collections import Counter

_ASSETS_ROOT = Path(os.environ.get("ASSETS_ROOT") or str(Path(__file__).parent.parent / "assets"))

# Word indexes loaded once per (lang, length) key; subsequent requests skip disk I/O entirely.
# Each entry contains: (original_word, normalized_word, char_counter)
_word_cache: dict[str, list[tuple[str, str, Counter]]] = {}

def _load_word_indexes(lang: str, nb_car: int) -> list[tuple[str, str, Counter]]:
    """Load words and build indexes in a single loop: word, normalized_word, char_counter"""
    key = f"{lang}/{nb_car}"
    if key not in _word_cache:
        file_name = _ASSETS_ROOT / lang / f"{nb_car}.txt"
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                word_indexes = []
                for line in f:
                    word = line.strip()
                    if word:
                        normalized = unidecode.unidecode(word)
                        char_counter = Counter(normalized)
                        word_indexes.append((word, normalized, char_counter))
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

def is_search_by_content(normalized_word: str, word_counter: Counter, lst_car: List[str]=[], strict = False):
    """
    Returns False if normalized_word is not set
    Returns False if lstCar is empty
    Returns False if less caracters in lstCar than in word
    Returns True if each and every caracters are in lstCar
    """
    if not normalized_word:
        return False
    if is_list_empty_or_full_of_none(lst_car):
        return False

    if strict:
        lst_car_counter = Counter(lst_car)
        return all(word_counter[char] <= lst_car_counter[char] for char in word_counter)
    else:
        lst_car_set = set(lst_car)
        return all(char in lst_car_set for char in word_counter)
        
    return True


def is_search_by_hint(word: str, hint_list: List[Hint]=[]):
    """
    Returns False if word is not provided.
    Returns True if no hints are provided.
    Returns False if the word does not contain the character at the hint position.
    Returns False if the word has the character at the inverted hint position.
    Returns True if the word contains each letter of the hint at the correct position.
    """
    if not word:
        return False
    if is_hint_list_empty_or_full_of_none(hint_list):
        return True

    for hint in (x for x in hint_list if x.car):
        if int(hint.pos) > len(word):
            if not hint.inverted:
                return False
        elif hint.inverted:
            if word[int(hint.pos)-1] == hint.car:
                return False
        else:
            if word[int(hint.pos)-1] != hint.car:
                return False
    return True


def search_in_file(lang="fr", nb_car=0, lst_car: List[str]=[], lst_hint: List[Hint]=[], strict=False):
    is_empty_hint = is_hint_list_empty_or_full_of_none(lst_hint)
    is_empty_cars = is_list_empty_or_full_of_none(lst_car)
    if nb_car == 0 or (is_empty_cars and is_empty_hint):
        raise Exception(
            "Parameters lstCar et lstHint cannot be empty at the same time")

    for word, normalized_word, word_counter in _load_word_indexes(lang, nb_car):
        searchByContent = is_search_by_content(normalized_word, word_counter, list(lst_car), strict)
        searchByHint = is_search_by_hint(word, lst_hint)
        if searchByContent and is_empty_hint:
            yield word
        elif is_empty_cars and searchByHint:
            yield word
        elif searchByContent and searchByHint:
            yield word


def search_in_many_files(lang="fr", cars="", lst_hint=[]):
    min_len = max(
        (int(h.pos) for h in lst_hint if h.car and not h.inverted),
        default=1
    )
    for i in reversed(range(min_len, len(cars) + 1)):
        yield from search_in_file(lang=lang, nb_car=i, lst_car=list(cars), lst_hint=lst_hint)
