"""Correctness guard: the threaded variants must return byte-identical output
(same words, same order) as the sequential dispatcher baseline, for every split
degree. This keeps the parallel/GIL-demo path safe even though it always runs on
the scan strategy while the baseline may dispatch to the index.
"""

import pytest

from seek_words import Hint, search_in_file, search_in_many_files
from parallel import search_in_file_parallel, search_in_many_parallel

FILE_CASES = [
    dict(lang="fr", nb_car=5, lst_car=list("elisa"), strict=True),
    dict(lang="fr", nb_car=5, lst_car=list("elisa"), strict=False),
    dict(lang="fr", nb_car=5, lst_hint=[Hint(1, "s"), Hint(3, "a"), Hint(5, "e")]),
    dict(lang="fr", nb_car=5, lst_car=list("elisa"), lst_hint=[Hint(1, "l"), Hint(5, "s")]),
    dict(lang="fr", nb_car=99, lst_car=list("abc")),  # missing file -> []
]

MANY_CASES = [
    dict(lang="fr", cars="guillaume"),
    dict(lang="fr", cars="guillaume", lst_hint=[Hint(4, "a"), Hint(1, "a", inverted=True)]),
]


@pytest.mark.parametrize("threads", [1, 2, 3, 5])
@pytest.mark.parametrize("case", FILE_CASES)
def test_file_parallel_matches_baseline(case, threads):
    expected = list(search_in_file(**case))
    assert search_in_file_parallel(threads=threads, **case) == expected


@pytest.mark.parametrize("threads", [1, 2, 3])
@pytest.mark.parametrize("case", MANY_CASES)
def test_many_parallel_matches_baseline(case, threads):
    expected = list(search_in_many_files(**case))
    # threads controls the inner split: 1 == fanout, >1 == nested.
    assert search_in_many_parallel(threads=threads, **case) == expected
