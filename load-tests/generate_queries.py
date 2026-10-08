"""Generate 500 diverse search queries for Artillery load testing."""
import csv
from pathlib import Path
import json
import random

# French-frequency-ordered letters for realistic word searches
LETTERS = list('eaiuosnrtlcdpmgfhbvqyzxjkw')
VOWELS = list('eaiuo')

random.seed(42)  # reproducible


def random_letters(n):
    pool = LETTERS.copy()
    random.shuffle(pool)
    letters = pool[:n]
    if not any(c in VOWELS for c in letters):
        letters[random.randrange(n)] = random.choice(VOWELS)
    return letters


rows = []
for _ in range(500):
    word_length = random.randint(4, 10)
    n_available = word_length + random.randint(0, 3)
    letters = random_letters(n_available)
    strict = random.random() < 0.3

    n_hints = random.choices([0, 1, 2], weights=[0.5, 0.35, 0.15])[0]
    hints = []
    positions_used = set()
    for _ in range(n_hints):
        pos = random.randint(1, word_length)
        if pos in positions_used:
            continue
        positions_used.add(pos)
        hints.append({
            "position": pos,
            "letter": random.choice(letters),
            "excluded": random.random() < 0.2,
        })

    rows.append({
        'wordLength': word_length,
        'letters': ''.join(letters),
        'strict': str(strict).lower(),
        'hints': json.dumps(hints),
    })

# Always write next to this script, wherever it is run from.
OUT = Path(__file__).parent / 'queries.csv'
with open(OUT, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['wordLength', 'letters', 'strict', 'hints'])
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} rows → {OUT}")
