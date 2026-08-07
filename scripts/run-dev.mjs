import { join } from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, readdirSync, statSync } from 'node:fs';
import os from 'node:os';
import { ensureLogDirs, logError, logInfo, ROOT, writeAgentLog } from './lib/logger.mjs';
import { ensurePortFree, freePort } from './lib/ports.mjs';
import { spawnPnpm } from './lib/pnpm.mjs';
import { resolvePython } from './lib/python.mjs';
import { waitForApi } from './lib/wait-api.mjs';
import { StartupTimeline, readLatestStartupReport } from './lib/startup-timeline.mjs';

function newestMtimeMs(dir) {
  let newest = 0;
  if (!existsSync(dir)) return newest;
  const stack = [dir];
  while (stack.length > 0) {
    const current = stack.pop();
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const full = join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
        continue;
      }
      const mtime = statSync(full).mtimeMs;
      if (mtime > newest) newest = mtime;
    }
  }
  return newest;
}

/** Skip tsc when dist is newer than src (typical warm `pnpm dev`). */
function sharedPackageNeedsBuild() {
  const pkg = join(ROOT, 'packages', 'shared');
  const distEntry = join(pkg, 'dist', 'index.js');
  if (!existsSync(distEntry)) return true;
  return newestMtimeMs(join(pkg, 'src')) > newestMtimeMs(join(pkg, 'dist'));
}

const API_PORT = Number(process.env.API_PYTHON_PORT ?? 8000);
const WEB_PORT = Number(process.env.WEB_PORT ?? 5173);
const XTB_BRIDGE_PORT = Number(process.env.XTB_BRIDGE_PORT ?? 3002);
const XTB_BRIDGE_AUTOSTART = process.env.XTB_BRIDGE_AUTOSTART !== '0';
const SCAN_QUEUE_BACKEND = (process.env.SCAN_QUEUE_BACKEND ?? 'postgres').toLowerCase();

ensureLogDirs();

const timeline = new StartupTimeline();
timeline.mark('init');

function runDbPrepare() {
  timeline.mark('db_check_start');
  logInfo('dev', 'Comprobando PostgreSQL...');
  let result = spawnSync(process.execPath, [join(ROOT, 'scripts', 'db-ensure.mjs'), '--ping'], {
    cwd: ROOT,
    stdio: 'inherit',
  });

  if (result.status !== 0) {
    logInfo('dev', 'PostgreSQL no responde — setup completo (Docker puede tardar 1-2 min)...');
    result = spawnSync(process.execPath, [join(ROOT, 'scripts', 'db-ensure.mjs')], {
      cwd: ROOT,
      stdio: 'inherit',
    });
    if (result.status !== 0) {
      logError('dev', 'No se pudo preparar la base de datos');
      timeline.finish('failed', { phase: 'db_full_setup' });
      process.exit(result.status ?? 1);
    }
    timeline.mark('db_ready', { mode: 'full_setup' });
    return;
  }

  result = spawnSync(
    process.execPath,
    [join(ROOT, 'scripts', 'db-ensure.mjs'), '--ping', '--migrate'],
    { cwd: ROOT, stdio: 'inherit' },
  );
  if (result.status !== 0) {
    logError('dev', 'Fallo aplicando migraciones');
    timeline.finish('failed', { phase: 'db_migrate' });
    process.exit(result.status ?? 1);
  }
  timeline.mark('db_ready', { mode: 'ping_migrate' });
}

runDbPrepare();

for (const [label, port] of [
  ['Web', WEB_PORT],
  ['API', API_PORT],
  ['XTB mock', XTB_BRIDGE_PORT],
]) {
  if (freePort(port)) {
    logInfo('dev', `Puerto ${port} (${label}) liberado — proceso anterior cerrado`);
  }
}

timeline.mark('ports_freed');

// Liberar YA los puertos clave (API/Web/XTB) antes de iniciar, con reintentos.
if (!ensureStackPortsFree()) {
  timeline.finish('failed', { phase: 'ports' });
  process.exit(1);
}

/**
 * Libera de forma robusta los puertos del stack justo ANTES de usarlos.
 * Con `strictPort:true`, un Vite huérfano de un arranque previo que aún no
 * había bindeado 5173 al inicio podía dejar el puerto ocupado y provocar un
 * aborto en seco (ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL) en cada arranque.
 * @returns {boolean} true si todos los puertos quedaron libres
 */
