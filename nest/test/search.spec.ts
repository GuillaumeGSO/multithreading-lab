// Pure-logic unit tests — no workers. Imports the algorithm directly and
// mirrors go/search/search_test.go: helper, content and hint matching, plus
// integration assertions against the real asset files.
import * as path from 'path';

// Point ASSETS_ROOT at the repo-root assets/ before any word list is loaded.
// search.ts reads this lazily, so setting it at module scope is sufficient.
process.env.ASSETS_ROOT = path.resolve(__dirname, '../../assets');

import {
  Hint,
  inFile,
  inManyFiles,
  loadWords,
  matchesContent,
  matchesHints,
  noHints,
  noLetters,
  planLengths,
} from '../src/search/search';

// h builds a Hint with a default non-inverted flag.
const h = (pos: number, car: string | null, inverted = false): Hint => ({
  pos,
  car,
  inverted,
});

describe('noLetters', () => {
  it('is true for an empty pool', () => {
    expect(noLetters([])).toBe(true);
  });
  it('is true when every entry is empty', () => {
    expect(noLetters(['', ''])).toBe(true);
  });
  it('is false when a letter is present', () => {
    expect(noLetters(['a', ''])).toBe(false);
  });
});

describe('noHints', () => {
  it('is true for an empty list', () => {
    expect(noHints([])).toBe(true);
  });
  it('is true when no hint carries a character', () => {
    expect(noHints([h(1, null), h(2, '')])).toBe(true);
  });
  it('is false when a hint carries a character', () => {
    expect(noHints([h(1, 's')])).toBe(false);
  });
});

describe('matchesContent', () => {
  it('rejects an empty word', () => {
    expect(matchesContent('', ['a', 'l', 'e'], false)).toBe(false);
  });
  it('rejects an empty pool', () => {
    expect(matchesContent('ale', [], false)).toBe(false);
  });
  it('matches when every letter is available', () => {
    expect(matchesContent('ale', ['a', 'l', 'e', 's'], false)).toBe(true);
  });
  it('rejects a word with a missing letter', () => {
    expect(matchesContent('zoo', ['a', 'l', 'e'], false)).toBe(false);
  });
  it('allows letter reuse in non-strict mode', () => {
    expect(matchesContent('aaa', ['a'], false)).toBe(true);
  });
  it('forbids letter reuse in strict mode', () => {
    expect(matchesContent('alle', ['a', 'l', 'e'], true)).toBe(false);
  });
  it('strips accents before matching', () => {
    expect(matchesContent('île', ['i', 'l', 'e'], false)).toBe(true);
  });
});

describe('matchesHints', () => {
  it('rejects an empty word', () => {
    expect(matchesHints('', [h(1, 's')])).toBe(false);
  });
  it('passes when there are no hints', () => {
    expect(matchesHints('salut', [])).toBe(true);
  });
  it('matches a positional hint', () => {
    expect(matchesHints('salut', [h(1, 's')])).toBe(true);
  });
  it('rejects a mismatched position', () => {
    expect(matchesHints('salut', [h(1, 'a')])).toBe(false);
  });
  it('rejects when an inverted hint is present at the position', () => {
    expect(matchesHints('salut', [h(1, 's', true)])).toBe(false);
  });
  it('passes when an inverted hint is absent at the position', () => {
    expect(matchesHints('salut', [h(1, 'a', true)])).toBe(true);
  });
  it('rejects a normal hint past the word end', () => {
    expect(matchesHints('sal', [h(4, 'x')])).toBe(false);
  });
  it('passes an inverted hint past the word end', () => {
    expect(matchesHints('sal', [h(4, 'x', true)])).toBe(true);
  });
  it('ignores a hint with no character', () => {
    expect(matchesHints('salut', [h(1, null)])).toBe(true);
  });
  it('requires every hint to match', () => {
    expect(matchesHints('salut', [h(1, 's'), h(2, 'a')])).toBe(true);
    expect(matchesHints('salut', [h(1, 's'), h(2, 'x')])).toBe(false);
  });
});

describe('loadWords', () => {
  it('returns an empty list for a missing file', () => {
    expect(loadWords('fr', 99)).toEqual([]);
  });
});

describe('inFile', () => {
  it('throws when length is zero', () => {
    expect(() => inFile('fr', 0, ['a'], [], false)).toThrow(
      'letters and hints cannot both be empty',
    );
  });
  it('throws when letters and hints are both empty', () => {
    expect(() => inFile('fr', 5, [], [], false)).toThrow(
      'letters and hints cannot both be empty',
    );
  });
  it('searches by content — "elisa" strict on 5-letter French words', () => {
    const words = inFile('fr', 5, ['e', 'l', 'i', 's', 'a'], [], true);
    expect(words).toHaveLength(8);
    expect(words).toContain('ailes');
  });
  it('searches by hint — pos1=s, pos3=a, pos5=e', () => {
    const words = inFile(
      'fr',
      5,
      [],
      [h(1, 's'), h(3, 'a'), h(5, 'e')],
      false,
    );
    expect(words).toHaveLength(8);
    expect(words).toContain('slave');
  });
  it('searches by content and hint combined', () => {
    const words = inFile(
      'fr',
      5,
      ['e', 'l', 'i', 's', 'a'],
      [h(1, 'l'), h(5, 's')],
      false,
    );
    expect(words).toHaveLength(11);
  });
});

describe('planLengths', () => {
  it('uses len(cars) as the max length', () => {
    expect(planLengths('guillaume', []).maxLen).toBe(9);
  });
  it('min length is 1 with no hints', () => {
    expect(planLengths('guillaume', []).minLen).toBe(1);
  });
  it('a non-inverted hint raises the min length', () => {
    expect(planLengths('guillaume', [h(4, 'a')]).minLen).toBe(4);
  });
  it('an inverted hint does not constrain the min length', () => {
    expect(planLengths('guillaume', [h(4, 'a', true)]).minLen).toBe(1);
  });
});

describe('inManyFiles', () => {
  it('finds 498 words for "guillaume" across all lengths', () => {
    expect(inManyFiles('fr', 'guillaume', [])).toHaveLength(498);
  });
  it('orders results longest-first', () => {
    const words = inManyFiles('fr', 'guillaume', []);
    for (let i = 1; i < words.length; i++) {
      expect([...words[i]].length).toBeLessThanOrEqual([...words[i - 1]].length);
    }
  });
  it('returns an empty list when hints force a length above len(cars)', () => {
    expect(inManyFiles('fr', 'abc', [h(9, 'a')])).toEqual([]);
  });
});
