#!/usr/bin/env node
/**
 * D6 Ciclo C2: public Prisma schema commands fail closed.
 * Invokes the fail script directly (no Docker).
 *
 *   node scripts/research/verify_prisma_not_authoritative.mjs
 */

import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const script = path.join(root, 'scripts', 'prisma-not-authoritative.mjs');
const MSG = 'Prisma schema is not authoritative. Use Alembic.';

const result = spawnSync(process.execPath, [script], {
  cwd: root,
  encoding: 'utf8',
  windowsHide: true,
});

const combined = `${result.stderr || ''}${result.stdout || ''}`;
const code = result.status ?? 0;

if (code === 0) {
  console.error('FAIL: expected non-zero exit from prisma-not-authoritative.mjs');
  process.exit(1);
}
if (!combined.includes(MSG)) {
  console.error(`FAIL: output missing exact message.\n---\n${combined}\n---`);
  process.exit(1);
}

console.log(`OK: exit ${code}; message present`);
