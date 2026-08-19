import { appendFileSync, mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = new URL('../..', import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1');
const LOGS_DIR = join(ROOT, 'logs');

/**
 * Rotación por retención de los logs con sello por sesión (p. ej. `logs/dev/dev-<ISO>.log`).
 * Cada `pnpm dev` crea un fichero nuevo y sin esta limpieza los lanzamientos antiguos se
 * acumulan indefinidamente (F-SEG-2: ~155,8 MB). Se conservan los `keep` más recientes y se
 * eliminan los más viejos; nunca toca `.gitkeep` ni ficheros fuera del patrón.
 */
export function pruneStampedLogs(subdir, prefix, keep) {
  const dir = join(LOGS_DIR, subdir);
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true })
      .filter((e) => e.isFile() && e.name.startsWith(prefix))
      .map((e) => ({ name: e.name, full: join(dir, e.name), mtimeMs: statSync(join(dir, e.name)).mtimeMs }));
  } catch {
    return 0;
  }
  if (entries.length <= keep) return 0;
  const toRemove = entries.sort((a, b) => b.mtimeMs - a.mtimeMs).slice(keep);
  for (const entry of toRemove) {
    try {
      rmSync(entry.full, { force: true });
    } catch {
      /* best-effort: un fichero en uso no debe tumbar el arranque */
    }
  }
  return toRemove.length;
}

export function ensureLogDirs() {
  for (const sub of ['api', 'web', 'tests', 'agent', 'dev']) {
    mkdirSync(join(LOGS_DIR, sub), { recursive: true });
  }
}

function timestamp() {
  return new Date().toISOString();
}

function fileStamp() {
  return timestamp().replace(/[:.]/g, '-');
}

export function writeAgentLog(name, payload) {
  ensureLogDirs();
  const entry = { at: timestamp(), ...payload };
  const latestPath = join(LOGS_DIR, 'agent', `${name}.json`);
  const stampedPath = join(LOGS_DIR, 'agent', `${name}-${fileStamp()}.json`);
  const body = `${JSON.stringify(entry, null, 2)}\n`;
  writeFileSync(latestPath, body, 'utf8');
  writeFileSync(stampedPath, body, 'utf8');
  return latestPath;
}

export function appendLog(subdir, filename, line) {
  ensureLogDirs();
  const path = join(LOGS_DIR, subdir, filename);
  appendFileSync(path, `${line}\n`, 'utf8');
  return path;
}

export function logInfo(scope, message, meta = {}) {
  const line = JSON.stringify({ at: timestamp(), level: 'info', scope, message, ...meta });
  console.log(`[${scope}] ${message}`);
  return appendLog('agent', 'events.log', line);
}

export function logError(scope, message, meta = {}) {
  const line = JSON.stringify({ at: timestamp(), level: 'error', scope, message, ...meta });
  console.error(`[${scope}] ${message}`);
  return appendLog('agent', 'events.log', line);
}

export function logWarn(scope, message, meta = {}) {
  const line = JSON.stringify({ at: timestamp(), level: 'warn', scope, message, ...meta });
  console.warn(`[${scope}] ${message}`);
  return appendLog('agent', 'events.log', line);
}

export { LOGS_DIR, ROOT };
