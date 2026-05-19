// Pure, synchronous brute-force word search — a verbatim port of
// go/search/search.go. It filters word lists by available letters, positional
// hints, and word length.
//
// This module has no NestJS or worker_threads dependency on purpose: it is
// imported directly by Jest tests and by the worker script alike. The file
// cache below is therefore per-process — every worker thread keeps its own.
import { readFileSync } from 'fs';
import { join } from 'path';
import unidecode from 'unidecode';

// Hint is a positional constraint on a word. `pos` is 1-indexed. `car` is the
// expected character; a null or empty `car` imposes no constraint. When
// `inverted` is true the character must NOT appear at `pos`.
export interface Hint {
  pos: number;
  car: string | null;
  inverted: boolean;
}

// wordCache holds word lists keyed by "lang/length". Each key is written once
// and then read by many searches; stored arrays are treated as immutable.
const wordCache = new Map<string, string[]>();

// assetsRoot resolves the word-list directory, defaulting to a relative path.
function assetsRoot(): string {
  return process.env.ASSETS_ROOT || 'assets';
}

// loadWords returns the word list for (lang, length), reading it from disk on
// the first call and caching it afterwards. A missing file yields an empty list.
export function loadWords(lang: string, length: number): string[] {
  const key = `${lang}/${length}`;
  const cached = wordCache.get(key);
  if (cached !== undefined) {
    return cached;
  }

  let words: string[] = [];
  const path = join(assetsRoot(), lang, `${length}.txt`);
  try {
    words = readFileSync(path, 'utf-8')
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line !== '');
  } catch {
    words = [];
  }

  wordCache.set(key, words);
  return words;
}

// noLetters reports whether the letter pool imposes no constraint.
export function noLetters(letters: string[]): boolean {
  return letters.every((c) => c === '');
}

// noHints reports whether the hint list imposes no constraint.
export function noHints(hints: Hint[]): boolean {
  return hints.every((h) => h.car == null || h.car === '');
}

// matchesContent reports whether `word` can be built from the letter pool. In
// strict mode each letter is consumed at most once. The caller must pass a copy
// of `letters`, since strict mode mutates the array.
export function matchesContent(
  word: string,
  letters: string[],
  strict: boolean,
): boolean {
  if (word === '' || noLetters(letters)) {
    return false;
  }
  // Iterate code points of the transliterated word so accented characters
  // match their plain-ASCII equivalents (matches Go's []rune over Unidecode).
  for (const r of unidecode(word)) {
    const idx = letters.indexOf(r);
    if (idx === -1) {
      return false;
    }
    if (strict) {
      letters.splice(idx, 1);
    }
  }
  return true;
}

// matchesHints reports whether `word` satisfies every positional hint.
export function matchesHints(word: string, hints: Hint[]): boolean {
  if (word === '') {
    return false;
  }
  if (noHints(hints)) {
    return true;
  }
  // Spread into code points so multi-byte characters index correctly.
  const runes = [...word];
  for (const h of hints) {
    if (h.car == null || h.car === '') {
      continue;
    }
    if (h.pos > runes.length) {
      // A normal hint past the word's end can never match; an inverted hint
      // is trivially satisfied (the character is absent).
      if (!h.inverted) {
        return false;
      }
      continue;
    }
    const car = [...h.car][0];
    if (h.inverted) {
      if (runes[h.pos - 1] === car) {
        return false;
      }
    } else if (runes[h.pos - 1] !== car) {
      return false;
    }
  }
  return true;
}

// inFile returns words of exactly `length` code points matching the letter
// pool and/or the positional hints. It throws when `length` is zero or when
// neither a letter pool nor a hint is provided.
export function inFile(
  lang: string,
  length: number,
  letters: string[],
  hints: Hint[],
  strict: boolean,
): string[] {
  const emptyLetters = noLetters(letters);
  const emptyHints = noHints(hints);
  if (length === 0 || (emptyLetters && emptyHints)) {
    throw new Error('letters and hints cannot both be empty');
  }

  const result: string[] = [];
  for (const word of loadWords(lang, length)) {
    // matchesContent mutates its array in strict mode, so clone per word.
    const byContent = matchesContent(word, [...letters], strict);
    const byHint = matchesHints(word, hints);
    if (byContent && emptyHints) {
      result.push(word);
    } else if (emptyLetters && byHint) {
      result.push(word);
    } else if (byContent && byHint) {
      result.push(word);
    }
  }
  return result;
}

// planLengths derives the word-length range a /search/many request must scan.
// `maxLen` is the code-point count of `cars`; `minLen` is the largest position
// among non-inverted hints carrying a character (inverted hints do not
// constrain the minimum). It does no file I/O, so it is safe on the main thread.
export function planLengths(
  cars: string,
  hints: Hint[],
): { minLen: number; maxLen: number; letters: string[] } {
  const carsRunes = [...cars];
  const maxLen = carsRunes.length;
  let minLen = 1;
  for (const h of hints) {
    if (h.car != null && h.car !== '' && !h.inverted && h.pos > minLen) {
      minLen = h.pos;
    }
  }
  return { minLen, maxLen, letters: carsRunes };
}

// inManyFiles returns words of every length from len(cars) down to the minimum
// length implied by the hints, ordered longest-first. This is the synchronous
// reference used by tests; the service fans the per-length scans out across the
// worker pool instead.
export function inManyFiles(
  lang: string,
  cars: string,
  hints: Hint[],
): string[] {
  const { minLen, maxLen, letters } = planLengths(cars, hints);
  if (maxLen < minLen) {
    return [];
  }
  const result: string[] = [];
  for (let length = maxLen; length >= minLen; length--) {
    result.push(...inFile(lang, length, letters, hints, false));
  }
  return result;
}
