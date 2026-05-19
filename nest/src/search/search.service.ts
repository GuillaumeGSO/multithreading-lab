import { Injectable } from '@nestjs/common';
import { planLengths } from './search';
import { WorkerPool } from './worker-pool';
import { SearchFileDto, SearchManyDto, SearchResponse } from './dto/search.dto';

// defaultLang mirrors the "fr" default the other implementations use.
function defaultLang(lang?: string): string {
  return lang || 'fr';
}

@Injectable()
export class SearchService {
  constructor(private readonly pool: WorkerPool) {}

  // searchFile dispatches a single fixed-length scan to the worker pool. An
  // invalid request (nb_car 0, or no letters and no hints) makes the worker's
  // inFile throw; the rejection propagates to the global exception filter.
  async searchFile(dto: SearchFileDto): Promise<SearchResponse> {
    const words = await this.pool.run({
      lang: defaultLang(dto.lang),
      length: dto.nb_car ?? 0,
      letters: dto.lst_car ?? [],
      hints: dto.lst_hint ?? [],
      strict: dto.strict ?? false,
    });
    return { words, count: words.length };
  }

  // searchMany fans one scan out per word length across the pool, then
  // concatenates the results longest-first.
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
    const partials = await Promise.all(
      lengths.map((length) =>
        this.pool.run({ lang, length, letters, hints, strict: false }),
      ),
    );
    const words = partials.flat();
    return { words, count: words.length };
  }
}
