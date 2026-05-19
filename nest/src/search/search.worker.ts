// Worker entry point. Each worker thread runs an instance of this script; one
// inbound message is one single-length `inFile` scan. Because it imports
// search.ts, every worker keeps its own word-list cache, warmed over its
// lifetime — the deliberate contrast with Go's single shared sync.Map.
import { isMainThread, parentPort } from 'worker_threads';
import { inFile, Hint } from './search';

// WorkerTask is the unit of fan-out: one length scan dispatched to a worker.
export interface WorkerTask {
  taskId: number;
  lang: string;
  length: number;
  letters: string[];
  hints: Hint[];
  strict: boolean;
}

// WorkerResult carries either the matched words or the error message back to
// the pool, tagged with the originating taskId.
export type WorkerResult =
  | { taskId: number; words: string[] }
  | { taskId: number; error: string };

if (!isMainThread && parentPort) {
  const port = parentPort;
  port.on('message', (task: WorkerTask) => {
    try {
      const words = inFile(
        task.lang,
        task.length,
        task.letters,
        task.hints,
        task.strict,
      );
      port.postMessage({ taskId: task.taskId, words } as WorkerResult);
    } catch (err) {
      port.postMessage({
        taskId: task.taskId,
        error: (err as Error).message,
      } as WorkerResult);
    }
  });
}
