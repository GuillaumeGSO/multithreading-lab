// Worker-pool integration tests. These run against the COMPILED output in
// dist/ — the worker file must be plain JavaScript for worker_threads to load
// it, so `npm run test:integration` builds first. They verify pool dispatch,
// concurrent fan-out, parity with the pure algorithm, and clean teardown.
import * as path from 'path';

import { WorkerPool } from '../dist/search/worker-pool';
import { inFile, inManyFiles, planLengths } from '../dist/search/search';

describe('WorkerPool', () => {
  let pool: WorkerPool;

  beforeAll(() => {
    // Set before spawning workers so they inherit ASSETS_ROOT via env.
    process.env.ASSETS_ROOT = path.resolve(__dirname, '../../assets');
    pool = new WorkerPool();
  });

  afterAll(async () => {
    await pool.destroy();
  });

  it('runs a single inFile task with parity to the pure call', async () => {
    const words = await pool.run({
      lang: 'fr',
      length: 5,
      letters: ['e', 'l', 'i', 's', 'a'],
      hints: [],
      strict: true,
    });
    expect(words).toEqual(inFile('fr', 5, ['e', 'l', 'i', 's', 'a'], [], true));
    expect(words).toHaveLength(8);
  });

  it('runs many tasks concurrently', async () => {
    const lengths = [3, 4, 5, 6, 7];
    const results = await Promise.all(
      lengths.map((length) =>
        pool.run({
          lang: 'fr',
          length,
          letters: ['e', 'l', 'i', 's', 'a', 'b', 'c', 'd'],
          hints: [],
          strict: false,
        }),
      ),
    );
    expect(results).toHaveLength(5);
    results.forEach((r) => expect(Array.isArray(r)).toBe(true));
  });

  it('fans /search/many out across lengths — 494 for "guillaume"', async () => {
    const { minLen, maxLen, letters } = planLengths('guillaume', []);
    const lengths: number[] = [];
    for (let length = maxLen; length >= minLen; length--) {
      lengths.push(length);
    }
    const partials = await Promise.all(
      lengths.map((length) =>
        pool.run({ lang: 'fr', length, letters, hints: [], strict: false }),
      ),
    );
    const words = partials.flat();
    expect(words).toHaveLength(inManyFiles('fr', 'guillaume', []).length);
    expect(words).toHaveLength(494);
  });

  it('rejects when letters and hints are both empty', async () => {
    await expect(
      pool.run({ lang: 'fr', length: 0, letters: [], hints: [], strict: false }),
    ).rejects.toThrow('letters and hints cannot both be empty');
  });

  // Intra-file split: chunk-tasks reassembled in index order must equal the
  // whole-file scan, for every split degree — order independent of timing.
  it.each([1, 2, 3, 5])(
    'split into %i chunks matches the whole-file scan',
    async (chunkCount) => {
      const letters = ['e', 'l', 'i', 's', 'a'];
      const want = inFile('fr', 5, letters, [], true);
      const chunks = await Promise.all(
        Array.from({ length: chunkCount }, (_, chunkIndex) =>
          pool.run({
            lang: 'fr',
            length: 5,
            letters,
            hints: [],
            strict: true,
            chunkIndex,
            chunkCount,
          }),
        ),
      );
      expect(chunks.flat()).toEqual(want);
    },
  );
});
