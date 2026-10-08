import { Injectable } from '@nestjs/common';
import { Hint, planLengths } from './search';
import { WorkerPool } from './worker-pool';
import { SearchMode, parseSearchMode } from './search.mode';
import {
  HintRequest,
  SearchFileRequest,
  SearchManyRequest,
  SearchResponse,
} from './search.types';

// defaultLang applies the spec's default language ("fr") when lang is absent.
function defaultLang(lang?: string): string {
  return lang || 'fr';
}

// toHints applies the spec's defaults to request hints (TypeScript types
// carry no default values).
function toHints(hints: HintRequest[] = []): Hint[] {
  return hints.map((h) => ({
    position: h.position,
    letter: h.letter ?? null,
    excluded: h.excluded ?? false,
  }));
}

@Injectable()
export class SearchService {
  // mode comes from SEARCH_MODE (see search.mode.ts); an unknown value throws
  // here, while Nest instantiates providers at startup. chunkCount is the
  // intra-file split degree (axis B): SPLIT_DEGREE chunks in parallel mode, 1 in
  // baseline.
  readonly mode: SearchMode;
  private readonly chunkCount: number;

  constructor(private readonly pool: WorkerPool) {
    this.mode = parseSearchMode(process.env.SEARCH_MODE);
    const degree = Math.max(1, parseInt(process.env.SPLIT_DEGREE || '', 10) || 2);
    this.chunkCount = this.mode === 'parallel' ? degree : 1;
  }

  // runChunks dispatches `chunkCount` chunk-tasks for one length and merges
  // their results in index order (== a single whole-file scan).
  private async runChunks(
    lang: string,
    length: number,
    letters: string[],
    hints: Hint[],
    strict: boolean,
  ): Promise<string[]> {
    const chunks = await Promise.all(
      Array.from({ length: this.chunkCount }, (_, chunkIndex) =>
        this.pool.run({
          lang,
          length,
          letters,
          hints,
          strict,
          chunkIndex,
          chunkCount: this.chunkCount,
        }),
      ),
    );
    return chunks.flat();
  }

  // searchFile scans one fixed length, split into chunkCount chunks across the
  // pool. An invalid request (wordLength 0, or no letters and no hints) makes
  // the worker's scan throw; the rejection propagates to the exception filter.
  async searchFile(req: SearchFileRequest): Promise<SearchResponse> {
    const words = await this.runChunks(
      defaultLang(req.lang),
      req.wordLength ?? 0,
      req.letters ?? [],
      toHints(req.hints),
      req.strict ?? false,
    );
    return { words, count: words.length };
  }

  // searchMany scans every length longest-first. In parallel mode the lengths
  // fan out across the pool (axis A), each further split into chunkCount chunks
  // (axis B); in baseline mode they run one after another, one task at a time.
  async searchMany(req: SearchManyRequest): Promise<SearchResponse> {
    const lang = defaultLang(req.lang);
    const hints = toHints(req.hints);
    const { minLen, maxLen, pool } = planLengths(req.letters ?? '', hints);
    if (maxLen < minLen) {
      return { words: [], count: 0 };
    }

    const lengths: number[] = [];
    for (let length = maxLen; length >= minLen; length--) {
      lengths.push(length);
    }
    let perLength: string[][];
    if (this.mode === 'parallel') {
      perLength = await Promise.all(
        lengths.map((length) =>
          this.runChunks(lang, length, pool, hints, false),
        ),
      );
    } else {
      perLength = [];
      for (const length of lengths) {
        perLength.push(await this.runChunks(lang, length, pool, hints, false));
      }
    }
    const words = perLength.flat();
    return { words, count: words.length };
  }
}
