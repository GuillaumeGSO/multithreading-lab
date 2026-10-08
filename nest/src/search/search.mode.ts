// SEARCH_MODE: the implementation the live API serves. Every language in this
// lab gives the modes the same meaning:
//   baseline  single-threaded scan: one worker task in flight per request
//             (/many scans the lengths one after another)
//   parallel  scan split into SPLIT_DEGREE chunks per file; /many also fans
//             out per length — all tasks queue on the fixed worker pool
//             (the default)
// This implementation has no positional index, so "indexed" is not available.
export type SearchMode = 'baseline' | 'parallel';

export const SEARCH_MODES: readonly SearchMode[] = ['baseline', 'parallel'];
export const DEFAULT_SEARCH_MODE: SearchMode = 'parallel';

// parseSearchMode returns the mode named by `value` (empty means the default).
// An unknown value throws, so a typo fails at startup instead of silently
// serving a different mode.
export function parseSearchMode(value: string | undefined): SearchMode {
  const name = (value ?? '').trim().toLowerCase();
  if (name === '') return DEFAULT_SEARCH_MODE;
  if ((SEARCH_MODES as readonly string[]).includes(name)) return name as SearchMode;
  throw new Error(
    `unknown SEARCH_MODE '${name}'; expected one of ${SEARCH_MODES.join(', ')}`,
  );
}
