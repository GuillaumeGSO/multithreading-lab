// WorkerPool owns a fixed set of persistent worker threads and load-balances
// search tasks across them. This is the concurrency model under test: the Node
// analog of Go goroutines / Java ExecutorService.
//
// `/search/file` submits one task; `/search/many` submits one task per word
// length and awaits them all. Idle workers take queued tasks as they free up.
import { Injectable, OnApplicationShutdown } from '@nestjs/common';
import { cpus } from 'os';
import { join } from 'path';
import { Worker } from 'worker_threads';
import type { WorkerResult, WorkerTask } from './search.worker';

// SearchTask is a task without its pool-assigned id.
export type SearchTask = Omit<WorkerTask, 'taskId'>;

interface Pending {
  resolve: (words: string[]) => void;
  reject: (err: Error) => void;
}

@Injectable()
export class WorkerPool implements OnApplicationShutdown {
  private readonly size: number;
  private readonly workerPath: string;
  private workers: Worker[] = [];
  private idle: Worker[] = [];
  private readonly queue: { task: WorkerTask; pending: Pending }[] = [];
  private readonly pendingByTask = new Map<number, Pending>();
  private readonly taskByWorker = new Map<Worker, number>();
  private nextTaskId = 0;
  private destroyed = false;

  constructor() {
    this.size = Math.max(
      1,
      parseInt(process.env.WORKER_POOL_SIZE || '', 10) || cpus().length,
    );
    // Compiled output: dist/search/worker-pool.js sits beside search.worker.js.
    this.workerPath = join(__dirname, 'search.worker.js');
    for (let i = 0; i < this.size; i++) {
      this.spawn();
    }
  }

  // run submits a task, dispatching it to an idle worker or queueing it.
  run(input: SearchTask): Promise<string[]> {
    return new Promise<string[]>((resolve, reject) => {
      const task: WorkerTask = { ...input, taskId: this.nextTaskId++ };
      const pending: Pending = { resolve, reject };
      const worker = this.idle.pop();
      if (worker) {
        this.assign(worker, task, pending);
      } else {
        this.queue.push({ task, pending });
      }
    });
  }

  // destroy terminates every worker. Without it the worker_threads keep the
  // process alive, hanging `docker stop` and Jest.
  async destroy(): Promise<void> {
    this.destroyed = true;
    await Promise.all(this.workers.map((w) => w.terminate()));
    this.workers = [];
    this.idle = [];
  }

  // onApplicationShutdown ties the pool into the NestJS lifecycle; it fires on
  // SIGTERM once main.ts has called enableShutdownHooks().
  async onApplicationShutdown(): Promise<void> {
    await this.destroy();
  }

  private spawn(): void {
    // Pass env explicitly so the worker sees ASSETS_ROOT even when it was set
    // at runtime (e.g. by a Jest spec) rather than at process launch.
    const worker = new Worker(this.workerPath, { env: process.env });
    worker.on('message', (msg: WorkerResult) => {
      const pending = this.pendingByTask.get(msg.taskId);
      this.pendingByTask.delete(msg.taskId);
      this.taskByWorker.delete(worker);
      if (pending) {
        if ('error' in msg) {
          pending.reject(new Error(msg.error));
        } else {
          pending.resolve(msg.words);
        }
      }
      this.release(worker);
    });
    worker.on('error', (err) => {
      // Fail the in-flight task, drop the dead worker, and respawn.
      const taskId = this.taskByWorker.get(worker);
      if (taskId !== undefined) {
        this.pendingByTask.get(taskId)?.reject(err);
        this.pendingByTask.delete(taskId);
        this.taskByWorker.delete(worker);
      }
      this.workers = this.workers.filter((w) => w !== worker);
      this.idle = this.idle.filter((w) => w !== worker);
      if (!this.destroyed) {
        this.spawn();
      }
    });
    this.workers.push(worker);
    this.idle.push(worker);
  }

  private assign(worker: Worker, task: WorkerTask, pending: Pending): void {
    this.pendingByTask.set(task.taskId, pending);
    this.taskByWorker.set(worker, task.taskId);
    worker.postMessage(task);
  }

  // release hands the worker the next queued task, or returns it to the idle
  // set when the queue is empty.
  private release(worker: Worker): void {
    const next = this.queue.shift();
    if (next) {
      this.assign(worker, next.task, next.pending);
    } else {
      this.idle.push(worker);
    }
  }
}
