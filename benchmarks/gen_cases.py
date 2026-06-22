#!/usr/bin/env python3
"""Deterministically generate a balanced, realistic cases.json.

Earlier versions used pathological inputs (20+ letter pools, 8-12 inverted hints)
to stress the brute-force scan — but no real letter-game query looks like that.
This version builds a *balanced grid* that mirrors actual usage, so the
indexed-vs-scan crossover it reveals reflects reality:

  * One seed word per length (4-13), drawn from the dictionary.
  * A realistic letter rack: the seed's distinct letters + ~3 decoys.
  * Four query shapes per length — the variable under study:
      none     - rack only, no positional hints
      normal   - rack + 2 'pinned'   hints (letter IS at this position)
      inverted - rack + 2 'excluded' hints (letter is NOT at this position)
      mixed    - rack + 1 pinned + 1 excluded
  * The same four shapes for a few realistic /search/many racks (7-9 letters).
  * A 'none-wide' letters-only case per length with a generous pool (~16 letters) —
    the "here are lots of letters, what can I build" query (large result set).
  * 'strict' /file variants of the 4 shapes (Scrabble/Countdown/anagram): a multiset
    tile rack, exact letter-count matching. strict is /file-only — /search/many has no
    strict parameter in this app.
  * 'nopool' /file variants (crossword): hints only, empty rack — known positions with
    letters otherwise unrestricted.

Each length uses ONE seed word for all four shapes, so the only thing that varies
within a length is the hint shape. Every case is seeded from a real accent-free
word (so it returns >= 1 result and the cross-language correctness check holds).
Deterministic (fixed seed).  Re-run after tuning:  python3 gen_cases.py
"""

import json
import os
import random
import re

SEED = 42
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "cases.json")
ASSETS_ROOT = os.path.join(HERE, "..", "assets")
ASCII_WORD = re.compile(r"^[a-z]+$")

RACK_DECOYS = 3                # extra letters beyond the seed's own, in every rack
N_HINTS = 2                    # hints in the normal / inverted variants (mixed = 1+1)
FILE_LENGTHS = range(4, 14)    # one /file case-group per length 4..13
MANY_RACKS = (7, 8, 9)         # realistic /search/many rack sizes
WIDE_POOL = 16                 # generous letters-only pool ("what can I build from these")

# The four query shapes under study, as (suffix, n_normal, n_inverted).
SHAPES = [
    ("none", 0, 0),
    ("normal", N_HINTS, 0),
    ("inverted", 0, N_HINTS),
    ("mixed", 1, 1),
]

rng = random.Random(SEED)


def pick_word(lang: str, length: int) -> str:
    """A random accent-free (^[a-z]+$) word of `length`. ASCII-only so the content
    check (which unidecodes the word) and the hint check (which compares raw
    characters) agree — letting us seed both the rack and the hints from it."""
    path = os.path.join(ASSETS_ROOT, lang, f"{length}.txt")
    with open(path, encoding="utf-8") as f:
        words = [w for w in (line.strip() for line in f) if ASCII_WORD.match(w)]
    if not words:
        raise SystemExit(f"no accent-free word of length {length} in {lang}")
    return rng.choice(words)


def make_rack(word: str, decoys: int = RACK_DECOYS) -> list[str]:
    """The seed word's distinct letters + `decoys` random extras (capped at 26).
    Always contains every letter of `word`, so `word` passes the (non-strict)
    content check and the case yields >= 1 result."""
    letters = set(word)
    pad = [c for c in ALPHABET if c not in letters]
    rng.shuffle(pad)
    letters.update(pad[: max(0, min(decoys, 26 - len(letters)))])
    return sorted(letters)


def make_wide_rack(word: str, size: int = WIDE_POOL) -> list[str]:
    """A generous pool of ~`size` distinct letters that still includes every letter
    of `word` (so the seed is always a result). Models the 'here are lots of letters,
    what can I build' query — a wider pool than the tight rack, so letters-only
    returns many words."""
    letters = set(word)
    pad = [c for c in ALPHABET if c not in letters]
    rng.shuffle(pad)
    while len(letters) < size and pad:
        letters.add(pad.pop())
    return sorted(letters)


def make_strict_rack(word: str, decoys: int = RACK_DECOYS) -> list[str]:
    """A *multiset* rack for strict mode: the seed's letters WITH their counts (so the
    seed passes the strict letter-count check) + a few decoys. Models a real tile rack
    (Scrabble/Countdown), where having two 'e' tiles matters."""
    letters = list(word)                       # keep repeats — strict compares counts
    pad = [c for c in ALPHABET if c not in word]
    rng.shuffle(pad)
    letters += pad[: max(0, decoys)]
    rng.shuffle(letters)
    return letters


