from pathlib import Path
import unidecode
from typing import List

_ASSETS_ROOT = Path(__file__).parent.parent / "assets"

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

def is_search_by_content(word: str, lst_car: List[str]=[], strict = False):
    """
    Returns False if word is not set
    Returns False if lstCar is empty
    Returns False if less caracters in lstCar than in word
    Returns True if each and every caracters are in lstCar
    """
    if not word:
        return False
    if is_list_empty_or_full_of_none(lst_car):
        return False

    word_no_accent = unidecode.unidecode(word)

    for car in word_no_accent:
        if car not in lst_car:
            return False
        else:
            if strict:
                lst_car.remove(car)
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
        if hint.inverted:
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

    file_name = _ASSETS_ROOT / lang / f"{nb_car}.txt"
    try:
        with open(file_name, "r", encoding="utf-8") as file_content:
            lines = file_content.readlines()
    except FileNotFoundError:
        return []

    for line in lines:
        word = line.strip()
        searchByContent = is_search_by_content(word, list(lst_car), strict)
        searchByHint = is_search_by_hint(word, lst_hint)
        if searchByContent and is_empty_hint:
            yield word
        elif is_empty_cars and searchByHint:
            yield word
        elif searchByContent and searchByHint:
            yield word


def search_in_many_files(lang="fr", cars="", lst_hint=[]):
    for i in reversed(range(1, len(cars)+1)):
        for m in search_in_file(lang=lang, nb_car=i, lst_car=list(cars), lst_hint=lst_hint):
            yield m
