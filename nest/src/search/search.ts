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

// WordList is one length's dictionary with the data the scan needs, computed
// once at load: each word, its accent-free form (for the letter-pool check)
// and its a–z letter counts (26 bytes per word in one flat array, for strict
// mode). Parallel arrays keep it compact — every worker holds its own copy.
export interface WordList {
  words: string[];
  norms: string[];
  freq: Uint8Array;
}

const EMPTY_LIST: WordList = { words: [], norms: [], freq: new Uint8Array(0) };

function buildWordList(words: string[]): WordList {
  const norms = new Array<string>(words.length);
  const freq = new Uint8Array(words.length * 26);
  words.forEach((word, i) => {
    const norm = unidecode(word);
    norms[i] = norm === word ? word : norm;
    for (let k = 0; k < norm.length; k++) {
      const c = norm.charCodeAt(k) - 97;
      if (c >= 0 && c < 26) freq[i * 26 + c]++;
    }
  });
  return { words, norms, freq };
}

// wordCache holds word lists keyed by "lang/length". Each key is written once
// and then read by many searches; stored lists are treated as immutable.
const wordCache = new Map<string, WordList>();

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

// loadWords returns the words for (lang, length); see loadWordList.
export function loadWords(lang: string, length: number): string[] {
  return loadWordList(lang, length).words;
}

// loadWordList returns the word list for (lang, length), reading it from disk
// on the first call and caching it afterwards. A missing file yields an empty
// list. An unsafe `lang` yields an empty list and is never cached.
export function loadWordList(lang: string, length: number): WordList {
  if (!isValidLang(lang)) {
    return EMPTY_LIST;
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

  const list = buildWordList(words);
  wordCache.set(key, list);
  return list;
}

// noLetters reports whether the letter pool imposes no constraint.
export function noLetters(letters: string[]): boolean {
  return letters.every((c) => c === '');
}

// noHints reports whether the hint list imposes no constraint.
export function noHints(hints: Hint[]): boolean {
  return hints.every((h) => h.letter == null || h.letter === '');
}

// LetterPool is a query's available letters, prepared once per search: a
// membership table for the pool check and a–z counts for strict mode. Each
// element of `letters` is one character; an element of several characters can
// never match a single letter.
export class LetterPool {
  private readonly ascii = new Uint8Array(128);
  private readonly other = new Set<number>();
  private readonly freq = new Int32Array(26);
  private readonly empty: boolean;

  constructor(letters: string[], private readonly strict: boolean) {
    let any = false;
    for (const l of letters) {
      if (!l) continue;
      const cp = l.codePointAt(0)!;
      if (String.fromCodePoint(cp).length !== l.length) continue;
      any = true;
      if (cp < 128) this.ascii[cp] = 1;
      else this.other.add(cp);
      if (cp >= 97 && cp <= 122) this.freq[cp - 97]++;
    }
    this.empty = !any;
  }

  // matches reports whether word `i` of `list` can be built from the pool:
  // every letter of its accent-free form is in the pool, and in strict mode no
  // a–z letter is needed more often than the pool holds it.
  matches(list: WordList, i: number): boolean {
    const norm = list.norms[i];
    if (norm === '' || this.empty) return false;
    for (let k = 0; k < norm.length; k++) {
      const c = norm.charCodeAt(k);
      if (c < 128) {
        if (!this.ascii[c]) return false;
      } else {
        const cp = norm.codePointAt(k)!;
        if (cp > 0xffff) k++;
        if (!this.other.has(cp)) return false;
      }
    }
    if (this.strict) {
      const base = i * 26;
      for (let c = 0; c < 26; c++) {
        if (list.freq[base + c] > this.freq[c]) return false;
      }
    }
    return true;
  }
}

// matchesContent reports whether `word` can be built from the letter pool. In
// strict mode each letter is consumed at most once. Convenience form of
// LetterPool.matches for one word; the scan prepares both once instead.
export function matchesContent(
  word: string,
  letters: string[],
  strict: boolean,
): boolean {
  return new LetterPool(letters, strict).matches(buildWordList([word]), 0);
}

// codePointAtPosition returns the code point at 1-indexed `position`, walking
// the string without allocating; undefined when outside the word.
function codePointAtPosition(word: string, position: number): number | undefined {
  if (position < 1) return undefined;
  let n = 0;
  for (let k = 0; k < word.length; k++) {
    const cp = word.codePointAt(k)!;
    if (cp > 0xffff) k++;
    if (++n === position) return cp;
  }
  return undefined;
}

// matchesHints reports whether `word` satisfies every positional hint.
export function matchesHints(word: string, hints: Hint[]): boolean {
  if (word === '') {
    return false;
  }
  if (noHints(hints)) {
    return true;
  }
  for (const h of hints) {
    if (h.letter == null || h.letter === '') {
      continue;
    }
    const actual = codePointAtPosition(word, h.position);
    if (actual === undefined) {
      // A pinned hint outside the word can never match; an excluded hint is
      // trivially satisfied (the character is absent). Positions are 1-indexed.
      if (!h.excluded) {
        return false;
      }
      continue;
    }
    if (h.excluded === (actual === h.letter.codePointAt(0))) {
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

  const list = loadWordList(lang, length);
  const words = list.words;
  const pool = new LetterPool(letters, strict);
  let start = 0;
  let end = words.length;
  if (chunkCount > 1) {
    const chunk = Math.ceil(words.length / chunkCount); // ceil keeps chunks contiguous
    start = Math.min(chunkIndex * chunk, words.length);
    end = Math.min(start + chunk, words.length);
  }

  // Only the predicates the query needs are evaluated.
  const result: string[] = [];
  for (let i = start; i < end; i++) {
    const word = words[i];
    const ok = emptyHints
      ? pool.matches(list, i)
      : emptyLetters
        ? matchesHints(word, hints)
        : pool.matches(list, i) && matchesHints(word, hints);
    if (ok) result.push(word);
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
