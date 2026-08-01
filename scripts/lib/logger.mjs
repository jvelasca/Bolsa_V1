import { appendFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = new URL('../..', import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1');
const LOGS_DIR = join(ROOT, 'logs');

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
