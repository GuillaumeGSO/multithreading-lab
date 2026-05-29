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

Deterministic (fixed seed), written once to cases.json, so every language reads
identical inputs — keeping the cross-language correctness check intact.
Re-run after tuning SEED / sizes:  python3 gen_cases.py
"""

import json
import os
import random

SEED = 1234
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
VOWELS = "aeiou"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "cases.json")

rng = random.Random(SEED)


def pool(size: int) -> list[str]:
    """A letter pool of `size` distinct letters, vowel-biased so many words match."""
    if size == 0:
        return []
    letters = set(rng.sample(VOWELS, k=min(4, size)))
    while len(letters) < size:
        letters.add(rng.choice(ALPHABET))
    return sorted(letters)


def hints(count: int, max_pos: int, inverted_ratio: float) -> list[dict]:
    """`count` positional hints over positions [1, max_pos]. Inverted hints
    (word[pos] != car) keep most words matching; normal hints pin an exact
    letter. `inverted_ratio` is the share that are inverted."""
    out = []
    for _ in range(count):
        inverted = rng.random() < inverted_ratio
        out.append({
            "pos": rng.randint(1, max_pos),
            "car": rng.choice(ALPHABET),
            "inverted": inverted,
        })
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
        lst_car = pool(psize)
        lst_hint = hints(nh, nb_car, inv_ratio)
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
        letters = pool(min(clen, 26))
        while len(letters) < clen:
            letters.append(rng.choice(ALPHABET))
        rng.shuffle(letters)
        cars = "".join(letters[:clen])
        lst_hint = hints(nh, clen, inverted_ratio=1.0)
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
