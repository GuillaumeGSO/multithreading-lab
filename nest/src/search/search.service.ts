import { Injectable } from '@nestjs/common';
import { Hint, planLengths } from './search';
import { WorkerPool } from './worker-pool';
import { SearchFileDto, SearchManyDto, SearchResponse } from './dto/search.dto';

// defaultLang mirrors the "fr" default the other implementations use.
function defaultLang(lang?: string): string {
  return lang || 'fr';
}

@Injectable()
export class SearchService {
  // chunkCount is the intra-file split degree (axis B). SEARCH_MODE=baseline
  // pins it to 1, restoring the original one-task-per-length fan-out;
  // SEARCH_MODE=parallel (default) uses SPLIT_DEGREE chunks per file, so
  // /search/file splits and /search/many nests (per-length × per-chunk tasks,
  // which queue on the fixed pool rather than spawning new threads).
  private readonly chunkCount: number;

  constructor(private readonly pool: WorkerPool) {
    const parallel =
      (process.env.SEARCH_MODE || 'parallel').toLowerCase() !== 'baseline';
    const degree = Math.max(1, parseInt(process.env.SPLIT_DEGREE || '', 10) || 2);
    this.chunkCount = parallel ? degree : 1;
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
  // pool. An invalid request (nb_car 0, or no letters and no hints) makes the
  // worker's scan throw; the rejection propagates to the exception filter.
  async searchFile(dto: SearchFileDto): Promise<SearchResponse> {
    const words = await this.runChunks(
      defaultLang(dto.lang),
      dto.nb_car ?? 0,
      dto.lst_car ?? [],
      dto.lst_hint ?? [],
      dto.strict ?? false,
    );
    return { words, count: words.length };
  }

  // searchMany fans out per word length across the pool (axis A), each length
  // further split into chunkCount chunks (axis B), then concatenates the
  // results longest-first.
  async searchMany(dto: SearchManyDto): Promise<SearchResponse> {
    const lang = defaultLang(dto.lang);
    const hints = dto.lst_hint ?? [];
    const { minLen, maxLen, letters } = planLengths(dto.cars ?? '', hints);
    if (maxLen < minLen) {
      return { words: [], count: 0 };
    }

    const lengths: number[] = [];
    for (let length = maxLen; length >= minLen; length--) {
      lengths.push(length);
    }
    const perLength = await Promise.all(
      lengths.map((length) =>
        this.runChunks(lang, length, letters, hints, false),
      ),
    );
    const words = perLength.flat();
    return { words, count: words.length };
  }
}
