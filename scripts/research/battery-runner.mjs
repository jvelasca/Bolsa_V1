#!/usr/bin/env node
/**
 * Shared runner for research batteries (spawn + phase logging).
 */

import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const isWin = process.platform === 'win32';

export function runPhase(label, command, args, env = {}) {
  console.log(`\n── ${label} ──`);
  console.log(`$ ${command} ${args.join(' ')}`);
  const result = spawnSync(command, args, {
    cwd: repoRoot,
    stdio: 'inherit',
    env: { ...process.env, ...env },
    shell: isWin,
  });
  const code = result.status ?? 1;
  if (code !== 0) {
    console.error(`\n✗ FAIL: ${label} (exit ${code})`);
    return false;
  }
  console.log(`✓ OK: ${label}`);
  return true;
}

export function runVitestWeb(label, files) {
  return runPhase(label, 'pnpm', [
    '--filter',
    '@bolsa/web',
    'exec',
    'vitest',
    'run',
    ...files,
  ]);
}

export function runVitestShared(label, files) {
  return runPhase(label, 'pnpm', [
    '--filter',
    '@bolsa/shared',
    'exec',
    'vitest',
    'run',
    ...files,
  ]);
}

export function runPytest(label, files) {
  return runPhase(label, 'python', ['-m', 'pytest', ...files, '-q']);
}
