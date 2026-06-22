"""The dispatcher's two guarantees:

1. **Routing** — /search/file goes to INDEXED iff a pinned hint is present, else SCAN;
   /search/many always goes to SCAN (the index barely helps /many but would build
   pos_index for every length — too costly for the memory budget).
2. **Equivalence** — the two strategies return byte-identical output for the same
   inputs. This is *why* dispatch is safe: picking a strategy can never change the
   result, only the speed.
"""

import pytest

from seek_words import (
    INDEXED,
    SCAN,
    Hint,
    choose_strategy,
    search_in_file,
    search_in_many_files,
)


# --- 1. Routing ---

@pytest.mark.parametrize("lst_hint, expected", [
    ([], SCAN),                                           # letters-only
    ([Hint(1, "a", inverted=True)], SCAN),                # excluded only
    ([Hint(1, "a")], INDEXED),                            # pinned
    ([Hint(1, "a"), Hint(2, "b", inverted=True)], INDEXED),  # mixed
    ([Hint(1)], SCAN),                                    # hint w/o letter ignored
])
def test_choose_strategy(lst_hint, expected):
    assert choose_strategy(lst_hint) is expected


def test_search_in_file_delegates_to_chosen(monkeypatch):
    calls = []

    def spy(name, real):
        def wrapper(*a, **k):
            calls.append(name)
            return real(*a, **k)
        return wrapper

    monkeypatch.setattr(INDEXED, "search_in_file", spy("indexed", INDEXED.search_in_file))
    monkeypatch.setattr(SCAN, "search_in_file", spy("scan", SCAN.search_in_file))

    list(search_in_file(lang="fr", nb_car=5, lst_hint=[Hint(1, "s")]))  # pinned -> indexed
    list(search_in_file(lang="fr", nb_car=5, lst_car=list("elisa")))    # letters-only -> scan
    list(search_in_file(lang="fr", nb_car=5, lst_car=list("elisa"), strict=True))  # strict, no pinned -> scan
    assert calls == ["indexed", "scan", "scan"]


def test_search_in_many_delegates_to_chosen(monkeypatch):
    calls = []

    def spy(name, real):
        def wrapper(*a, **k):
            calls.append(name)
            return real(*a, **k)
        return wrapper

    monkeypatch.setattr(INDEXED, "search_in_many_files", spy("indexed", INDEXED.search_in_many_files))
    monkeypatch.setattr(SCAN, "search_in_many_files", spy("scan", SCAN.search_in_many_files))

    list(search_in_many_files(lang="fr", cars="guillaume"))                       # no pinned -> scan
    list(search_in_many_files(lang="fr", cars="guillaume", lst_hint=[Hint(2, "u")]))  # pinned -> scan (always)
    assert calls == ["scan", "scan"]


# --- 2. Cross-strategy equivalence (the safety property) ---

EQUIV_FILE = [
    dict(nb_car=5, lst_car=list("elisa")),                                  # letters-only
    dict(nb_car=5, lst_car=list("elisa"), strict=True),                     # strict
    dict(nb_car=5, lst_hint=[Hint(1, "s"), Hint(3, "a")]),                  # pinned hints
    dict(nb_car=5, lst_car=list("elisa"), lst_hint=[Hint(1, "l")]),         # pinned + pool
    dict(nb_car=6, lst_hint=[Hint(2, "a", inverted=True)]),                 # excluded only
    dict(nb_car=7, lst_car=list("aeioustr")),                              # letters-only, longer
    dict(nb_car=8, lst_car=list("maisonre"), strict=True),                  # strict + pool
    dict(nb_car=9, lst_car=list("guillaume"), lst_hint=[Hint(1, "g"), Hint(3, "i", inverted=True)]),  # mixed
    dict(nb_car=99, lst_car=list("abc")),                                   # missing file -> []
]


@pytest.mark.parametrize("case", EQUIV_FILE)
def test_strategies_agree_file(case):
    a = list(INDEXED.search_in_file(lang="fr", **case))
    b = list(SCAN.search_in_file(lang="fr", **case))
    assert a == b


EQUIV_MANY = [
    dict(cars="guillaume"),
    dict(cars="guillaume", lst_hint=[Hint(4, "a")]),
    dict(cars="maisonre", lst_hint=[Hint(1, "m", inverted=True)]),
    dict(cars="arbiste", lst_hint=[Hint(2, "r"), Hint(5, "x", inverted=True)]),
]


@pytest.mark.parametrize("case", EQUIV_MANY)
def test_strategies_agree_many(case):
    a = list(INDEXED.search_in_many_files(lang="fr", **case))
    b = list(SCAN.search_in_many_files(lang="fr", **case))
    assert a == b
