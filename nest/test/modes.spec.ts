// SEARCH_MODE through the real SearchService and worker pool (compiled dist/,
// part of `npm run test:integration`): every mode returns exactly the
// baseline's words.
import * as path from 'path';

import { WorkerPool } from '../dist/search/worker-pool';
import { SearchService } from '../dist/search/search.service';

describe('SEARCH_MODE', () => {
  let pool: WorkerPool;
  const services: Record<string, SearchService> = {};

  beforeAll(() => {
    process.env.ASSETS_ROOT = path.resolve(__dirname, '../../assets');
    pool = new WorkerPool();
    for (const mode of ['baseline', 'parallel']) {
      process.env.SEARCH_MODE = mode;
      services[mode] = new SearchService(pool);
    }
    delete process.env.SEARCH_MODE;
  });

  afterAll(async () => {
    await pool.destroy();
  });

  const fileCases = [
    { wordLength: 5, letters: ['e', 'l', 'i', 's', 'a'], strict: true },
    { wordLength: 5, letters: ['e', 'l', 'i', 's', 'a'], hints: [{ position: 1, letter: 's' }] },
    { wordLength: 7, hints: [{ position: 1, letter: 'a' }, { position: 7, letter: 'e', excluded: true }] },
  ];
  const manyCases = [
    { letters: 'guillaume' },
    { letters: 'artes', hints: [{ position: 1, letter: 'a' }] },
  ];

  it.each(fileCases)('file %j: parallel equals baseline', async (req) => {
    const expected = await services.baseline.searchFile(req);
    expect(expected.count).toBeGreaterThan(0);
    expect(await services.parallel.searchFile(req)).toEqual(expected);
  });

  it.each(manyCases)('many %j: parallel equals baseline', async (req) => {
    const expected = await services.baseline.searchMany(req);
    expect(expected.count).toBeGreaterThan(0);
    expect(await services.parallel.searchMany(req)).toEqual(expected);
  });

  it('rejects an unknown mode at construction', () => {
    process.env.SEARCH_MODE = 'indexed';
    try {
      expect(() => new SearchService(pool)).toThrow('unknown SEARCH_MODE');
    } finally {
      delete process.env.SEARCH_MODE;
    }
  });
});
