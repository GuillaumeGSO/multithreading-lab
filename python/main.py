import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from seek_words import Hint, search_in_file, search_in_many_files


def timeit(fn):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = list(fn(*args, **kwargs))
        elapsed_ms = (time.perf_counter() - start) * 1000
        return result, elapsed_ms
    return wrapper


timed_file = timeit(search_in_file)
timed_many = timeit(search_in_many_files)


@dataclass
class TestCase:
    name: str
    description: str
    params: str
    fn: Callable
    kwargs: dict


@dataclass
class TestResult:
    case: TestCase
    words: list[str]
    elapsed_ms: float


CASES: list[TestCase] = [
    TestCase(
        name="Letters strict — anagrams of 'elisa'",
        description="5-letter French words that are exact anagrams of 'elisa' (each letter used once)",
        params="lang=fr, nb_car=5, lst_car=list('elisa'), strict=True",
        fn=timed_file,
        kwargs=dict(lang="fr", nb_car=5, lst_car=list("elisa"), strict=True),
    ),
    TestCase(
        name="Letters open — anagrams of 'elisa'",
        description="5-letter French words that are exact anagrams of 'elisa' (may repeat letters)",
        params="lang=fr, nb_car=5, lst_car=list('elisa'), strict=False",
        fn=timed_file,
        kwargs=dict(lang="fr", nb_car=5, lst_car=list("elisa"), strict=False),
    ),
    TestCase(
        name="Hint only — pattern s_a_e",
        description="5-letter words with 's' at pos 1, 'a' at pos 3, 'e' at pos 5",
        params="lang=fr, nb_car=5, lst_hint=[Hint(1,'s'), Hint(3,'a'), Hint(5,'e')]",
        fn=timed_file,
        kwargs=dict(lang="fr", nb_car=5, lst_hint=[Hint(1, "s"), Hint(3, "a"), Hint(5, "e")]),
    ),
    TestCase(
        name="Letters + 2 hints",
        description="5-letter words from 'elisa' letters, starting with 'l' and ending with 's'",
        params="lang=fr, nb_car=5, lst_car=list('elisa'), lst_hint=[Hint(1,'l'), Hint(5,'s')]",
        fn=timed_file,
        kwargs=dict(
            lang="fr",
            nb_car=5,
            lst_car=list("elisa"),
            lst_hint=[Hint(1, "l"), Hint(5, "s")],
        ),
    ),
    TestCase(
        name="Inverted hints + letters",
        description="5-letter words from 'elisa' letters, 'l' not at pos 1, 'e' not at pos 3",
        params="lang=fr, nb_car=5, lst_car=list('elisa'), lst_hint=[Hint(1,'l',inverted=True), Hint(3,'e',inverted=True)]",
        fn=timed_file,
        kwargs=dict(
            lang="fr",
            nb_car=5,
            lst_car=list("elisa"),
            lst_hint=[Hint(1, "l", inverted=True),Hint(2, "l", inverted=True), Hint(3, "e", inverted=True)],
        ),
    ),
    TestCase(
        name="Strict + hint — anagrams of 'elisa' with 'a' at pos 3",
        description="Exact anagrams of 'elisa' where the 3rd letter is 'a'",
        params="lang=fr, nb_car=5, lst_car=list('elisa'), lst_hint=[Hint(3,'a')], strict=True",
        fn=timed_file,
        kwargs=dict(
            lang="fr",
            nb_car=5,
            lst_car=list("elisa "),
            lst_hint=[Hint(4, "a")],
            strict=True,
        ),
    ),
    TestCase(
        name="Multi-length — words from 'guillaume' letters",
        description="Words of any length (1-9) using only the letters from 'guillaume'",
        params="lang=fr, cars='guillaume'",
        fn=timed_many,
        kwargs=dict(lang="fr", cars="guillaume"),
    ),
    TestCase(
        name="Multi-length with hint — words from 'guillaume' letters with 'a' at pos 4",
        description="Words of any length (1-9) using only the letters from 'guillaume', with 'a' at position 4",
        params="lang=fr, cars='guillaume', lst_hint=[Hint(4, 'a'),Hint(1, 'a', inverted=True)]",
        fn=timed_many,
        kwargs=dict(lang="fr", cars="guillaume", lst_hint=[Hint(4, "a"), Hint(1, "a", inverted=True)]),
    ),
]


def run_tests() -> list[TestResult]:
    results = []
    for case in CASES:
        words, elapsed_ms = case.fn(**case.kwargs)
        result = TestResult(case=case, words=words, elapsed_ms=elapsed_ms)
        print(f"Test '{case.name}' found {len(words)} words in {elapsed_ms:.2f} ms")
        results.append(result)
    return results


def generate_report(results: list[TestResult]) -> str:
    lines = [
        "# seek_words Integration Report",
        f"_{date.today()}_",
        "",
        "## Summary",
        "",
        "| # | Test | Count | Time |",
        "|---|------|-------|------|",
    ]

    for i, r in enumerate(results, 1):
        lines.append(f"| {i} | {r.case.name} | {len(r.words)} words | {r.elapsed_ms:.2f} ms |")

    lines += ["", "---", "", "## Details", ""]

    for i, r in enumerate(results, 1):
        lines += [
            f"### {i}. {r.case.name}",
            "",
            f"_{r.case.description}_",
            "",
            f"**Params**: `{r.case.params}`  ",
            f"**Time**: {r.elapsed_ms:.2f} ms | **Count**: {len(r.words)}",
            "",
        ]
        if r.words:
            lines.append(", ".join(f"`{w}`" for w in r.words))
        else:
            lines.append("_No results._")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    results = run_tests()
    report = generate_report(results)
    print(report)
    report_path = Path(__file__).parent / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to {report_path}")
