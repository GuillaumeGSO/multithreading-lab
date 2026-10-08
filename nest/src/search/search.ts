// Pure, synchronous brute-force word search. It filters word lists by
// available letters, positional hints, and word length.
//
// This module has no NestJS or worker_threads dependency on purpose: it is
// imported directly by Jest tests and by the worker script alike. The file
// cache below is therefore per-process — every worker thread keeps its own.
import { readFileSync } from 'fs';
import { join } from 'path';
import unidecode from 'unidecode';

// Hint is a positional constraint on a word. `position` is 1-indexed.
// `letter` is the expected character; a null or empty `letter` imposes no
// constraint. When `excluded` is true the letter must NOT appear at `position`.
export interface Hint {
  position: number;
  letter: string | null;
  excluded: boolean;
}

// wordCache holds word lists keyed by "lang/length". Each key is written once
// and then read by many searches; stored arrays are treated as immutable.
const wordCache = new Map<string, string[]>();

// assetsRoot resolves the word-list directory, defaulting to a relative path.
function assetsRoot(): string {
  return process.env.ASSETS_ROOT || 'assets';
}

// LANG_PATTERN accepts only plain directory names under assets/. Anything else
// ("..", "/", an absolute path) would let `lang` escape the assets directory.
const LANG_PATTERN = /^[a-z]{2,8}$/;

// isValidLang reports whether `lang` is a safe dictionary directory name.
export function isValidLang(lang: string): boolean {
  return LANG_PATTERN.test(lang);
}

// loadWords returns the word list for (lang, length), reading it from disk on
// the first call and caching it afterwards. A missing file yields an empty list.
// An unsafe `lang` yields an empty list and is never cached.
export function loadWords(lang: string, length: number): string[] {
  if (!isValidLang(lang)) {
    return [];
  }
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
  return hints.every((h) => h.letter == null || h.letter === '');
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
  // match their plain-ASCII equivalents (compared code point by code point after Unidecode).
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
    if (h.letter == null || h.letter === '') {
      continue;
    }
    if (h.position < 1 || h.position > runes.length) {
      // A pinned hint outside the word can never match; an excluded hint is
      // trivially satisfied (the character is absent). Positions are 1-indexed.
      if (!h.excluded) {
        return false;
      }
      continue;
    }
    const letter = [...h.letter][0];
    if (h.excluded) {
      if (runes[h.position - 1] === letter) {
        return false;
      }
    } else if (runes[h.position - 1] !== letter) {
      return false;
    }
  }
  return true;
}

// inFileRange scans a contiguous chunk of one length's word list (axis B —
// intra-file split). The file is divided into `chunkCount` equal contiguous
// chunks and only chunk `chunkIndex` is scanned. The worker computes its own
// chunk so the main thread never has to load the word list. Concatenating the
// chunks in index order yields exactly inFile's output. chunkCount<=1 scans the
// whole file.
export function inFileRange(
  lang: string,
  length: number,
  letters: string[],
  hints: Hint[],
  strict: boolean,
  chunkIndex = 0,
  chunkCount = 1,
): string[] {
  if (!isValidLang(lang)) {
    throw new Error(`invalid lang: ${JSON.stringify(lang)}`);
  }
  const emptyLetters = noLetters(letters);
  const emptyHints = noHints(hints);
  if (length === 0 || (emptyLetters && emptyHints)) {
    throw new Error('letters and hints cannot both be empty');
  }

  const words = loadWords(lang, length);
  let start = 0;
  let end = words.length;
  if (chunkCount > 1) {
    const chunk = Math.ceil(words.length / chunkCount); // ceil keeps chunks contiguous
    start = Math.min(chunkIndex * chunk, words.length);
    end = Math.min(start + chunk, words.length);
  }

  const result: string[] = [];
  for (let i = start; i < end; i++) {
    const word = words[i];
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
  return inFileRange(lang, length, letters, hints, strict, 0, 1);
}

// planLengths derives the word-length range a /search/many request must scan.
// `maxLen` is the code-point count of `letters`; `minLen` is the largest
// position among pinned hints carrying a letter (excluded hints do not
// constrain the minimum). It does no file I/O, so it is safe on the main thread.
export function planLengths(
  letters: string,
  hints: Hint[],
): { minLen: number; maxLen: number; pool: string[] } {
  const runes = [...letters];
  const maxLen = runes.length;
  let minLen = 1;
  for (const h of hints) {
    if (h.letter != null && h.letter !== '' && !h.excluded && h.position > minLen) {
      minLen = h.position;
    }
  }
  return { minLen, maxLen, pool: runes };
}

// inManyFiles returns words of every length from len(letters) down to the minimum
// length implied by the hints, ordered longest-first. This is the synchronous
// reference used by tests; the service fans the per-length scans out across the
// worker pool instead.
export function inManyFiles(
  lang: string,
  letters: string,
  hints: Hint[],
): string[] {
  const { minLen, maxLen, pool } = planLengths(letters, hints);
  if (maxLen < minLen) {
    return [];
  }
  const result: string[] = [];
  for (let length = maxLen; length >= minLen; length--) {
    result.push(...inFile(lang, length, pool, hints, false));
  }
  return result;
}
