"""ScanStrategy — the lean on-load scan.

The scan iterates the shared `common.load_base` `(word, normalized, freq)` tuples
directly — it stores **no** per-word superstructure of its own. The per-request scan is
O(vocabulary) but with a cheap per-word predicate: a membership test for non-strict
queries, or a 26-integer array comparison for strict queries (no Counter allocation —
the frequency array is precomputed in load_base). This wins when the index has nothing
to seed from: letters-only or excluded-hint-only queries.

The module-level `is_search_by_content` is also imported by `parallel.py` (the GIL-demo
threaded modes run on this scan data path).
"""


from common import (
    Hint,
    is_hint_list_empty_or_full_of_none,
    is_list_empty_or_full_of_none,
    is_search_by_hint,
    load_base,
)


def is_search_by_content(normalized_word: str, avail_set: set,
                         avail_arr: list[int] | None = None, strict: bool = False,
                         word_freq: bytes | None = None):
    """Does the word fit the available pool? Pure predicate, zero per-word allocation.

    Non-strict: every letter of the normalized word must be in the pool (membership).
    Strict: membership check first (fast early-exit for non-pool chars), then a
    fixed-cost 26-integer frequency comparison against the precomputed `word_freq`.
    """
    if not normalized_word:
        return False
    if not avail_set:
        return False
    if not all(char in avail_set for char in normalized_word):
        return False
    if strict:
        return all(wf <= af for wf, af in zip(word_freq, avail_arr))
    return True


def _build_avail_arr(avail: list[str]) -> list[int]:
    """26-int letter-frequency array for the query pool, built once per search call."""
    arr = [0] * 26
    for c in avail:
        i = ord(c) - 97
        if 0 <= i < 26:
            arr[i] += 1
    return arr


class ScanStrategy:
    name = "scan"

    def search_in_file(self, lang="fr", word_length=0, letters: list[str] | None = None,
                       hints: list[Hint] | None = None, strict=False):
        letters = letters or []
        hints = hints or []
        is_empty_hint = is_hint_list_empty_or_full_of_none(hints)
        is_empty_letters = is_list_empty_or_full_of_none(letters)
        if word_length == 0 or (is_empty_letters and is_empty_hint):
            raise ValueError("letters and hints cannot both be empty")

        # Build the available-letter pool once for the whole scan.
        avail = [c for c in letters if c]
        avail_set = set(avail)
        avail_arr = _build_avail_arr(avail) if strict else None

        for word, normalized_word, word_freq in load_base(lang, word_length):
            if is_empty_hint:  # letters non-empty here (guaranteed by the guard above)
                if is_search_by_content(normalized_word, avail_set, avail_arr, strict, word_freq):
                    yield word
            elif is_empty_letters:
                if is_search_by_hint(word, hints):
                    yield word
            elif (is_search_by_content(normalized_word, avail_set, avail_arr, strict, word_freq)
                  and is_search_by_hint(word, hints)):
                yield word

    def search_in_many_files(self, lang="fr", letters="", hints: list[Hint] | None = None):
        hints = hints or []
        min_len = max(
            (int(h.position) for h in hints if h.letter and not h.excluded),
            default=1,
        )
        for i in reversed(range(min_len, len(letters) + 1)):
            yield from self.search_in_file(lang=lang, word_length=i, letters=list(letters), hints=hints)
