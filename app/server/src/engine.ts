// A small pool of resident `build/analyze --stdin` processes. Each process loads the networks once (~1 s with packed
// networks) and then answers one JSON line per request line. A worker serves one request at a time; requests queue in
// the pool. A worker that crashes, hangs past its timeout or fails to start is killed and restarted with backoff.
import { type ChildProcess, spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { log } from './log.ts';

export class EngineBusy extends Error {}
export class EngineUnavailable extends Error {}
export class EngineTimeout extends Error {}

export interface EngineSpec {
  root: string;
  bin: string;
  args: string[];
  startupTimeoutMs: number;
}

/** The engine command, run through bash for a large stack (as scripts/serve.py) with few malloc arenas. */
export function engineCommand(spec: { bin: string; args: string[] }): { cmd: string; args: string[] } {
  return {
    cmd: 'bash',
    args: ['-c', 'ulimit -s unlimited 2>/dev/null || true; exec "$0" "$@"', spec.bin, ...spec.args],
  };
}

const WARMUP = '| 0 0 0 2 0 0 0 0 0 0 0 0 2 0 0 0';

type State = 'starting' | 'ready' | 'busy' | 'dead' | 'stopped';

interface Job {
  line: string;
  timeoutMs: number;
  resolve: (out: string) => void;
  reject: (e: Error) => void;
  enqueued: number;
  waitTimer?: NodeJS.Timeout;
}

class Worker {
  state: State = 'dead';
  restarts = 0;
  served = 0;
  failures = 0;
  lastMs = 0;
  startedAt = 0;
  loadMs = 0;
  private proc?: ChildProcess;
  private waiting?: { resolve: (s: string) => void; reject: (e: Error) => void; timer: NodeJS.Timeout };
  private stderrTail: string[] = [];
  private backoffMs = 500;
  private restartTimer?: NodeJS.Timeout;

  readonly id: number;
  private spec: EngineSpec;
  private onReady: () => void;

  constructor(id: number, spec: EngineSpec, onReady: () => void) {
    this.id = id;
    this.spec = spec;
    this.onReady = onReady;
  }

  start(): void {
    if (this.state === 'stopped') return;
    this.state = 'starting';
    const { cmd, args } = engineCommand(this.spec);
    const t0 = Date.now();
    const proc = spawn(cmd, args, {
      cwd: this.spec.root,
      env: { ...process.env, MALLOC_ARENA_MAX: '2' },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    this.proc = proc;
    this.stderrTail = [];
    createInterface({ input: proc.stdout! }).on('line', (line) => this.onLine(line));
    createInterface({ input: proc.stderr! }).on('line', (line) => {
      this.stderrTail.push(line);
      if (this.stderrTail.length > 20) this.stderrTail.shift();
    });
    proc.stdin!.on('error', () => {}); // EPIPE when the process died; handled by 'exit'
    proc.on('error', (e) => log('engine.spawn_error', { worker: this.id, error: String(e) }));
    proc.on('exit', (code, signal) => this.onExit(proc, code, signal));
    this.ask(WARMUP, this.spec.startupTimeoutMs).then(
      (out) => {
        if (!out.includes('"moves"')) throw new Error(`unexpected warmup answer: ${out.slice(0, 200)}`);
        this.loadMs = Date.now() - t0;
        this.startedAt = Date.now();
        this.state = 'ready';
        log('engine.ready', { worker: this.id, load_ms: this.loadMs, pid: proc.pid });
        this.onReady();
      },
      (e) => {
        log('engine.start_failed', { worker: this.id, error: String(e), stderr: this.stderrTail.slice(-5) });
        this.kill();
      },
    );
  }

  /** Runs one request on this (ready) worker. */
  run(line: string, timeoutMs: number): Promise<string> {
    this.state = 'busy';
    const t0 = Date.now();
    return this.ask(line, timeoutMs).then(
      (out) => {
        this.lastMs = Date.now() - t0;
        this.served++;
        if (this.state === 'busy') this.state = 'ready';
        if (this.startedAt && Date.now() - this.startedAt > 60000) this.backoffMs = 500;
        return out;
      },
      (e) => {
        this.failures++;
        throw e;
      },
    );
  }

  private ask(line: string, timeoutMs: number): Promise<string> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.waiting = undefined;
        log('engine.timeout', { worker: this.id, ms: timeoutMs, line: line.slice(0, 120) });
        reject(new EngineTimeout(`the engine did not answer within ${timeoutMs} ms`));
        this.kill(); // a hung search: restart the process
      }, timeoutMs);
      this.waiting = { resolve, reject, timer };
      this.proc!.stdin!.write(line.replace(/[\r\n]/g, ' ') + '\n');
    });
  }

  private onLine(line: string): void {
    const w = this.waiting;
    if (!w) return; // an answer after a timeout: the process is being killed anyway
    this.waiting = undefined;
    clearTimeout(w.timer);
    w.resolve(line);
  }

  private onExit(proc: ChildProcess, code: number | null, signal: string | null): void {
    if (proc !== this.proc) return;
    const w = this.waiting;
    this.waiting = undefined;
    if (w) {
      clearTimeout(w.timer);
      w.reject(new EngineUnavailable('the engine process stopped'));
    }
    if (this.state === 'stopped') return;
    log('engine.exit', { worker: this.id, code, signal, stderr: this.stderrTail.slice(-5) });
    this.state = 'dead';
    this.restarts++;
    const delay = this.backoffMs;
    this.backoffMs = Math.min(30000, this.backoffMs * 2);
    this.restartTimer = setTimeout(() => this.start(), delay);
  }

  kill(): void {
    if (this.proc && this.proc.exitCode === null) this.proc.kill('SIGKILL');
  }

  stop(): void {
    this.state = 'stopped';
    clearTimeout(this.restartTimer);
    this.kill();
  }

  status() {
    return {
      id: this.id,
      state: this.state,
      pid: this.proc?.pid ?? null,
      restarts: this.restarts,
      served: this.served,
      failures: this.failures,
      last_ms: this.lastMs,
      load_ms: this.loadMs,
      uptime_s: this.startedAt && this.state !== 'dead' ? Math.round((Date.now() - this.startedAt) / 1000) : 0,
    };
  }
}