def make_hints(word: str, n_normal: int, n_inverted: int) -> list[dict]:
    """`n_normal` pinned hints (pin word[pos]) + `n_inverted` excluded hints (forbid a
    letter `word` does NOT have at that position), on distinct positions seeded
    from `word` so `word` satisfies every one."""
    total = n_normal + n_inverted
    positions = rng.sample(range(1, len(word) + 1), k=min(total, len(word)))
    hints = []
    for i, pos in enumerate(positions):
        actual = word[pos - 1]
        if i < n_normal:
            hints.append({"pos": pos, "car": actual, "inverted": False})
        else:
            car = rng.choice([c for c in ALPHABET if c != actual])
            hints.append({"pos": pos, "car": car, "inverted": True})
    return hints


def main():
    cases = []

    # --- per-length /search/file grid: one seed per length, 4 shapes each ---
    for length in FILE_LENGTHS:
        seed = pick_word("fr", length)
        rack = make_rack(seed)
        for suffix, nn, ni in SHAPES:
            cases.append({
                "name": f"file len={length} {suffix}",
                "kind": "file", "lang": "fr",
                "nb_car": length, "lst_car": rack,
                "lst_hint": make_hints(seed, nn, ni), "strict": False,
            })

    # --- realistic /search/many grid: a rack of N letters, 4 shapes each ---
    for clen in MANY_RACKS:
        seed = pick_word("fr", clen)
        # cars is both the rack and the max length scanned (len(cars)); build it to
        # length clen from the seed's letters + decoys.
        letters = list(dict.fromkeys(seed))
        pad = [c for c in ALPHABET if c not in seed]
        rng.shuffle(pad)
        while len(letters) < clen:
            letters.append(pad.pop())
        rng.shuffle(letters)
        cars = "".join(letters)
        for suffix, nn, ni in SHAPES:
            cases.append({
                "name": f"many rack={clen} {suffix}",
                "kind": "many", "lang": "fr",
                "cars": cars, "lst_hint": make_hints(seed, nn, ni),
            })

    # --- generous-pool letters-only /file cases ("qwertyuiop"-style) ---
    # A wide rack, no hints: "give me every word I can build from these letters".
    # Larger pool -> larger result set, so this checks the no-pinned -> scan rule still
    # holds when letters-only returns many words. Appended last so the cases above
    # stay byte-identical under the fixed seed.
    for length in FILE_LENGTHS:
        seed = pick_word("fr", length)
        cases.append({
            "name": f"file len={length} none-wide",
            "kind": "file", "lang": "fr",
            "nb_car": length, "lst_car": make_wide_rack(seed),
            "lst_hint": [], "strict": False,
        })

    # --- strict /file (Scrabble / Countdown / anagram): exact tile counts ---
    # strict changes only the content predicate, and the two strategies treat it very
    # differently (indexed compares PREcomputed Counters; scan REBUILDS Counter per
    # word), so this is where the no-pinned -> scan verdict could flip. Mirror the 4 rack
    # shapes, strict=True, with a multiset rack so the seed itself passes.
    # (/search/many has no strict parameter in this app, so strict is /file-only.)
    for length in FILE_LENGTHS:
        seed = pick_word("fr", length)
        rack = make_strict_rack(seed)
        for suffix, nn, ni in SHAPES:
            cases.append({
                "name": f"file len={length} {suffix} strict",
                "kind": "file", "lang": "fr",
                "nb_car": length, "lst_car": rack,
                "lst_hint": make_hints(seed, nn, ni), "strict": True,
            })

    # --- hint-only / no-pool /file (crossword): known positions, letters unrestricted ---
    # Empty rack: only the hints filter. Real crossword/Motus query. Pinned hints
    # present (normal, mixed), so the rule routes these to indexed — included to confirm
    # that holds when there is no content pre-filter at all.
    for length in FILE_LENGTHS:
        seed = pick_word("fr", length)
        for suffix, nn, ni in (("normal", N_HINTS, 0), ("mixed", 1, 1)):
            cases.append({
                "name": f"file len={length} {suffix} nopool",
                "kind": "file", "lang": "fr",
                "nb_car": length, "lst_car": [],
                "lst_hint": make_hints(seed, nn, ni), "strict": False,
            })

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)
        f.write("\n")
    nf = sum(c["kind"] == "file" for c in cases)
    nm = sum(c["kind"] == "many" for c in cases)
    print(f"wrote {OUT} — {len(cases)} cases ({nf} file, {nm} many)")


if __name__ == "__main__":
    main()