function ensureStackPortsFree() {
  let ok = true;
  for (const [label, port] of [
    ['API', API_PORT],
    ['Web', WEB_PORT],
    ['XTB mock', XTB_BRIDGE_PORT],
  ]) {
    if (!ensurePortFree(port, { label: 'dev', attempts: 4 })) {
      logError('dev', `Puerto ${port} (${label}) sigue ocupado. Ejecuta: node scripts/dev-doctor.mjs --fix-ports`);
      ok = false;
    }
  }
  return ok;
}

const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const logFile = join(ROOT, 'logs', 'dev', `dev-${stamp}.log`);

function lanWebUrls(port) {
  const urls = [];
  for (const ifaces of Object.values(os.networkInterfaces())) {
    for (const iface of ifaces ?? []) {
      if (iface.family === 'IPv4' && !iface.internal) {
        urls.push(`http://${iface.address}:${port}`);
      }
    }
  }
  return urls;
}

const networkUrls = lanWebUrls(WEB_PORT);

logInfo('dev', `Iniciando stack — API :${API_PORT} + Web :${WEB_PORT}`);
logInfo('dev', `Local: http://localhost:${WEB_PORT}`);
if (networkUrls.length > 0) {
  logInfo('dev', `LAN: ${networkUrls.join(', ')}`);
}
writeAgentLog('dev', {
  status: 'starting',
  stack: 'python+web',
  webPort: WEB_PORT,
  apiPort: API_PORT,
  logFile: `logs/dev/dev-${stamp}.log`,
});

timeline.mark('shared_build_start');
if (sharedPackageNeedsBuild()) {
  logInfo('dev', 'Compilando @bolsa/shared...');
  const sharedBuild = spawnSync('npm', ['run', 'build'], {
    cwd: join(ROOT, 'packages', 'shared'),
    stdio: 'inherit',
    shell: true,
  });
  if (sharedBuild.status !== 0) {
    logError('dev', 'Fallo compilacion @bolsa/shared');
    timeline.finish('failed', { phase: 'shared_build' });
    process.exit(sharedBuild.status ?? 1);
  }
  timeline.mark('shared_build_done', { rebuilt: true });
} else {
  logInfo('dev', '@bolsa/shared al día — skip build');
  timeline.mark('shared_build_done', { rebuilt: false });
}

const apiDir = join(ROOT, 'apps', 'api-python');
const python = resolvePython();
logInfo('dev', `Python: ${python}`);

const children = [];
let shuttingDown = false;

function tee(stream, label, logFn) {
  stream.on('data', (chunk) => {
    process[label === 'stdout' ? 'stdout' : 'stderr'].write(chunk);
    logFn(`[${label}] ${chunk.toString()}`);
  });
}

/**
 * Termina un proceso bajando TODO su árbol de procesos.
 * - Windows: `taskkill /PID <pid> /T /F` (mata hijos). `kill('SIGTERM')` no
 *   propaga a descendientes cuando se usa `shell:true` (pnpm.cmd).
 * - Unix: SIGTERM con fallback a SIGKILL tras un margen.
 */
function terminateProcessTree(child) {
  if (!child || child.exitCode !== null) return;
  const pid = child.pid;
  if (!pid) return;
  try {
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' });
    } else {
      try {
        child.kill('SIGTERM');
      } catch {
        // ignore
      }
    }
  } catch {
    try {
      child.kill('SIGKILL');
    } catch {
      // ignore
    }
  }
}

const { appendFileSync } = await import('node:fs');
const log = (line) => appendFileSync(logFile, line);

const xtbChildEarly = XTB_BRIDGE_AUTOSTART
  ? spawn(process.execPath, [join(ROOT, 'scripts', 'xtb-bridge-mock.mjs')], {
      cwd: ROOT,
      stdio: ['inherit', 'pipe', 'pipe'],
      env: { ...process.env, XTB_BRIDGE_PORT: String(XTB_BRIDGE_PORT) },
      shell: false,
    })
  : null;
if (xtbChildEarly) {
  children.push(xtbChildEarly);
  logInfo('dev', `Bridge XTB mock -> http://localhost:${XTB_BRIDGE_PORT}`);
  tee(xtbChildEarly.stdout, 'stdout', log);
  tee(xtbChildEarly.stderr, 'stderr', log);
}