export class EnginePool {
  private workers: Worker[];
  private queue: Job[] = [];
  private maxQueue: number;
  private queueWaitMs: number;

  constructor(n: number, spec: EngineSpec, maxQueue: number, queueWaitMs: number) {
    this.maxQueue = maxQueue;
    this.queueWaitMs = queueWaitMs;
    this.workers = Array.from({ length: n }, (_, i) => new Worker(i, spec, () => this.pump()));
  }

  start(): void {
    for (const w of this.workers) w.start();
  }

  get ready(): boolean {
    return this.workers.some((w) => w.state === 'ready' || w.state === 'busy');
  }

  /** Queues one engine request line; resolves with the engine's JSON line. */
  run(line: string, timeoutMs: number): Promise<string> {
    if (this.queue.length >= this.maxQueue) return Promise.reject(new EngineBusy('the analysis queue is full'));
    return new Promise((resolve, reject) => {
      const job: Job = { line, timeoutMs, resolve, reject, enqueued: Date.now() };
      job.waitTimer = setTimeout(() => {
        const i = this.queue.indexOf(job);
        if (i >= 0) this.queue.splice(i, 1);
        reject(new EngineUnavailable('no engine was free in time'));
      }, this.queueWaitMs);
      this.queue.push(job);
      this.pump();
    });
  }

  private pump(): void {
    for (const w of this.workers) {
      if (!this.queue.length) return;
      if (w.state !== 'ready') continue;
      const job = this.queue.shift()!;
      clearTimeout(job.waitTimer);
      w.run(job.line, job.timeoutMs)
        .then(job.resolve, job.reject)
        .finally(() => this.pump());
    }
  }

  status() {
    return { workers: this.workers.map((w) => w.status()), queue: this.queue.length };
  }

  stop(): void {
    for (const w of this.workers) w.stop();
    for (const j of this.queue.splice(0)) {
      clearTimeout(j.waitTimer);
      j.reject(new EngineUnavailable('the server is shutting down'));
    }
  }
}
