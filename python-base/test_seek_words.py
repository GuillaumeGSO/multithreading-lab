import pytest
from seek_words import (
    Hint,
    is_list_empty_or_full_of_none,
    is_hint_list_empty_or_full_of_none,
    is_search_by_content,
    is_search_by_hint,
    search_in_file,
    search_in_many_files,
)


# --- is_list_empty_or_full_of_none ---

def test_list_empty():
    assert is_list_empty_or_full_of_none([]) is True

def test_list_all_none():
    assert is_list_empty_or_full_of_none([None, None]) is True

def test_list_has_values():
    assert is_list_empty_or_full_of_none(["a", "b"]) is False


# --- is_hint_list_empty_or_full_of_none ---

def test_hint_list_empty():
    assert is_hint_list_empty_or_full_of_none([]) is True

def test_hint_list_no_car():
    assert is_hint_list_empty_or_full_of_none([Hint(1), Hint(2)]) is True

def test_hint_list_has_car():
    assert is_hint_list_empty_or_full_of_none([Hint(1, "a")]) is False


# --- is_search_by_content ---

def test_content_empty_word():
    assert is_search_by_content("", ["a", "b"]) is False

def test_content_empty_letters():
    assert is_search_by_content("abc", []) is False

def test_content_match():
    assert is_search_by_content("ale", ["a", "l", "e", "s"]) is True

def test_content_letter_missing():
    assert is_search_by_content("zoo", ["a", "l", "e"]) is False

def test_content_strict_exact_anagram():
    assert is_search_by_content("aile", list("aile")) is True

def test_content_strict_rejects_repeated_letter():
    # "alle" needs two l's; pool has only one
    assert is_search_by_content("alle", list("ale"), strict=True) is False

def test_content_accent_stripped():
    # "île" normalises to "ile"; pool covers it
    assert is_search_by_content("île", ["i", "l", "e"]) is True


# --- is_search_by_hint ---

def test_hint_empty_word():
    assert is_search_by_hint("", [Hint(1, "a")]) is False

def test_hint_no_hints():
    assert is_search_by_hint("bonjour", []) is True

def test_hint_match():
    assert is_search_by_hint("salut", [Hint(1, "s")]) is True

def test_hint_no_match():
    assert is_search_by_hint("salut", [Hint(1, "a")]) is False

def test_hint_inverted_match_excludes():
    # "salut" has 's' at pos 1 → inverted hint rejects it
    assert is_search_by_hint("salut", [Hint(1, "s", inverted=True)]) is False

def test_hint_inverted_no_match_includes():
    # "salut" does not have 'a' at pos 1 → inverted hint passes
    assert is_search_by_hint("salut", [Hint(1, "a", inverted=True)]) is True

def test_hint_position_out_of_range_normal_excludes():
    # word length 3, hint at pos 4 → can never be satisfied
    assert is_search_by_hint("mot", [Hint(4, "a")]) is False

def test_hint_position_out_of_range_inverted_includes():
    # word length 3, inverted hint at pos 4 → trivially satisfied
    assert is_search_by_hint("mot", [Hint(4, "a", inverted=True)]) is True

def test_hint_car_none_ignored():
    # Hint with no car should not filter anything
    assert is_search_by_hint("bonjour", [Hint(1)]) is True

def test_hint_multiple_all_match():
    assert is_search_by_hint("salut", [Hint(1, "s"), Hint(5, "t")]) is True

def test_hint_multiple_one_fails():
    assert is_search_by_hint("salut", [Hint(1, "s"), Hint(5, "x")]) is False


# --- search_in_file (integration — uses real assets) ---

def test_search_file_raises_without_params():
    with pytest.raises(Exception):
        list(search_in_file(lang="fr", nb_car=0))

def test_search_file_raises_empty_cars_and_hints():
    with pytest.raises(Exception):
        list(search_in_file(lang="fr", nb_car=5))

def test_search_file_missing_file_returns_empty():
    result = list(search_in_file(lang="fr", nb_car=99, lst_car=list("abc")))
    assert result == []

def test_search_file_by_content():
    result = list(search_in_file(lang="fr", nb_car=5, lst_car=list("elisa"), strict=True))
    assert len(result) == 8
    assert "ailes" in result

def test_search_file_by_hint():
    result = list(search_in_file(lang="fr", nb_car=5, lst_hint=[Hint(1, "s"), Hint(3, "a"), Hint(5, "e")]))
    assert len(result) == 8
    assert "slave" in result

def test_search_file_content_and_hint():
    result = list(search_in_file(lang="fr", nb_car=5, lst_car=list("elisa"), lst_hint=[Hint(1, "l"), Hint(5, "s")]))
    assert len(result) == 11


# --- search_in_many_files (integration — uses real assets) ---

def test_search_many_all_lengths():
    result = list(search_in_many_files(lang="fr", cars="guillaume"))
    assert len(result) == 498

def test_search_many_skips_short_words_with_normal_hint():
    # Hint at pos 4 → words shorter than 4 letters must be excluded
    result = list(search_in_many_files(lang="fr", cars="guillaume", lst_hint=[Hint(4, "a")]))
    assert all(len(w) >= 4 for w in result)

def test_search_many_inverted_hint_includes_short_words():
    # Inverted hint at pos 4 → words shorter than 4 letters are still included
    result = list(search_in_many_files(lang="fr", cars="guillaume", lst_hint=[Hint(4, "z", inverted=True)]))
    assert any(len(w) < 4 for w in result)
