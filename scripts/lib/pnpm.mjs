import { spawn, spawnSync } from 'node:child_process';
import { ROOT } from './logger.mjs';

/** En PowerShell, `pnpm` apunta a pnpm.ps1 (bloqueado). Usar pnpm.cmd en Windows. */
export function getPnpmCommand() {
  return process.platform === 'win32' ? 'pnpm.cmd' : 'pnpm';
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
  const cmd = getPnpmCommand();
  return spawn(cmd, args, {
    cwd: options.cwd ?? ROOT,
    shell: true,
    stdio: options.stdio ?? 'inherit',
    env: { ...process.env, ...options.env },
  });
}
