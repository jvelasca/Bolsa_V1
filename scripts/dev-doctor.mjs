#!/usr/bin/env node
/**
 * Diagnóstico del entorno de desarrollo Bolsa V1.
 * Uso: node scripts/dev-doctor.mjs [--fix-ports]
 */
import { execSync } from 'node:child_process';
import { checkPort, findDockerExe, isDockerDaemonRunning } from './lib/docker.mjs';
import { ensureLogDirs, logError, logInfo, logWarn, ROOT, writeAgentLog } from './lib/logger.mjs';
import { freePort, getListenerPids } from './lib/ports.mjs';
import { resolvePython } from './lib/python.mjs';
import { waitForApi } from './lib/wait-api.mjs';

const fixPorts = process.argv.includes('--fix-ports');
const API_PORT = Number(process.env.API_PYTHON_PORT ?? 8000);
const WEB_PORT = Number(process.env.WEB_PORT ?? 5173);
const XTB_PORT = Number(process.env.XTB_BRIDGE_PORT ?? 3002);
const PG_PORT = 5432;

const checks = [];

function record(name, ok, detail, hint) {
  checks.push({ name, ok, detail, hint });
}

function processNameWin(pid) {
  try {
    const out = execSync(
      `powershell -NoProfile -Command "(Get-Process -Id ${pid} -ErrorAction SilentlyContinue).ProcessName"`,
      { encoding: 'utf8' },
    );
    return out.trim() || 'unknown';
  } catch {
    return 'unknown';
  }
}

async function checkPortStatus(label, port) {
  const pids = getListenerPids(port);
  if (pids.length === 0) {
    record(label, true, `puerto ${port} libre`, null);
    return;
  }

  const details = pids.map((pid) => `PID ${pid} (${processNameWin(pid)})`).join(', ');
  record(
    label,
    false,
    `puerto ${port} ocupado: ${details}`,
    fixPorts
      ? `Ejecuta: node scripts/dev-doctor.mjs --fix-ports`
      : `Detén sesiones F5 anteriores o libera el puerto ${port}`,
  );

  if (fixPorts) {
    const freed = freePort(port);
    if (freed) {
      logInfo('doctor', `Puerto ${port} liberado`);
      record(`${label} (fix)`, true, `puerto ${port} liberado`, null);
    }
  }
}

async function main() {
  ensureLogDirs();
  logInfo('doctor', '=== Bolsa V1 — diagnóstico de desarrollo ===');

  // Runtime
  const nodeOk = Number(process.version.slice(1).split('.')[0]) >= 20;
  record('Node.js >= 20', nodeOk, process.version, nodeOk ? null : 'Instala Node 20+');

  try {
    const pnpmVer = execSync('pnpm --version', { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    record('pnpm', true, pnpmVer, null);
  } catch {
    record('pnpm', false, 'no encontrado', 'npm install -g pnpm');
  }

  try {
    const python = resolvePython();
    const pyVer = execSync(`"${python}" --version`, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    record('Python', true, `${python} (${pyVer})`, null);
  } catch {
    record('Python', false, 'no encontrado', 'Instala Python 3.11+');
  }

  // Docker / PostgreSQL
  const docker = findDockerExe();
  if (!docker) {
    record('Docker CLI', false, 'no instalado', 'Instala Docker Desktop');
  } else {
    record('Docker CLI', true, docker, null);
    record('Docker daemon', isDockerDaemonRunning(docker), isDockerDaemonRunning(docker) ? 'activo' : 'parado', 'Abre Docker Desktop');
  }

  const pgUp = await checkPort('127.0.0.1', PG_PORT);
  record(
    'PostgreSQL :5432',
    pgUp,
    pgUp ? 'responde' : 'no responde',
    pgUp ? null : 'node scripts/db-ensure.mjs (primera vez o tras reiniciar PC)',
  );

  // Puertos app
  await checkPortStatus('API :8000', API_PORT);
  await checkPortStatus('Web :5173', WEB_PORT);
  await checkPortStatus('XTB mock :3002', XTB_PORT);

  // HTTP si ya hay servicios
  if (getListenerPids(API_PORT).length > 0) {
    const apiWait = await waitForApi({ port: API_PORT, maxWaitMs: 3000, log: () => {} });
    record('API /health', apiWait.ok, apiWait.ok ? `${apiWait.elapsedMs}ms` : 'no responde', 'Reinicia con F5 Dev');
  }

  if (getListenerPids(WEB_PORT).length > 0) {
    try {
      const res = await fetch(`http://127.0.0.1:${WEB_PORT}/`, { signal: AbortSignal.timeout(3000) });
      record('Web Vite', res.ok, `HTTP ${res.status}`, null);
    } catch (error) {
      record('Web Vite', false, error instanceof Error ? error.message : 'error', null);
    }
  }

  const failed = checks.filter((c) => !c.ok);
  const report = {
    status: failed.length === 0 ? 'ready' : pgUp ? 'degraded' : 'blocked',
    checks,
    recommendation:
      failed.length === 0
        ? 'Listo para F5 — usa launch «Bolsa: F5 Dev (recomendado)»'
        : !pgUp
          ? 'Primero: node scripts/db-ensure.mjs'
          : 'Libera puertos conflictivos y relanza F5',
  };

  writeAgentLog('doctor', report);

  for (const item of checks) {
    const line = `${item.ok ? 'OK' : 'FAIL'}  ${item.name}: ${item.detail}`;
    if (item.ok) logInfo('doctor', line);
    else if (item.name.includes('ocupado')) logWarn('doctor', line);
    else logError('doctor', line);
    if (!item.ok && item.hint) logInfo('doctor', `      → ${item.hint}`);
  }

  logInfo('doctor', '---');
  logInfo('doctor', report.recommendation);

  process.exit(failed.some((c) => c.name === 'PostgreSQL :5432') ? 2 : failed.length > 0 ? 1 : 0);
}

main().catch((error) => {
  logError('doctor', error instanceof Error ? error.message : String(error));
  process.exit(1);
});
