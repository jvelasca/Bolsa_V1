/**
 * Cache de migraciones Prisma: si el árbol de migrations/ no cambió, skip deploy.
 * Acelera `pnpm dev` / F5 en warm start (Prisma deploy vacío sigue costando varios segundos).
 */

import { createHash } from 'node:crypto';
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { join } from 'node:path';
import { ROOT } from './logger.mjs';

const CACHE_DIR = join(ROOT, '.cache');
const STAMP_PATH = join(CACHE_DIR, 'prisma-migrate-stamp.json');
const MIGRATIONS_DIR = join(ROOT, 'packages', 'database', 'prisma', 'migrations');

export function migrationsFingerprint(dir = MIGRATIONS_DIR) {
  if (!existsSync(dir)) return 'missing';
  const names = readdirSync(dir).filter((name) => {
    try {
      return statSync(join(dir, name)).isDirectory();
    } catch {
      return false;
    }
  });
  names.sort();
  const hash = createHash('sha1');
  hash.update(names.join('\n'));
  for (const name of names) {
    const sql = join(dir, name, 'migration.sql');
    if (!existsSync(sql)) continue;
    hash.update(name);
    hash.update(readFileSync(sql));
  }
  const lock = join(dir, 'migration_lock.toml');
  if (existsSync(lock)) hash.update(readFileSync(lock));
  return hash.digest('hex');
}

export function shouldSkipMigrateDeploy() {
  const fp = migrationsFingerprint();
  if (!existsSync(STAMP_PATH)) return { skip: false, fp };
  try {
    const prev = JSON.parse(readFileSync(STAMP_PATH, 'utf8'));
    if (prev && prev.fp === fp) return { skip: true, fp };
  } catch {
    // ignore corrupt stamp
  }
  return { skip: false, fp };
}

export function writeMigrateStamp(fp) {
  mkdirSync(CACHE_DIR, { recursive: true });
  writeFileSync(
    STAMP_PATH,
    JSON.stringify({ fp, at: new Date().toISOString() }, null, 2),
    'utf8',
  );
}
