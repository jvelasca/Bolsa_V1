import { spawn, spawnSync } from 'node:child_process';
import { homedir } from 'node:os';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT } from './logger.mjs';

/**
 * En PowerShell, `pnpm` apunta a pnpm.ps1 (bloqueado). Usar pnpm.cmd en Windows.
 */
export function getPnpmCommand() {
  return process.platform === 'win32' ? 'pnpm.cmd' : 'pnpm';
}

/**
 * Binario Node real de pnpm (sin el wrapper `cmd`). Lanzarlo con `node` evita
 * el `cmd /c` intermedio: el proceso Vite queda como descendiente directo y el
 * `exit`/`taskkill /T` se propagan de forma fiable (sin huérfanos).
 */
function getPnpmNodeEntry() {
  const prefix =
    process.env.npm_config_prefix || join(homedir(), 'AppData', 'Roaming', 'npm');
  const entry = join(prefix, 'node_modules', 'pnpm', 'bin', 'pnpm.cjs');
  return existsSync(entry) ? entry : null;
}

export function runPnpm(args, options = {}) {
  const cmd = getPnpmCommand();
  return spawnSync(cmd, args, {
    cwd: options.cwd ?? ROOT,
    shell: true,
    stdio: options.stdio ?? 'inherit',
    encoding: options.encoding,
    env: { ...process.env, ...options.env },
  });
}

export function spawnPnpm(args, options = {}) {
  if (process.platform === 'win32') {
    const entry = getPnpmNodeEntry();
    if (entry) {
      // Lanzar pnpm directamente con Node: sin shell, sin cmd intermedio.
      return spawn(process.execPath, [entry, ...args], {
        cwd: options.cwd ?? ROOT,
        stdio: options.stdio ?? 'inherit',
        env: { ...process.env, ...options.env },
      });
    }
  }
  const cmd = getPnpmCommand();
  return spawn(cmd, args, {
    cwd: options.cwd ?? ROOT,
    shell: true,
    stdio: options.stdio ?? 'inherit',
    env: { ...process.env, ...options.env },
  });
}
