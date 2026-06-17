#!/usr/bin/env python3
"""Deterministically generate a heavier, hint-dense cases.json.

The hand-written cases were too light: searches finished before thread setup
paid off. These cases hit the big word files (lengths 8-13 hold 50k-65k words
each) AND lean hard on positional hints, because the brute-force algorithm runs
the hint check for *every word unconditionally* (no short-circuit with the
content check) — so each extra hint adds a full per-word cost across the whole
file. That is the dominant compute under brute force, and it is exactly what the
positional index in python-indexed is built to skip (a nice contrast in the
chart).

Design choices:
  * Many hints per case (file: 4-10; many: 5-12).
  * Some "hint-only" file cases (no letter pool) so the hint path is the *entire*
    cost, isolating it.
  * /search/many hints are inverted-heavy: a normal hint at position N forces
    words of length >= N (shrinking the fan-out), while inverted hints leave all
    lengths in play, so every length file is still scanned with the full hint cost.
  * Each case is **seeded from a real word** picked from the dictionary, then its
    pool and hints are derived from that word — so every case is guaranteed to
    return >= 1 result while keeping the scan cost (file length, hint count,
    inverted ratio) identical. Seeds are accent-free (^[a-z]+$) words because the
    content check unidecodes the word but the hint check compares raw characters;
    ASCII-only seeds keep the two in agreement.

Deterministic (fixed seed), written once to cases.json, so every language reads
identical inputs — keeping the cross-language correctness check intact.
Re-run after tuning SEED / sizes:  python3 gen_cases.py
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

rng = random.Random(SEED)


def pick_word(lang: str, length: int) -> str:
    """A random accent-free (^[a-z]+$) word of `length`. ASCII-only so the
    content check (which unidecodes the word) and the hint check (which compares
    raw characters) agree — letting us seed both the pool and the hints from it."""
    path = os.path.join(ASSETS_ROOT, lang, f"{length}.txt")
    with open(path, encoding="utf-8") as f:
        words = [w for w in (line.strip() for line in f) if ASCII_WORD.match(w)]
    if not words:
        raise SystemExit(f"no accent-free word of length {length} in {lang}")
    return rng.choice(words)


def seeded_pool(word: str, size: int, strict: bool) -> list[str]:
    """A letter pool of `size` letters that `word` satisfies under the content
    check. Always contains all of `word`'s letters — its exact *multiset* when
    `strict` (the check consumes each matched letter), or just its distinct
    letters otherwise — padded with extra random letters up to `size`.
    `size == 0` means a hint-only case (no content check)."""
    if size == 0:
        return []
    if strict:
        letters = list(word)
        pad = [c for c in ALPHABET if c not in word]
        rng.shuffle(pad)
        letters += pad[:max(0, size - len(letters))]
        rng.shuffle(letters)
        return letters
    letters = set(word)
    while len(letters) < size:
        letters.add(rng.choice(ALPHABET))
    return sorted(letters)


def seeded_hints(word: str, count: int, inverted_ratio: float) -> list[dict]:
    """`count` hints on **distinct** positions, derived from `word` so `word`
    satisfies every one: a non-inverted hint pins `word[pos]`; an inverted hint
    forbids a letter `word` does *not* have at that position. `inverted_ratio` is
    the share that are inverted. Distinct positions keep hints non-contradictory."""
    out = []
    positions = rng.sample(range(1, len(word) + 1), k=min(count, len(word)))
    for pos in positions:
        actual = word[pos - 1]
        if rng.random() < inverted_ratio:
            car = rng.choice([c for c in ALPHABET if c != actual])
            inverted = True
        else:
            car = actual
            inverted = False
        out.append({"pos": pos, "car": car, "inverted": inverted})
    return out


def main():
    cases = []

    # --- heavy single-file scans (axis B has 20k-65k words to split) ---
    file_specs = [
        # (nb_car, pool_size (0 = hint-only), strict, n_hints, inverted_ratio)
        (8, 20, False, 4, 0.5),
        (9, 18, False, 6, 0.7),
        (10, 0, False, 8, 0.85),   # hint-only — pure hint cost
        (11, 16, True, 5, 0.6),
        (12, 0, False, 10, 0.9),   # hint-only, very hint-dense
        (13, 26, False, 4, 0.5),
    ]
    for nb_car, psize, strict, nh, inv_ratio in file_specs:
        seed = pick_word("fr", nb_car)
        lst_car = seeded_pool(seed, psize, strict)
        lst_hint = seeded_hints(seed, nh, inv_ratio)
        kind = "hint-only" if psize == 0 else f"pool={psize}"
        name = f"file len={nb_car} {kind} {nh}hints" + (" strict" if strict else "")
        cases.append({
            "name": name, "kind": "file", "lang": "fr",
            "nb_car": nb_car, "lst_car": lst_car, "lst_hint": lst_hint, "strict": strict,
        })

    # --- heavy multi-length scans (axis A fans out over many lengths) ---
    # All-inverted hints so the min-length stays 1 and every length is scanned.
    many_specs = [
        # (cars_len, n_hints)
        (14, 5),
        (16, 7),
        (18, 6),
        (18, 9),
        (20, 8),
        (22, 12),
    ]
    for clen, nh in many_specs:
        seed = pick_word("fr", clen)
        # cars is both the letter pool and the max length scanned (len(cars)), so
        # build it to length clen and include every letter of the seed word.
        letters = list(dict.fromkeys(seed))          # seed's distinct letters
        pad = [c for c in ALPHABET if c not in seed]
        rng.shuffle(pad)
        while len(letters) < clen:
            letters.append(pad.pop())
        rng.shuffle(letters)
        cars = "".join(letters)
        lst_hint = seeded_hints(seed, nh, inverted_ratio=1.0)
        name = f"many cars={clen} {nh}hints(inv)"
        cases.append({
            "name": name, "kind": "many", "lang": "fr",
            "cars": cars, "lst_hint": lst_hint,
        })

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {OUT} — {len(cases)} cases "
          f"({sum(c['kind']=='file' for c in cases)} file, {sum(c['kind']=='many' for c in cases)} many)")


if __name__ == "__main__":
    main()
