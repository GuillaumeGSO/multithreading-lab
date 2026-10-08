"""SEARCH_MODE: every mode returns exactly the baseline's words, and an unknown
mode is rejected (the API would fail at startup)."""

import pytest

from common import Hint
from modes import MODES, resolve_mode

FILE_CASES = [
    dict(word_length=5, letters=list("elisa"), hints=[], strict=True),
    dict(word_length=5, letters=list("elisa"), hints=[Hint(1, "s")], strict=False),
    dict(word_length=7, letters=[], hints=[Hint(1, "a"), Hint(7, "e", excluded=True)], strict=False),
]
MANY_CASES = [
    dict(letters="guillaume", hints=[]),
    dict(letters="artes", hints=[Hint(1, "a")]),
]


@pytest.mark.parametrize("name", sorted(MODES))
@pytest.mark.parametrize("case", FILE_CASES)
def test_file_modes_match_baseline(name, case):
    expected = list(MODES["baseline"].search_file(lang="fr", **case))
    assert list(MODES[name].search_file(lang="fr", **case)) == expected
    assert expected  # the cases are chosen to return words


@pytest.mark.parametrize("name", sorted(MODES))
@pytest.mark.parametrize("case", MANY_CASES)
def test_many_modes_match_baseline(name, case):
    expected = list(MODES["baseline"].search_many(lang="fr", **case))
    assert list(MODES[name].search_many(lang="fr", **case)) == expected
    assert expected


def test_default_is_parallel(monkeypatch):
    monkeypatch.delenv("SEARCH_MODE", raising=False)
    assert resolve_mode().name == "parallel"


def test_mode_is_case_insensitive():
    assert resolve_mode(" Indexed ").name == "indexed"


@pytest.mark.parametrize("value", ["dispatcher", "fast", ""])
def test_unknown_mode_is_rejected(value):
    with pytest.raises(ValueError, match="unknown SEARCH_MODE"):
        resolve_mode(value)
