import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { ensureLogDirs, ROOT } from './logger.mjs';

const STARTUP_DIR = join(ROOT, 'logs', 'startup');

export class StartupTimeline {
  #sessionId;
  #startedAt;
  #steps = [];

  constructor(sessionId = new Date().toISOString().replace(/[:.]/g, '-')) {
    ensureLogDirs();
    mkdirSync(STARTUP_DIR, { recursive: true });
    this.#sessionId = sessionId;
    this.#startedAt = Date.now();
    this.mark('session_start');
  }

  mark(step, meta = {}) {
    const at = Date.now();
    const entry = {
      step,
      at: new Date(at).toISOString(),
      elapsedMs: at - this.#startedAt,
      sincePreviousMs:
        this.#steps.length === 0 ? 0 : at - (this.#steps[this.#steps.length - 1]._at ?? this.#startedAt),
      ...meta,
    };
    entry._at = at;
    this.#steps.push(entry);
    this.#flush();
    return entry;
  }

  #flush() {
    const report = {
      sessionId: this.#sessionId,
      startedAt: new Date(this.#startedAt).toISOString(),
      totalMs: Date.now() - this.#startedAt,
      status: this.#steps.some((s) => s.step === 'ready') ? 'ready' : 'starting',
      steps: this.#steps.map(({ _at, ...rest }) => rest),
    };

    writeFileSync(join(STARTUP_DIR, 'latest.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8');
    writeFileSync(
      join(STARTUP_DIR, `${this.#sessionId}.json`),
      `${JSON.stringify(report, null, 2)}\n`,
      'utf8',
    );
  }

  finish(status = 'ready', meta = {}) {
    this.mark(status === 'ready' ? 'ready' : 'failed', meta);
    this.#flush();
    return join(STARTUP_DIR, 'latest.json');
  }
}

export function readLatestStartupReport() {
  const path = join(STARTUP_DIR, 'latest.json');
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, 'utf8'));
}