// La API arranca primero y se espera a su health; Vite NO se levanta hasta que
// la API responde. Así evitamos la cascada de ECONNREFUSED (/sync) que antes
// tumbaba el stack en cada arranque.
logInfo('dev', 'Arrancando API Python...');
timeline.mark('api_spawn');
const apiChild = spawn(python, [join(apiDir, 'run_dev.py')], {
  cwd: apiDir,
  stdio: ['inherit', 'pipe', 'pipe'],
  env: {
    ...process.env,
    PYTHONPATH: join(apiDir, 'src'),
    API_PYTHON_PORT: String(API_PORT),
  },
  shell: false,
});
children.push(apiChild);
tee(apiChild.stdout, 'stdout', log);
tee(apiChild.stderr, 'stderr', log);

const apiReady = await waitForApi({
  port: API_PORT,
  maxWaitMs: 120_000,
  log: (msg) => logInfo('dev', msg),
});

if (!apiReady.ok) {
  logError('dev', 'La API no arrancó a tiempo. Revisa logs arriba.');
  for (const child of children) terminateProcessTree(child);
  timeline.finish('failed', { phase: 'api_health', waitMs: apiReady.elapsedMs });
  process.exit(1);
}
timeline.mark('api_ready', { waitMs: apiReady.elapsedMs });

let webReadyMarked = false;

logInfo('dev', 'API lista — arrancando Web (Vite)...');
timeline.mark('web_spawn');
// Un Vite huérfano de un arranque previo puede bindear 5173 con retardo:
// re-liberar justo aquí para que `strictPort` no provoque un aborto en seco.
if (!ensurePortFree(WEB_PORT)) {
  logInfo('dev', `Re-chequeo puerto ${WEB_PORT} (Web) liberado`);
}
const webChild = spawnPnpm(['--filter', '@bolsa/web', 'dev'], {
  stdio: ['inherit', 'pipe', 'pipe'],
  env: { ...process.env, BOLSA_LOG_DIR: join(ROOT, 'logs'), WEB_PORT: String(WEB_PORT) },
});
children.push(webChild);

webChild.stdout.on('data', (chunk) => {
  process.stdout.write(chunk);
  const text = chunk.toString();
  if (!webReadyMarked && (text.includes('ready in') || text.includes(`localhost:${WEB_PORT}`))) {
    webReadyMarked = true;
    logInfo('dev', `Web lista -> http://localhost:${WEB_PORT}`);
    timeline.mark('web_ready');
    timeline.finish('ready');
    writeAgentLog('startup', readLatestStartupReport() ?? { status: 'ready' });
    writeAgentLog('dev', { status: 'ready', webPort: WEB_PORT, apiPort: API_PORT });
  }
  log(`[stdout] ${text}`);
});
webChild.stderr.on('data', (chunk) => {
  process.stderr.write(chunk);
  log(`[stderr] ${chunk.toString()}`);
});

const arqChild =
  SCAN_QUEUE_BACKEND === 'arq'
    ? spawn(python, ['-m', 'bolsa_api.workers.arq_worker'], {
        cwd: apiDir,
        stdio: ['inherit', 'pipe', 'pipe'],
        env: { ...process.env, PYTHONPATH: join(apiDir, 'src') },
        shell: false,
      })
    : null;
if (arqChild) {
  children.push(arqChild);
  logInfo('dev', 'Worker Arq (SCAN_QUEUE_BACKEND=arq)');
  tee(arqChild.stdout, 'stdout', log);
  tee(arqChild.stderr, 'stderr', log);
}

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  logInfo('dev', `Deteniendo stack (exit=${code})…`);
  for (const child of children) terminateProcessTree(child);
  writeAgentLog('dev', { status: 'stopped', exitCode: code });
  process.exit(code);
}

apiChild.on('exit', (code) => {
  if (code && code !== 0) shutdown(code);
});
webChild.on('exit', (code) => {
  // Si Vite muere sin haber estado listo, seguro que algo falló en el boot.
  // Si ya estaba listo, un exit de Vite en dev suele ser intencional (Ctrl+C).
  if (!webReadyMarked && code && code !== 0) shutdown(code);
});

process.on('SIGINT', () => shutdown(0));
process.on('SIGTERM', () => shutdown(0));
// Guardia frente a huérfanos si el padre muere por crash/kill abrupto.
process.on('exit', () => {
  for (const child of children) terminateProcessTree(child);
});
