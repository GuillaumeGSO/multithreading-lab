// In-process benchmark for the Nest/Node implementation. Runs the algorithm
// directly (no HTTP), timing each canonical case per concurrency mode with
// warmup + median-of-N, and prints a single JSON report to stdout (logs go to
// stderr). Run as: node dist/bench.js
//
// Modes:
//   baseline -> synchronous scan on the main thread (no workers)
//   split    -> file split into SPLIT_DEGREE chunks across the worker pool
//   fanout   -> one task per word length across the pool (one whole-file scan)
//   nested   -> per-length AND per-chunk tasks queued on the fixed pool
import { readFileSync } from 'fs';
import { performance } from 'perf_hooks';
import { Hint, inFile, inManyFiles, planLengths } from './search/search';
import { WorkerPool } from './search/worker-pool';
import {
  HintRequest,
  SearchFileRequest,
  SearchManyRequest,
} from './search/search.types';

// A cases.json entry: a name and kind plus the request body of the matching
// endpoint (`letters` is an array for "file" cases and a string for "many").
type BenchCase =
  | ({ name: string; kind: 'file' } & SearchFileRequest)
  | ({ name: string; kind: 'many' } & SearchManyRequest);

const WARMUP = parseInt(process.env.BENCH_WARMUP || '', 10) || 20;
const ITERS = parseInt(process.env.BENCH_ITERS || '', 10) || 100;
const DEGREE = Math.max(1, parseInt(process.env.SPLIT_DEGREE || '', 10) || 2);
const CASES_PATH = process.env.CASES_PATH || '/app/cases.json';

function toHints(raw: HintRequest[] = []): Hint[] {
  return raw.map((h) => ({
    position: h.position,
    letter: h.letter ?? null,
    excluded: h.excluded ?? false,
  }));
}

async function timeMode(
  fn: () => Promise<string[]>,
): Promise<{ count: number; median_ms: number; min_ms: number }> {
  let count = 0;
  for (let i = 0; i < WARMUP; i++) count = (await fn()).length;
  const samples: number[] = [];
  for (let i = 0; i < ITERS; i++) {
    const start = performance.now();
    const r = await fn();
    samples.push(performance.now() - start);
    count = r.length;
  }
  samples.sort((a, b) => a - b);
  const mid = Math.floor(samples.length / 2);
  const median =
    samples.length % 2 === 0 ? (samples[mid - 1] + samples[mid]) / 2 : samples[mid];
  return { count, median_ms: median, min_ms: samples[0] };
}

async function main() {
  const pool = new WorkerPool();

  // Pool-based scan of one length, split into `chunkCount` chunks (merged in order).
  const runChunks = async (
    lang: string,
    length: number,
    letters: string[],
    hints: Hint[],
    strict: boolean,
    chunkCount: number,
  ): Promise<string[]> => {
    const chunks = await Promise.all(
      Array.from({ length: chunkCount }, (_, chunkIndex) =>
        pool.run({ lang, length, letters, hints, strict, chunkIndex, chunkCount }),
      ),
    );
    return chunks.flat();
  };

  const manyPool = async (
    lang: string,
    letters: string,
    hints: Hint[],
    chunkCount: number,
  ): Promise<string[]> => {
    const { minLen, maxLen, pool: letterPool } = planLengths(letters, hints);
    if (maxLen < minLen) return [];
    const lengths: number[] = [];
    for (let l = maxLen; l >= minLen; l--) lengths.push(l);
    const perLength = await Promise.all(
      lengths.map((l) => runChunks(lang, l, letterPool, hints, false, chunkCount)),
    );
    return perLength.flat();
  };

  // Concurrent-load: THROUGHPUT_OPS whole-file scans dispatched to the worker
  // pool with CONCURRENCY in flight. Each op is one pool task (no intra-file
  // split) — the pool itself (default 2 workers) is the bottleneck under load.
  const runThroughput = async () => {
    const concurrency = parseInt(process.env.CONCURRENCY || '', 10) || 16;
    const ops = parseInt(process.env.THROUGHPUT_OPS || '', 10) || 200;
    const lang = 'fr';
    const wordLength = 11;
    const letters = 'abcdefghijklmnopqrstuvwxyz'.split('');
    const hints: Hint[] = [{ position: 1, letter: 'x', excluded: false }];
    await pool.run({ lang, length: wordLength, letters, hints, strict: false }); // warmup

    const latencies: number[] = new Array(ops);
    let count = 0;
    let next = 0;
    const start = performance.now();
    const worker = async () => {
      for (;;) {
        const i = next++;
        if (i >= ops) return;
        const t = performance.now();
        const r = await pool.run({ lang, length: wordLength, letters, hints, strict: false });
        latencies[i] = performance.now() - t;
        count = r.length;
      }
    };
    await Promise.all(Array.from({ length: concurrency }, () => worker()));
    const elapsed = performance.now() - start;
    latencies.sort((a, b) => a - b);
    return {
      workload: 'file wordLength=11 pool=26 hint=1:x (baseline scan per op)',
      concurrency,
      ops,
      elapsed_ms: elapsed,
      ops_per_sec: ops / (elapsed / 1000),
      median_latency_ms: latencies[Math.floor(ops / 2)],
      count,
    };
  };

  const cases: BenchCase[] = JSON.parse(readFileSync(CASES_PATH, 'utf-8'));
  const outCases: unknown[] = [];

  for (const c of cases) {
    const lang = c.lang || 'fr';
    const hints = toHints(c.hints);
    const modes: Record<string, () => Promise<string[]>> = {};

    if (c.kind === 'file') {
      const wordLength = c.wordLength ?? 0;
      const letters = c.letters ?? [];
      const strict = c.strict ?? false;
      modes.baseline = async () => inFile(lang, wordLength, letters, hints, strict);
      modes.split = () => runChunks(lang, wordLength, letters, hints, strict, DEGREE);
    } else {
      const letters = c.letters ?? '';
      modes.baseline = async () => inManyFiles(lang, letters, hints);
      modes.fanout = () => manyPool(lang, letters, hints, 1);
      modes.nested = () => manyPool(lang, letters, hints, DEGREE);
    }

    const modeJson: Record<string, { median_ms: number; min_ms: number }> = {};
    let count = 0;
    for (const [name, fn] of Object.entries(modes)) {
      const t = await timeMode(fn);
      count = t.count;
      modeJson[name] = { median_ms: t.median_ms, min_ms: t.min_ms };
      process.stderr.write(
        `[Nest] ${c.name} / ${name}: ${count} words, median ${t.median_ms.toFixed(4)} ms\n`,
      );
    }
    outCases.push({ name: c.name, kind: c.kind, count, modes: modeJson });
  }

  const throughput = await runThroughput();
  process.stderr.write(
    `[Nest] throughput: ${throughput.ops_per_sec.toFixed(1)} ops/s @ concurrency ${throughput.concurrency}\n`,
  );

  await pool.destroy();

  const report = {
    language: 'nest',
    label: 'Node/NestJS',
    meta: { warmup: WARMUP, iterations: ITERS, split_degree: DEGREE },
    cases: outCases,
    throughput,
  };
  process.stdout.write(JSON.stringify(report) + '\n');
}

main().catch((err) => {
  process.stderr.write(String(err && err.stack ? err.stack : err) + '\n');
  process.exit(1);
});
