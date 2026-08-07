import { execSync } from 'node:child_process';

/**
 * PIDs en LISTEN sobre un puerto TCP (puede haber varios en Windows).
 * En Windows usa solo `netstat` (rápido). PowerShell Get-NetTCPConnection
 * añadía ~1s por puerto y dominaba el arranque F5 (~3s).
 * @param {number} port
 * @returns {number[]}
 */
export function getListenerPids(port) {
  const pids = new Set();

  if (process.platform === 'win32') {
    try {
      const out = execSync(`netstat -ano -p tcp`, { encoding: 'utf8' });
      const needle = `:${port}`;
      for (const line of out.split(/\r?\n/)) {
        if (!line.includes('LISTENING')) continue;
        const parts = line.trim().split(/\s+/);
        const local = parts[1] ?? '';
        // :5173 o 0.0.0.0:5173 / [::]:5173
        if (!local.endsWith(needle)) continue;
        // Evitar falsos positivos (:51730)
        const idx = local.lastIndexOf(':');
        if (idx < 0 || Number(local.slice(idx + 1)) !== port) continue;
        const pid = Number(parts[parts.length - 1]);
        if (Number.isFinite(pid) && pid > 0) pids.add(pid);
      }
    } catch {
      // Puerto libre o comando sin resultados.
    }
  } else {
    try {
      const out = execSync(`lsof -ti tcp:${port} -sTCP:LISTEN`, { encoding: 'utf8' });
      for (const line of out.split('\n')) {
        const pid = Number(line.trim());
        if (Number.isFinite(pid) && pid > 0) pids.add(pid);
      }
    } catch {
      // Puerto libre o comando sin resultados.
    }
  }

  return [...pids];
}

/** @param {number} port @returns {number | null} */
export function getListenerPid(port) {
  return getListenerPids(port)[0] ?? null;
}

/** @param {number} ms */
function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

/** @param {number} pid @returns {boolean} */
function killPid(pid) {
  if (pid === process.pid) return false;

  try {
    if (process.platform === 'win32') {
      try {
        execSync(`taskkill /PID ${pid} /F /T`, { stdio: 'ignore' });
        return true;
      } catch {
        try {
          execSync(
            `powershell -NoProfile -Command "Stop-Process -Id ${pid} -Force -ErrorAction SilentlyContinue"`,
            { stdio: 'ignore' },
          );
          return true;
        } catch {
          return false;
        }
      }
    }

    process.kill(pid, 'SIGTERM');
    return true;
  } catch {
    return false;
  }
}

/**
 * Libera un puerto matando todos los procesos en LISTEN.
 * @param {number} port
 * @returns {boolean} true si se terminó al menos un proceso
 */
export function freePort(port) {
  let killed = false;

  for (const pid of getListenerPids(port)) {
    if (killPid(pid)) killed = true;
  }

  return killed;
}

/**
 * Intenta liberar el puerto varias veces antes de arrancar un servidor.
 * @param {number} port
 * @param {{ attempts?: number, label?: string }} [options]
 * @returns {boolean} true si el puerto quedó libre
 */
export function ensurePortFree(port, options = {}) {
  const { attempts = 3, label = 'ports' } = options;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const pids = getListenerPids(port);
    if (pids.length === 0) {
      return true;
    }

    for (const pid of pids) {
      killPid(pid);
    }

    if (attempt < attempts) {
      sleep(400);
    }
  }

  const remaining = getListenerPids(port);
  if (remaining.length > 0) {
    console.warn(
      `[${label}] Puerto ${port} sigue ocupado por PID(s): ${remaining.join(', ')}`,
    );
    console.warn(
      `[${label}] Detén sesiones de depuración anteriores (Bolsa: API Python) y vuelve a arrancar.`,
    );
    return false;
  }

  return true;
}
