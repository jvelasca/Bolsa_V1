#!/usr/bin/env node
/**
 * Comprueba arranque / salud FA: import API + health HTTP + rutas FA montadas.
 *
 * Uso:
 *   node scripts/research/verify_fa_boot.mjs
 *   FA_BOOT_REQUIRED=1 node scripts/research/verify_fa_boot.mjs  # falla si API/web down
 *
 * No arranca servidores: usa API/web ya vivos o SKIP (salvo FA_BOOT_REQUIRED=1).
 */

import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const API = (process.env.BOLSA_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const WEB = (process.env.BOLSA_WEB_URL || 'http://127.0.0.1:5173').replace(/\/$/, '');
const REQUIRED = ['1', 'true', 'yes', 'on'].includes(
  (process.env.FA_BOOT_REQUIRED || '').trim().toLowerCase(),
);

async function httpOk(url, timeoutMs = 4000) {
  // Evitar AbortController: en Windows Node a veces crashea al salir (UV_HANDLE_CLOSING).
  try {
    const res = await Promise.race([
      fetch(url),
      new Promise((_, reject) => {
        setTimeout(() => reject(new Error('timeout')), timeoutMs);
      }),
    ]);
    return { ok: res.ok, status: res.status };
  } catch (err) {
    return { ok: false, status: 0, error: String(err?.message || err) };
  }
}

function checkApiImport() {
  const script = path.join(root, 'scripts', 'research', 'verify_fa_boot_import.py');
  const py = spawnSync('python', [script], {
    cwd: path.join(root, 'apps', 'api-python'),
    encoding: 'utf-8',
    // shell:false — shell:true + spawnSync provoca UV_HANDLE_CLOSING en Win a veces
    windowsHide: true,
  });
  if (py.status !== 0) {
    console.error(py.stdout || '');
    console.error(py.stderr || '');
    return false;
  }
  console.log((py.stdout || '').trim());
  return true;
}

console.log('=== verify_fa_boot ===');
console.log(`API=${API} WEB=${WEB} required=${REQUIRED}`);

if (!checkApiImport()) {
  console.error('FAIL: API import / rutas FA');
  process.exitCode = 1;
} else {
  const health = await httpOk(`${API}/api/health`);
  const web = await httpOk(WEB);
  const accounts = await httpOk(`${API}/api/accounts`);

  if (!health.ok) {
    const msg = `API health ${health.status || health.error}`;
    if (REQUIRED) {
      console.error(`FAIL: ${msg}`);
      process.exitCode = 1;
    } else {
      console.log(`SKIP live API: ${msg}`);
    }
  } else {
    console.log(`OK live API health ${health.status}`);
  }

  if (process.exitCode !== 1) {
    if (!accounts.ok) {
      if (REQUIRED) {
        console.error(`FAIL: /api/accounts ${accounts.status}`);
        process.exitCode = 1;
      } else {
        console.log(`SKIP /api/accounts (${accounts.status || accounts.error})`);
      }
    } else {
      console.log(`OK /api/accounts ${accounts.status}`);
    }
  }

  if (process.exitCode !== 1) {
    if (!web.ok) {
      if (REQUIRED) {
        console.error(`FAIL: web ${web.status || web.error}`);
        process.exitCode = 1;
      } else {
        console.log(`SKIP web: ${web.status || web.error}`);
      }
    } else {
      console.log(`OK web ${web.status}`);
    }
  }

  if (process.exitCode !== 1) {
    console.log('OK: FA boot checks');
  }
}
