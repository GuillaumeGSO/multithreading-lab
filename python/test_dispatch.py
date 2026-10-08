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

@pytest.mark.parametrize("hints, expected", [
    ([], SCAN),                                           # letters-only
    ([Hint(1, "a", excluded=True)], SCAN),                # excluded only
    ([Hint(1, "a")], INDEXED),                            # pinned
    ([Hint(1, "a"), Hint(2, "b", excluded=True)], INDEXED),  # mixed
    ([Hint(1)], SCAN),                                    # hint w/o letter ignored
])
def test_choose_strategy(hints, expected):
    assert choose_strategy(hints) is expected


def test_search_in_file_delegates_to_chosen(monkeypatch):
    calls = []

    def spy(name, real):
        def wrapper(*a, **k):
            calls.append(name)
            return real(*a, **k)
        return wrapper

    monkeypatch.setattr(INDEXED, "search_in_file", spy("indexed", INDEXED.search_in_file))
    monkeypatch.setattr(SCAN, "search_in_file", spy("scan", SCAN.search_in_file))

    list(search_in_file(lang="fr", word_length=5, hints=[Hint(1, "s")]))  # pinned -> indexed
    list(search_in_file(lang="fr", word_length=5, letters=list("elisa")))    # letters-only -> scan
    list(search_in_file(lang="fr", word_length=5, letters=list("elisa"), strict=True))  # strict, no pinned -> scan
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

    list(search_in_many_files(lang="fr", letters="guillaume"))                       # no pinned -> scan
    list(search_in_many_files(lang="fr", letters="guillaume", hints=[Hint(2, "u")]))  # pinned -> scan (always)
    assert calls == ["scan", "scan"]


# --- 2. Cross-strategy equivalence (the safety property) ---

EQUIV_FILE = [
    dict(word_length=5, letters=list("elisa")),                                  # letters-only
    dict(word_length=5, letters=list("elisa"), strict=True),                     # strict
    dict(word_length=5, hints=[Hint(1, "s"), Hint(3, "a")]),                  # pinned hints
    dict(word_length=5, letters=list("elisa"), hints=[Hint(1, "l")]),         # pinned + pool
    dict(word_length=6, hints=[Hint(2, "a", excluded=True)]),                 # excluded only
    dict(word_length=7, letters=list("aeioustr")),                              # letters-only, longer
    dict(word_length=8, letters=list("maisonre"), strict=True),                  # strict + pool
    dict(word_length=9, letters=list("guillaume"), hints=[Hint(1, "g"), Hint(3, "i", excluded=True)]),  # mixed
    dict(word_length=99, letters=list("abc")),                                   # missing file -> []
]


@pytest.mark.parametrize("case", EQUIV_FILE)
def test_strategies_agree_file(case):
    a = list(INDEXED.search_in_file(lang="fr", **case))
    b = list(SCAN.search_in_file(lang="fr", **case))
    assert a == b


EQUIV_MANY = [
    dict(letters="guillaume"),
    dict(letters="guillaume", hints=[Hint(4, "a")]),
    dict(letters="maisonre", hints=[Hint(1, "m", excluded=True)]),
    dict(letters="arbiste", hints=[Hint(2, "r"), Hint(5, "x", excluded=True)]),
]


@pytest.mark.parametrize("case", EQUIV_MANY)
def test_strategies_agree_many(case):
    a = list(INDEXED.search_in_many_files(lang="fr", **case))
    b = list(SCAN.search_in_many_files(lang="fr", **case))
    assert a == b
